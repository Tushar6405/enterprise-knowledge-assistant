"""
main.py
FastAPI application exposing:
  POST /ingest/slack     - ingest a Slack export JSON
  POST /ingest/notion    - ingest a Notion markdown export
  POST /ingest/text      - ingest arbitrary text
  POST /query            - RAG query → Claude answer
  POST /slack/webhook    - Slack slash command handler
  GET  /health           - health + stats
  GET  /docs             - Swagger UI (auto)
"""

import hashlib
import hmac
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.rag_engine import (
    collection_stats,
    ingest_notion,
    ingest_slack,
    ingest_text,
    reset_collection,
    retrieve,
)
from app.synthesizer import synthesize

# ── Lifespan: pre-warm embedder on startup ────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.rag_engine import get_embedder, get_collection
    print("[Startup] Pre-warming embedding model...")
    get_embedder()
    get_collection()
    print("[Startup] Ready.")
    yield


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Enterprise Knowledge Assistant",
    description="RAG-powered internal Q&A over Slack + Notion knowledge base",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET", "")
DATA_DIR = Path("./data/sample")


# ── Pydantic models ───────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    query: str
    top_k: int = 5


class TextIngestRequest(BaseModel):
    text: str
    source_name: str
    doc_type: str = "manual"


class ResetRequest(BaseModel):
    confirm: str  # must be "YES_RESET"


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["System"])
def health():
    stats = collection_stats()
    return {
        "status": "ok",
        "knowledge_base": stats,
        "model": os.getenv("CLAUDE_MODEL", "claude-haiku-4-5"),
    }


# ── Ingestion endpoints ───────────────────────────────────────────────────────
@app.get("/", include_in_schema=False)
def serve_frontend():
    return FileResponse("index.html")

@app.post("/ingest/slack", tags=["Ingestion"])
async def ingest_slack_endpoint(file: UploadFile = File(None)):
    """
    Upload a Slack export JSON file, OR use the bundled sample data.
    If no file is uploaded, ingests ./data/sample/slack_export.json.
    """
    if file:
        content = await file.read()
        tmp_path = f"/tmp/slack_upload_{int(time.time())}.json"
        with open(tmp_path, "wb") as f:
            f.write(content)
        path = tmp_path
    else:
        path = str(DATA_DIR / "slack_export.json")
        if not Path(path).exists():
            raise HTTPException(404, "Sample Slack data not found. Upload a file.")

    chunks = ingest_slack(path)
    return {"status": "ok", "chunks_stored": chunks, "source": path}


@app.post("/ingest/notion", tags=["Ingestion"])
async def ingest_notion_endpoint(file: UploadFile = File(None)):
    """
    Upload a Notion markdown export, OR use the bundled sample data.
    If no file is uploaded, ingests ./data/sample/notion_export.md.
    """
    if file:
        content = await file.read()
        tmp_path = f"/tmp/notion_upload_{int(time.time())}.md"
        with open(tmp_path, "wb") as f:
            f.write(content)
        path = tmp_path
    else:
        path = str(DATA_DIR / "notion_export.md")
        if not Path(path).exists():
            raise HTTPException(404, "Sample Notion data not found. Upload a file.")

    chunks = ingest_notion(path)
    return {"status": "ok", "chunks_stored": chunks, "source": path}


@app.post("/ingest/text", tags=["Ingestion"])
def ingest_text_endpoint(body: TextIngestRequest):
    """Ingest arbitrary text — useful for testing or piping in custom docs."""
    chunks = ingest_text(body.text, body.source_name, body.doc_type)
    return {"status": "ok", "chunks_stored": chunks}


@app.post("/ingest/reset", tags=["Ingestion"])
def reset_endpoint(body: ResetRequest):
    """Wipe the entire knowledge base. Requires confirm='YES_RESET'."""
    if body.confirm != "YES_RESET":
        raise HTTPException(400, "Send confirm='YES_RESET' to wipe the knowledge base.")
    reset_collection()
    return {"status": "ok", "message": "Knowledge base wiped."}


# ── Query endpoint ────────────────────────────────────────────────────────────

@app.post("/query", tags=["Query"])
def query_endpoint(body: QueryRequest):
    """
    Main RAG query endpoint.
    Retrieves relevant chunks then calls Claude to synthesize an answer.
    """
    if not body.query.strip():
        raise HTTPException(400, "Query cannot be empty.")

    chunks = retrieve(body.query, top_k=body.top_k)
    result = synthesize(body.query, chunks)

    return {
        "query": body.query,
        "answer": result["answer"],
        "sources": result["sources"],
        "model": result["model"],
        "chunks_used": result["chunks_used"],
        "retrieved_chunks": [
            {"text": c["text"][:200] + "...", "source": c["source"], "score": c["score"]}
            for c in chunks
        ],
    }


# ── Slack slash command webhook ───────────────────────────────────────────────

def _verify_slack_signature(request_body: bytes, timestamp: str, signature: str) -> bool:
    """Verify the request actually came from Slack."""
    if not SLACK_SIGNING_SECRET:
        return True  # skip verification in dev/test

    if abs(time.time() - float(timestamp)) > 300:
        return False  # replay attack guard

    sig_basestring = f"v0:{timestamp}:{request_body.decode()}"
    computed = "v0=" + hmac.new(
        SLACK_SIGNING_SECRET.encode(),
        sig_basestring.encode(),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(computed, signature)


@app.post("/slack/webhook", tags=["Slack"])
async def slack_webhook(request: Request):
    """
    Handles Slack slash command /ask.
    Slack sends form data: token, text, user_name, channel_name, etc.
    We return a plain-text response that Slack renders to the user.

    Setup in Slack:
      1. Create a Slack App at api.slack.com/apps
      2. Add a Slash Command /ask → Request URL: https://your-render-url/slack/webhook
      3. Copy the Signing Secret into SLACK_SIGNING_SECRET env var
    """
    body = await request.body()
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "0")
    signature = request.headers.get("X-Slack-Signature", "")

    if not _verify_slack_signature(body, timestamp, signature):
        raise HTTPException(403, "Invalid Slack signature.")

    form = await request.form()
    query = form.get("text", "").strip()
    user = form.get("user_name", "someone")

    if not query:
        return PlainTextResponse(
            "Usage: `/ask <your question>`\nExample: `/ask What is the leave policy?`"
        )

    # Immediate response to avoid Slack's 3-second timeout
    # For production, use Slack's response_url for async replies
    try:
        chunks = retrieve(query, top_k=5)
        result = synthesize(query, chunks)
        answer = result["answer"]
        sources = result["sources"]

        sources_text = ""
        if sources:
            sources_text = "\n\n_Sources: " + " · ".join(
                f"`{s}`" for s in sources
            ) + "_"

        response_text = f"*Question from @{user}:* {query}\n\n{answer}{sources_text}"

    except Exception as e:
        response_text = f"Sorry, something went wrong: {str(e)}"

    return PlainTextResponse(response_text)


# ── Run locally ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
