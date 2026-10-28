"""Hybrid retrieval: BM25 keyword search fused with embedding similarity.

Legal documents are full of exact tokens (case numbers, exhibit names, model numbers, defined terms)
that embeddings blur, while paraphrased questions need semantic matching. Reciprocal rank fusion
combines both without having to tune score scales. BM25 alone still works with no API key.
"""

import math
import re
from collections import Counter
from dataclasses import dataclass

import numpy as np

from .db import Database
from .llm import LLM

_TOKEN = re.compile(r"[a-z0-9]+(?:[.'-][a-z0-9]+)*")
_STOP = set(
    "a an the of and or to in on for by with at from as is are was were be been it its this that these those "
    "did does do what when who whom which how why where any all not no did has have had i you he she they we "
    "about into than then there their our your his her them".split()
)


def tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in _STOP]


@dataclass
class Hit:
    chunk_id: int
    document_id: int
    exhibit_no: int
    filename: str
    page_no: int
    text: str
    score: float


class BM25:
    def __init__(self, docs: list[list[str]], k1: float = 1.5, b: float = 0.75) -> None:
        self.docs = docs
        self.k1, self.b = k1, b
        self.avgdl = sum(map(len, docs)) / max(len(docs), 1)
        df: Counter = Counter()
        for d in docs:
            df.update(set(d))
        n = len(docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}
        self.tf = [Counter(d) for d in docs]

    def scores(self, query: list[str]) -> list[float]:
        out = []
        for tf, d in zip(self.tf, self.docs):
            s = 0.0
            for t in query:
                if t in tf:
                    f = tf[t]
                    s += self.idf[t] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * len(d) / self.avgdl))
            out.append(s)
        return out


def _rank(scores: list[float]) -> dict[int, int]:
    order = sorted((i for i, s in enumerate(scores) if s > 0), key=lambda i: -scores[i])
    return {i: r for r, i in enumerate(order)}


async def search(
    db: Database,
    llm: LLM,
    case_id: int,
    query: str,
    top_k: int = 6,
    document_id: int | None = None,
) -> list[Hit]:
    sql = (
        "SELECT c.id, c.document_id, c.page_no, c.text, c.embedding, d.exhibit_no, d.filename "
        "FROM chunks c JOIN documents d ON d.id = c.document_id WHERE c.case_id = ?"
    )
    params: list = [case_id]
    if document_id is not None:
        sql += " AND c.document_id = ?"
        params.append(document_id)
    rows = db.all(sql, params)
    if not rows:
        return []

    keyword_rank = _rank(BM25([tokenize(r["text"]) for r in rows]).scores(tokenize(query)))

    semantic_rank: dict[int, int] = {}
    if llm.enabled and all(r["embedding"] is not None for r in rows):
        [qv] = await llm.embed([query])
        q = np.asarray(qv, dtype=np.float32)
        q /= np.linalg.norm(q) + 1e-12
        matrix = np.stack([np.frombuffer(r["embedding"], dtype=np.float32) for r in rows])
        semantic_rank = _rank(list(matrix @ q + 1.0))  # shift so every score is positive

    k = 60  # standard RRF constant
    fused: dict[int, float] = {}
    for ranks in (keyword_rank, semantic_rank):
        for i, r in ranks.items():
            fused[i] = fused.get(i, 0.0) + 1.0 / (k + r + 1)

    best = sorted(fused, key=lambda i: -fused[i])[:top_k]
    return [
        Hit(
            chunk_id=rows[i]["id"],
            document_id=rows[i]["document_id"],
            exhibit_no=rows[i]["exhibit_no"],
            filename=rows[i]["filename"],
            page_no=rows[i]["page_no"],
            text=rows[i]["text"],
            score=round(fused[i], 5),
        )
        for i in best
    ]
