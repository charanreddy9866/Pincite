import hashlib
import json

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.db import Database, get_db
from app.llm import DisabledLLM, get_llm
from app.main import app
from app.search import tokenize


class FakeLLM:
    """Scripted stand-in for the model.

    `script` is a list of assistant messages returned in order by chat(). Embeddings are
    deterministic hashed bag-of-words vectors, so the semantic search path is exercised too.
    """

    enabled = True

    def __init__(self, script: list[dict] | None = None) -> None:
        self.script = list(script or [])
        self.calls: list[dict] = []

    async def embed(self, texts):
        out = []
        for t in texts:
            v = np.zeros(64, dtype=np.float32)
            for tok in tokenize(t):
                v[int(hashlib.md5(tok.encode()).hexdigest(), 16) % 64] += 1
            out.append((v + 0.01).tolist())
        return out

    async def chat(self, messages, *, tools=None, schema=None, schema_name="result"):
        self.calls.append({"messages": messages, "tools": tools, "schema_name": schema_name})
        if not self.script:
            raise AssertionError("FakeLLM script exhausted")
        step = self.script.pop(0)
        return step(messages) if callable(step) else step


def answer(found=True, text="", citations=()):
    return {"content": json.dumps({"found_in_documents": found, "answer": text, "citations": list(citations)}),
            "tool_calls": None}


def excerpt_id_containing(messages, needle: str) -> str:
    """Find the id the app assigned to the excerpt containing `needle` (ids depend on ranking)."""
    import re

    for m in messages:
        for eid, body in re.findall(r'<excerpt id="(E\d+)"[^>]*>(.*?)</excerpt>', m.get("content") or "", re.S):
            if needle in body:
                return eid
    raise AssertionError(f"no excerpt contains {needle!r}")


def tool_call(query, exhibit_no=None, call_id="call_1"):
    return {
        "content": None,
        "tool_calls": [{"id": call_id, "type": "function",
                        "function": {"name": "search_documents",
                                     "arguments": json.dumps({"query": query, "exhibit_no": exhibit_no})}}],
    }


@pytest.fixture
def db():
    return Database(":memory:")


@pytest.fixture
def make_client(db):
    def _make(llm=None):
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[get_llm] = lambda: (llm or DisabledLLM())
        return TestClient(app)

    yield _make
    app.dependency_overrides.clear()


@pytest.fixture
def sample_case(make_client):
    """Loads the sample case offline (no embeddings) and returns (client, case_id)."""
    client = make_client()
    r = client.post("/api/cases/sample")
    assert r.status_code == 201, r.text
    return client, r.json()["id"]
