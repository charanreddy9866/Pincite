# 4. One container on Cloud Run, SQLite storage, one instance

**Status:** accepted for the demo; superseded when real case data is involved

## Context
The goal is a deployable, inexpensive demo that a reviewer can open with a link and that scales to zero when idle.

## Decision
The Next.js UI is statically exported and served by the FastAPI app, so there is one image and one Cloud Run service. Data lives in a SQLite file on the instance's local disk. The service is capped at one instance so every request sees the same database. Secrets (OpenAI key, access code) come from Secret Manager. An access code guards every API route.

## Consequences
- Deploying is one command (`deploy/cloudrun.sh`) and costs nothing when idle.
- Data is lost when the instance is recycled. For a demo with fictional data that's acceptable, even desirable: nothing lingers.
- For real use: Cloud SQL for PostgreSQL with pgvector for cases, chunks and audit; Cloud Storage (CMEK) for original PDFs; Identity-Aware Proxy or the firm's SSO instead of a shared code; per-matter access control; then lift the instance cap.
