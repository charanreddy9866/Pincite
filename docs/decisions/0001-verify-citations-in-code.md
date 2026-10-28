# 1. Citations are verified by application code, not trusted from the model

**Status:** accepted

## Context
Attorneys can't use an answer they can't trace to the record, and language models sometimes paraphrase or invent quotes while sounding confident. Asking the model to "be accurate" doesn't change that.

## Decision
The model must return structured output (strict JSON schema): an answer, a `found_in_documents` flag, and citations that each name an excerpt id and a verbatim quote. The application then looks up the stored text of the cited page and checks that the quote appears there (case- and whitespace-insensitive, smart quotes normalized, `...` allowed for elisions, transcript line numbers tolerated).

Each answer gets a status: `verified`, `partially_verified`, `unverified`, or `not_found`. Unverified citations stay visible but struck through, so the user sees exactly what failed instead of a silently cleaned-up answer. The same check filters AI-extracted chronology events, which are dropped and counted when their quote isn't found.

## Consequences
- A wrong citation is caught before a person relies on it.
- Quotes that are correct but reworded (the model fixing a typo, say) fail too. That's the right trade-off in legal work, and the prompt asks for word-for-word quotes.
- The check proves the quote exists, not that it supports the sentence it's attached to. The page viewer highlights the quote in context so a person can judge that.
- Transcript line numbers broke early matching for quotes spanning two lines. The verifier retries with leading line numbers stripped (found while testing the sample deposition).
