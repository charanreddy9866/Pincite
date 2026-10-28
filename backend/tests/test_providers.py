import asyncio
import json
from types import SimpleNamespace

import httpx
import openai

from app.agent import ANSWER_SCHEMA, SEARCH_TOOL
from app.config import GEMINI_BASE_URL, Settings
from app.llm import OpenAICompatibleLLM, extract_json, loosen_schema

from .conftest import FakeLLM


def _response(status: int) -> httpx.Response:
    return httpx.Response(status, request=httpx.Request("POST", "https://example.test/v1/chat/completions"))


def test_provider_selection(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "g-key")
    s = Settings()
    assert (s.provider, s.base_url, s.embeddings_enabled) == ("gemini", GEMINI_BASE_URL, False)
    assert s.llm_enabled

    monkeypatch.setenv("OPENAI_API_KEY", "sk-key")  # OpenAI wins when both are set
    s = Settings()
    assert (s.provider, s.base_url, s.embeddings_enabled) == ("openai", None, True)

    monkeypatch.delenv("OPENAI_API_KEY")
    monkeypatch.delenv("GEMINI_API_KEY")
    assert Settings().llm_enabled is False


def test_loosen_schema_for_gemini():
    tool = loosen_schema(SEARCH_TOOL)
    params = tool["function"]["parameters"]
    assert "strict" not in tool["function"]
    assert params["properties"]["exhibit_no"]["type"] == "integer"
    assert params["required"] == ["query"]
    assert SEARCH_TOOL["function"]["strict"] is True  # original untouched
    assert loosen_schema(ANSWER_SCHEMA)["required"] == ANSWER_SCHEMA["required"]


def test_extract_json_strips_fences():
    assert extract_json('```json\n{"a": 1}\n```') == '{"a": 1}'
    assert extract_json(' {"a": 1} ') == '{"a": 1}'
    assert extract_json(None) is None


def test_falls_back_to_json_mode_when_schema_rejected():
    llm = OpenAICompatibleLLM("k", "gemini-x", "e", base_url=GEMINI_BASE_URL, strict=False, embeddings_enabled=False)
    calls = []

    async def create(**kwargs):
        calls.append(kwargs)
        if kwargs["response_format"]["type"] == "json_schema":
            raise openai.BadRequestError("schema not supported", response=_response(400), body=None)
        content = '```json\n{"found_in_documents": false, "answer": "No.", "citations": []}\n```'
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content, tool_calls=None))])

    llm._client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    msg = asyncio.run(llm.chat([{"role": "user", "content": "q"}], schema=ANSWER_SCHEMA))
    assert json.loads(msg["content"])["answer"] == "No."
    assert [c["response_format"]["type"] for c in calls] == ["json_schema", "json_object"]
    assert "JSON Schema" in calls[1]["messages"][-1]["content"]


def test_rate_limit_becomes_a_clear_429(sample_case, make_client):
    _, case_id = sample_case

    def limited(messages):
        raise openai.RateLimitError("quota", response=_response(429), body=None)

    r = make_client(FakeLLM([limited])).post(f"/api/cases/{case_id}/ask", json={"question": "Who is Daniel Chen?"})
    assert r.status_code == 429
    assert "usage limit" in r.json()["detail"]
