"""Model access behind a small interface, so the provider can be swapped (or faked in tests)."""

from typing import Any, Protocol

from openai import AsyncOpenAI

from .config import get_settings


class LLM(Protocol):
    enabled: bool

    async def embed(self, texts: list[str]) -> list[list[float]]: ...

    async def chat(
        self,
        messages: list[dict],
        *,
        tools: list[dict] | None = None,
        schema: dict | None = None,
        schema_name: str = "result",
    ) -> dict[str, Any]:
        """Return the assistant message as a dict: {"content": str|None, "tool_calls": [...]|None}."""
        ...


class OpenAILLM:
    def __init__(self, api_key: str, chat_model: str, embedding_model: str) -> None:
        self.enabled = True
        self._client = AsyncOpenAI(api_key=api_key)
        self._chat_model = chat_model
        self._embedding_model = embedding_model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for i in range(0, len(texts), 96):
            resp = await self._client.embeddings.create(model=self._embedding_model, input=texts[i : i + 96])
            out.extend(d.embedding for d in resp.data)
        return out

    async def chat(self, messages, *, tools=None, schema=None, schema_name="result"):
        kwargs: dict[str, Any] = {"model": self._chat_model, "messages": messages, "temperature": 0}
        if tools:
            kwargs["tools"] = tools
        if schema:
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": schema_name, "schema": schema, "strict": True},
            }
        resp = await self._client.chat.completions.create(**kwargs)
        msg = resp.choices[0].message
        tool_calls = None
        if msg.tool_calls:
            tool_calls = [
                {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in msg.tool_calls
            ]
        return {"content": msg.content, "tool_calls": tool_calls}


class DisabledLLM:
    """Used when no API key is configured. Callers check `enabled` and fall back to offline paths."""

    enabled = False

    async def embed(self, texts):
        raise RuntimeError("LLM disabled")

    async def chat(self, messages, **kwargs):
        raise RuntimeError("LLM disabled")


_llm: LLM | None = None


def get_llm() -> LLM:
    global _llm
    if _llm is None:
        s = get_settings()
        _llm = OpenAILLM(s.openai_api_key, s.chat_model, s.embedding_model) if s.llm_enabled else DisabledLLM()
    return _llm
