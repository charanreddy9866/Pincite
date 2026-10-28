# 5. Tests run without a model; quality is measured with evals

**Status:** accepted

## Context
Tests that call a live model are slow, cost money, need a secret in CI and give different results run to run. But the parts most likely to break (tool-call handling, citation checks, redaction, retrieval) are deterministic code.

## Decision
- Model access sits behind a small `LLM` interface. Tests use a scripted fake that returns tool calls and structured answers, including deliberately fabricated citations, and checks the app's reaction (status, struck citations, forced final answer after the step limit).
- Without an API key the app still runs: search returns passages, chronologies use a deterministic date extractor, and nothing calls a model.
- Answer quality is measured separately by `evals/run.py --mode full` against 19 golden questions on the sample case: answerable, unanswerable, a planted prompt injection, and a privacy probe. It reports pass rate, groundedness (share of citations verified) and correct refusals.

## Consequences
- CI is fast, free and deterministic.
- Model regressions (a new model version, a prompt change) are caught by running the full eval before shipping, not by unit tests.
