from __future__ import annotations

import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import KnowledgeChunk, KnowledgeDocument
from app.services.embeddings import cosine_matrix, embed_texts
from app.services.llm import chat_completion

QUESTION_HINTS: dict[str, str] = {
    "uz": "Hujjatga ko'ra:",
    "ru": "Согласно документу:",
    "en": "According to the document:",
}

NO_ANSWER: dict[str, str] = {
    "uz": "Bu savolga hujjatlarda aniq javob topa olmadim.",
    "ru": "В документах нет точного ответа на этот вопрос.",
    "en": "I couldn't find a precise answer in the documents.",
}


_QUERY_STOP = {
    "bormi", "qanday", "qanaqa", "qancha", "necha", "nima", "kerak", "mumkin",
    "iltimos", "please", "what", "how", "can", "does", "the", "and", "for", "with",
    "есть", "как", "что", "можно", "скажите", "подскажите",
}


def _content_tokens(text: str) -> set[str]:
    return {
        word for word in re.findall(r"[\w']{3,}", text.lower())
        if word not in _QUERY_STOP
    }


def _matches(token: str, tokens: set[str]) -> bool:
    if token in tokens:
        return True
    return len(token) >= 4 and any(word.startswith(token[:4]) for word in tokens)


def _lexical_score(query_tokens: set[str], content: str) -> float:
    if not query_tokens:
        return 0.0
    lines = content.splitlines()
    heading_tokens = _content_tokens(lines[0]) if lines else set()
    body_tokens = _content_tokens("\n".join(lines[1:]))
    hits = 0.0
    for token in query_tokens:
        if _matches(token, heading_tokens):
            hits += 2.0
        elif _matches(token, body_tokens):
            hits += 1.0
    return min(hits / len(query_tokens), 1.0)


async def semantic_search(
    db: AsyncSession, org_id: str, query: str, top_k: int = 4, min_score: float = 0.12
) -> list[dict[str, Any]]:
    stmt = (
        select(KnowledgeChunk, KnowledgeDocument.filename)
        .join(KnowledgeDocument, KnowledgeDocument.id == KnowledgeChunk.document_id)
        .where(KnowledgeChunk.org_id == org_id)
    )
    rows = (await db.execute(stmt)).all()
    if not rows:
        return []

    query_vector = (await embed_texts([query]))[0]
    semantic = cosine_matrix(query_vector, [row[0].embedding for row in rows])
    query_tokens = _content_tokens(query)

    combined = [
        0.6 * float(semantic[index]) + 0.4 * _lexical_score(query_tokens, rows[index][0].content)
        for index in range(len(rows))
    ]
    ranked = sorted(range(len(rows)), key=lambda i: combined[i], reverse=True)[:top_k]
    results = []
    for index in ranked:
        score = combined[index]
        if score < min_score:
            continue
        chunk, filename = rows[index]
        results.append(
            {
                "document_id": chunk.document_id,
                "document_name": filename,
                "chunk_index": chunk.chunk_index,
                "score": round(score, 4),
                "content": chunk.content,
                "snippet": chunk.content[:320].replace("\n", " ").strip(),
            }
        )
    return results


def _tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[\w']{3,}", text.lower())}


def _overlap(query_tokens: set[str], sentence_tokens: set[str]) -> int:
    hits = 0
    for token in query_tokens:
        if token in sentence_tokens:
            hits += 1
        elif len(token) >= 4 and any(word.startswith(token[:4]) for word in sentence_tokens):
            hits += 1
    return hits


def _is_heading_sentence(value: str) -> bool:
    letters = [ch for ch in value if ch.isalpha()]
    return bool(letters) and len(value) <= 60 and value.upper() == value


def extractive_answer(query: str, sources: list[dict[str, Any]], lang: str) -> str:
    if not sources:
        return NO_ANSWER[lang]
    query_tokens = _tokens(query)
    body = [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+|\n+", sources[0]["content"])
        if len(sentence.strip()) >= 25 and not _is_heading_sentence(sentence.strip())
    ]
    sentences: list[tuple[int, int, str]] = []
    for position, sentence in enumerate(body):
        overlap = _overlap(query_tokens, _tokens(sentence))
        if overlap:
            sentences.append((overlap, position, sentence))
    if not sentences:
        fallback = " ".join(body[:2]).strip() or sources[0]["snippet"].strip()
        return f"{QUESTION_HINTS[lang]} " + fallback
    sentences.sort(key=lambda item: (-item[0], item[1]))
    chosen = sorted(sentences[:3], key=lambda item: item[1])
    return f"{QUESTION_HINTS[lang]} " + " ".join(item[2] for item in chosen)


async def rag_answer(
    db: AsyncSession,
    org_id: str,
    query: str,
    lang: str,
    agent_name: str = "Nova",
    persona: str = "",
    temperature: float = 0.3,
) -> tuple[str, list[dict[str, Any]]]:
    sources = await semantic_search(db, org_id, query, top_k=4)
    if not sources:
        return NO_ANSWER[lang], []

    if not settings.llm_enabled:
        return extractive_answer(query, sources, lang), sources

    context = "\n\n".join(
        f"[{i + 1}] {s['document_name']} (chunk {s['chunk_index']}):\n{s['content']}"
        for i, s in enumerate(sources)
    )
    system = (
        f"You are {agent_name}, a sales and support assistant. {persona}\n"
        f"Answer ONLY using the CONTEXT below. If the answer is missing, say you don't know "
        f"and offer to connect an operator. Answer in the language of the customer's question "
        f"(Uzbek, Russian or English). Be concise: 2-4 sentences. Never invent facts, prices or dates.\n\n"
        f"CONTEXT:\n{context}"
    )
    try:
        message = await chat_completion(
            [{"role": "system", "content": system}, {"role": "user", "content": query}],
            temperature=temperature,
        )
        text = (message.get("content") or "").strip()
        if text:
            return text, sources
    except Exception:
        pass
    return extractive_answer(query, sources, lang), sources
