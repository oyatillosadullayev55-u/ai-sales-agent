from __future__ import annotations

import csv
import io
import re

from docx import Document
from pypdf import PdfReader


def _decode(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1251", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="ignore")


def extract_text(filename: str, content_type: str, data: bytes) -> str:
    suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if suffix == "pdf" or "pdf" in content_type:
        reader = PdfReader(io.BytesIO(data))
        pages = [(page.extract_text() or "") for page in reader.pages]
        text = "\n\n".join(pages)
    elif suffix == "docx" or "wordprocessingml" in content_type:
        document = Document(io.BytesIO(data))
        parts = [p.text for p in document.paragraphs]
        for table in document.tables:
            for row in table.rows:
                cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if cells:
                    parts.append(" | ".join(cells))
        text = "\n".join(parts)
    elif suffix == "csv" or "csv" in content_type:
        raw = _decode(data)
        reader = csv.reader(io.StringIO(raw))
        lines = [" | ".join(cell.strip() for cell in row if cell.strip()) for row in reader]
        text = "\n".join(line for line in lines if line)
    else:
        text = _decode(data)

    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _is_heading(block: str) -> bool:
    value = block.strip()
    if not value or len(value) > 90:
        return False
    if value.startswith("#"):
        return True
    if value.endswith((".", "!", "?", ";", ",")):
        return False
    words = value.split()
    if len(words) > 8:
        return False
    letters = [ch for ch in value if ch.isalpha()]
    if not letters:
        return False
    uppercase = sum(1 for ch in letters if ch.isupper())
    return uppercase / len(letters) >= 0.6


def _split_section(section: str, size: int) -> list[str]:
    if len(section) <= size:
        return [section]

    sentences = [
        part.strip()
        for part in re.split(r"(?<=[.!?])\s+|\n+", section)
        if part.strip()
    ]
    chunks: list[str] = []
    buffer = ""
    for sentence in sentences:
        candidate = f"{buffer} {sentence}".strip() if buffer else sentence
        if len(candidate) <= size:
            buffer = candidate
            continue
        if buffer:
            chunks.append(buffer)
            buffer = ""
        while len(sentence) > size:
            cut = sentence.rfind(" ", 0, size)
            if cut < size // 2:
                cut = size
            chunks.append(sentence[:cut].strip())
            sentence = sentence[cut:].lstrip()
        if sentence:
            buffer = sentence
    if buffer:
        chunks.append(buffer)
    return chunks


def chunk_text(text: str, size: int = 320) -> list[str]:
    text = text.strip()
    if not text:
        return []

    sections: list[str] = []
    current: list[str] = []
    for line in (value.strip() for value in text.splitlines()):
        if not line:
            continue
        if _is_heading(line) and current:
            sections.append("\n".join(current))
            current = [line]
        else:
            current.append(line)
    if current:
        sections.append("\n".join(current))

    chunks: list[str] = []
    for section in sections:
        chunks.extend(_split_section(section.strip(), size))
    return [chunk for chunk in chunks if len(chunk.strip()) > 20]
