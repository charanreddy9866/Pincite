"""Model access behind a small interface, so the provider can be swapped (or faked in tests)."""

import copy
import json
import re
from typing import Any, Protocol

from openai import AsyncOpenAI, BadRequestError

from .config import get_settings


class LLM(Protocol):
    enabled: bool
    embeddings_enabled: bool

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


def loosen_schema(schema: dict) -> dict:
    """Make a strict OpenAI schema acceptable to providers with a smaller JSON Schema subset.

    Drops `strict`, and turns nullable unions like ["integer", "null"] into an optional field.
    """
    schema = copy.deepcopy(schema)

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            node.pop("strict", None)
            props = node.get("properties")
            if isinstance(props, dict):
                for name, prop in props.items():
                    t = prop.get("type") if isinstance(prop, dict) else None
                    if isinstance(t, list) and "null" in t:
                        prop["type"] = next(x for x in t if x != "null")
                        if name in node.get("required", []):
                            node["required"] = [r for r in node["required"] if r != name]
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(schema)
    return schema


def extract_json(text: str | None) -> str | None:
    """Strip Markdown code fences some models wrap around JSON."""
    if text is None:
        return None
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    return m.group(1).strip() if m else text.strip()


class OpenAICompatibleLLM:
    """OpenAI, or any provider with an OpenAI-compatible API (Google Gemini)."""

    def __init__(self, api_key: str, chat_model: str, embedding_model: str, *, base_url: str | None = None,
                 strict: bool = True, embeddings_enabled: bool = True) -> None:
        self.enabled = True
        self.embeddings_enabled = embeddings_enabled
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self._chat_model = chat_model
        self._embedding_model = embedding_model
        self._strict = strict

    async def embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for i in range(0, len(texts), 96):
            resp = await self._client.embeddings.create(model=self._embedding_model, input=texts[i : i + 96])
            out.extend(d.embedding for d in resp.data)
        return out

    async def chat(self, messages, *, tools=None, schema=None, schema_name="result"):
        kwargs: dict[str, Any] = {"model": self._chat_model, "messages": messages, "temperature": 0}
        if tools:
            kwargs["tools"] = tools if self._strict else [loosen_schema(t) for t in tools]
        if schema:
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": schema_name,
                    "schema": schema if self._strict else loosen_schema(schema),
                    **({"strict": True} if self._strict else {}),
                },
            }
        try:
            resp = await self._client.chat.completions.create(**kwargs)
        except BadRequestError:
            if not schema:
                raise
            # Fallback for providers that reject this schema: plain JSON mode, schema stated in the prompt.
            kwargs["response_format"] = {"type": "json_object"}
            kwargs["messages"] = [
                *messages,
                {"role": "system", "content": "Reply with only a JSON object matching this JSON Schema:\n"
                 + json.dumps(schema)},
            ]
            resp = await self._client.chat.completions.create(**kwargs)

        msg = resp.choices[0].message
        tool_calls = None
        if msg.tool_calls:
            tool_calls = [
                {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in msg.tool_calls
            ]
        return {"content": extract_json(msg.content), "tool_calls": tool_calls}


class DisabledLLM:
    """Used when no API key is configured. Callers check `enabled` and fall back to offline paths."""

    enabled = False
    embeddings_enabled = False

    async def embed(self, texts):
        raise RuntimeError("LLM disabled")

    async def chat(self, messages, **kwargs):
        raise RuntimeError("LLM disabled")


_llm: LLM | None = None


def get_llm() -> LLM:
    global _llm
    if _llm is None:
        s = get_settings()
        if s.llm_enabled:
            _llm = OpenAICompatibleLLM(
                s.api_key, s.chat_model, s.embedding_model,
                base_url=s.base_url,
                strict=s.provider == "openai",
                embeddings_enabled=s.embeddings_enabled,
            )
        else:
            _llm = DisabledLLM()
    return _llm
