# Enterprise Knowledge Assistant

A production RAG system that ingests **Slack threads + Notion pages** and answers employee questions via a FastAPI endpoint or a **Slack slash command** (`/ask`).

Built with: Python · FastAPI · ChromaDB · Sentence Transformers · Anthropic Claude API · Docker · Render

---

## Architecture

```
Slack Export JSON ─┐
                   ├─► Chunker ─► Sentence Transformers ─► ChromaDB
Notion Export MD  ─┘                  (all-MiniLM-L6-v2)

User Query ─► Embed ─► ChromaDB Retrieve (top-5) ─► Claude (haiku) ─► Answer + Sources
                                                          ▲
                                                   System prompt with
                                                   strict grounding rules
```

---

## Quick Start (Local)

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Set environment variables
```bash
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

### 3. Ingest sample data
```bash
python scripts/ingest.py
```

### 4. Start the API
```bash
uvicorn app.main:app --reload
```

### 5. Test a query
```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the leave policy?"}'
```

Visit http://localhost:8000/docs for the full interactive Swagger UI.

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check + knowledge base stats |
| POST | `/ingest/slack` | Upload Slack export JSON (or use sample) |
| POST | `/ingest/notion` | Upload Notion markdown export (or use sample) |
| POST | `/ingest/text` | Ingest arbitrary text |
| POST | `/ingest/reset` | Wipe the knowledge base |
| POST | `/query` | RAG query → Claude answer |
| POST | `/slack/webhook` | Slack slash command handler |

### Example query response
```json
{
  "query": "What is the leave policy?",
  "answer": "Employees receive 12 annual leaves and 6 sick leaves per year. [Source: slack_hr-general] Submit requests in Zoho at least 3 days in advance. Manager approval is required for more than 3 consecutive days. [Source: notion_leave_policy]",
  "sources": ["slack_hr-general", "notion_leave_policy"],
  "model": "claude-haiku-4-5",
  "chunks_used": 5
}
```

---

## Ingesting Your Own Data

### Slack
Export your Slack workspace: Workspace Settings → Import/Export → Export → JSON
```bash
python scripts/ingest.py --slack path/to/your/slack-export.json
```

### Notion
Export Notion pages: Page menu → Export → Markdown & CSV
```bash
python scripts/ingest.py --notion path/to/your/notion-export.md
```

### Reset and re-ingest
```bash
python scripts/ingest.py --reset --slack data/slack.json --notion data/notion.md
```

---

## Slack Integration Setup

1. Go to [api.slack.com/apps](https://api.slack.com/apps) → Create New App
2. Add a **Slash Command**: `/ask` → Request URL: `https://your-render-url.onrender.com/slack/webhook`
3. Install the app to your workspace
4. Copy the **Signing Secret** → add to Render env vars as `SLACK_SIGNING_SECRET`
5. Type `/ask What is the leave policy?` in any Slack channel

---

## Deploy to Render

1. Push this repo to GitHub
2. Go to [render.com](https://render.com) → New → Web Service → Connect your repo
3. Render auto-detects `render.yaml`
4. Add env vars in the Render dashboard:
   - `ANTHROPIC_API_KEY` ← your Anthropic key
   - `SLACK_SIGNING_SECRET` ← from Slack app settings (optional)
5. Deploy — the disk mount persists ChromaDB across deploys
6. After deploy, hit `POST /ingest/slack` and `POST /ingest/notion` (no file needed, uses sample data)

---

## Project Structure

```
enterprise-knowledge-assistant/
├── app/
│   ├── main.py          # FastAPI app + all endpoints
│   ├── rag_engine.py    # Chunking, embedding, ChromaDB retrieval
│   └── synthesizer.py   # Claude API answer synthesis
├── data/sample/
│   ├── slack_export.json   # Sample Slack data for testing
│   └── notion_export.md    # Sample Notion data for testing
├── scripts/
│   └── ingest.py        # CLI script to seed ChromaDB
├── Dockerfile
├── render.yaml
├── requirements.txt
└── .env.example
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | required | Your Anthropic API key |
| `SLACK_SIGNING_SECRET` | optional | Slack app signing secret |
| `CLAUDE_MODEL` | `claude-haiku-4-5` | Claude model to use |
| `CHROMA_PATH` | `./chroma_db` | ChromaDB persistence directory |
| `TOP_K` | `5` | Number of chunks to retrieve per query |
| `CHUNK_SIZE` | `400` | Characters per chunk |
| `CHUNK_OVERLAP` | `80` | Overlap between chunks |
