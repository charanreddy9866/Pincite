"""PDF → page text (with OCR for scanned pages) → redaction → chunks → embeddings → SQLite."""

import io
import json
import logging
from collections import Counter
from dataclasses import dataclass

import numpy as np
import pdfplumber

from .config import get_settings
from .db import Database, now
from .llm import LLM
from .redact import redact

logging.getLogger("pdfminer").setLevel(logging.ERROR)  # silence noisy CropBox warnings

MIN_TEXT_CHARS = 25  # below this a page is treated as scanned and sent to OCR


@dataclass
class ExtractedPage:
    page_no: int
    text: str
    ocr: bool


def _ocr_page(pdf_bytes: bytes, index: int) -> str:
    import pypdfium2 as pdfium
    import pytesseract

    pdf = pdfium.PdfDocument(pdf_bytes)
    try:
        image = pdf[index].render(scale=300 / 72).to_pil()
        return pytesseract.image_to_string(image)
    finally:
        pdf.close()


def extract_pages(pdf_bytes: bytes, ocr_enabled: bool = True) -> list[ExtractedPage]:
    pages: list[ExtractedPage] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            used_ocr = False
            if len(text.strip()) < MIN_TEXT_CHARS and ocr_enabled:
                try:
                    ocr_text = _ocr_page(pdf_bytes, i)
                    if len(ocr_text.strip()) > len(text.strip()):
                        text, used_ocr = ocr_text, True
                except Exception:
                    pass  # OCR is best-effort; keep whatever text layer exists
            pages.append(ExtractedPage(i + 1, text, used_ocr))
    return pages


def chunk_text(text: str, size: int, overlap: int) -> list[str]:
    """Split on whitespace into ~size-character windows that overlap, never cutting a word."""
    words = text.split()
    chunks, current, length = [], [], 0
    for word in words:
        if length + len(word) + 1 > size and current:
            chunks.append(" ".join(current))
            # carry the tail forward as overlap
            tail, tail_len = [], 0
            for w in reversed(current):
                if tail_len + len(w) + 1 > overlap:
                    break
                tail.insert(0, w)
                tail_len += len(w) + 1
            current, length = tail, tail_len
        current.append(word)
        length += len(word) + 1
    if current:
        chunks.append(" ".join(current))
    return chunks


def to_blob(vec: list[float]) -> bytes:
    arr = np.asarray(vec, dtype=np.float32)
    arr /= np.linalg.norm(arr) + 1e-12
    return arr.tobytes()


async def ingest_pdf(db: Database, llm: LLM, case_id: int, filename: str, pdf_bytes: bytes) -> dict:
    settings = get_settings()
    extracted = extract_pages(pdf_bytes, settings.ocr_enabled)

    totals: Counter = Counter()
    pages: list[tuple[int, str]] = []
    for p in extracted:
        clean, counts = redact(p.text)
        totals.update(counts)
        pages.append((p.page_no, clean.strip()))

    if not any(text for _, text in pages):
        raise ValueError("No readable text found in this PDF, even after OCR.")

    row = db.one("SELECT COALESCE(MAX(exhibit_no), 0) + 1 AS n FROM documents WHERE case_id = ?", (case_id,))
    exhibit_no = row["n"]
    cur = db.execute(
        "INSERT INTO documents (case_id, exhibit_no, filename, pages, ocr_pages, redactions, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (case_id, exhibit_no, filename, len(pages), sum(p.ocr for p in extracted), json.dumps(totals), now()),
    )
    doc_id = cur.lastrowid
    db.executemany("INSERT INTO pages (document_id, page_no, text) VALUES (?, ?, ?)", [(doc_id, n, t) for n, t in pages])

    chunk_rows = [
        (page_no, piece)
        for page_no, text in pages
        for piece in chunk_text(text, settings.chunk_size, settings.chunk_overlap)
    ]
    vectors: list[bytes | None] = [None] * len(chunk_rows)
    if llm.enabled and chunk_rows:
        vectors = [to_blob(v) for v in await llm.embed([t for _, t in chunk_rows])]
    db.executemany(
        "INSERT INTO chunks (case_id, document_id, page_no, text, embedding) VALUES (?, ?, ?, ?, ?)",
        [(case_id, doc_id, n, t, v) for (n, t), v in zip(chunk_rows, vectors)],
    )
    # A new document makes any cached chronology stale.
    db.execute("DELETE FROM events WHERE case_id = ?", (case_id,))
    db.audit(
        case_id,
        "document.uploaded",
        document_id=doc_id,
        filename=filename,
        pages=len(pages),
        ocr_pages=sum(p.ocr for p in extracted),
        redactions=dict(totals),
    )
    return {"id": doc_id, "exhibit_no": exhibit_no, "filename": filename, "pages": len(pages),
            "ocr_pages": sum(p.ocr for p in extracted), "redactions": dict(totals)}
