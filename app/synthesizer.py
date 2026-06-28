"""
synthesizer.py - Uses Groq free tier for LLM answer synthesis
"""

import os
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

SYSTEM_PROMPT = """You are an internal knowledge assistant for a company.
Answer employee questions using ONLY the provided context excerpts from Slack and Notion.

Rules:
- Answer concisely. Use bullet points for multi-step answers.
- Cite sources using [Source: <source_name>] after each fact.
- If context is insufficient, say: "I don't have enough information in the knowledge base. Try #general or Notion directly."
- Never make up information outside the provided context.
- Keep answers under 200 words."""


def synthesize(query: str, chunks: list[dict]) -> dict:
    if not chunks:
        return {
            "answer": "I don't have enough information in the knowledge base to answer this.",
            "sources": [],
            "model": MODEL,
            "chunks_used": 0,
        }

    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        context_parts.append(
            f"[Excerpt {i} | Source: {chunk.get('source','unknown')} | Relevance: {chunk.get('score',0)}]\n{chunk.get('text','')}"
        )
    context = "\n\n---\n\n".join(context_parts)

    response = client.chat.completions.create(
        model=MODEL,
        max_tokens=512,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Context:\n{context}\n\n---\n\nQuestion: {query}\n\nAnswer:"}
        ],
    )

    answer = response.choices[0].message.content.strip()
    sources = list({c["source"] for c in chunks})

    return {
        "answer": answer,
        "sources": sources,
        "model": MODEL,
        "chunks_used": len(chunks),
    }