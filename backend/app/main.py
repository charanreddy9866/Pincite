import csv
import io
import json
from pathlib import Path

import openai
from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .agent import answer_question
from .chronology import build_chronology, list_events
from .config import get_settings
from .db import Database, get_db, now
from .ingest import ingest_pdf
from .llm import LLM, get_llm

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "sample_data"
SAMPLE_CASE_NAME = "Rivera v. Northwind Appliance Co. (sample)"

settings = get_settings()
app = FastAPI(title="Pincite", version="1.0.0", description="Cited answers and chronologies from case documents.")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)


@app.middleware("http")
async def access_code_guard(request: Request, call_next):
    s = get_settings()
    path = request.url.path
    if s.access_code and path.startswith("/api/") and path != "/api/health" and request.method != "OPTIONS":
        if request.headers.get("x-access-code") != s.access_code:
            return JSONResponse({"detail": "Enter the access code to use this workspace."}, status_code=401)
    return await call_next(request)


# ---------- models ----------

class CaseIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class AskIn(BaseModel):
    question: str = Field(min_length=3, max_length=2000)


def _case_or_404(db: Database, case_id: int):
    row = db.one("SELECT * FROM cases WHERE id = ?", (case_id,))
    if row is None:
        raise HTTPException(404, "Case not found.")
    return row


def _documents(db: Database, case_id: int) -> list[dict]:
    rows = db.all(
        "SELECT id, exhibit_no, filename, pages, ocr_pages, redactions, created_at "
        "FROM documents WHERE case_id = ? ORDER BY exhibit_no",
        (case_id,),
    )
    return [dict(r, redactions=json.loads(r["redactions"])) for r in rows]


# ---------- routes ----------

@app.get("/api/health")
def health():
    s = get_settings()
    return {
        "status": "ok",
        "ai_enabled": s.llm_enabled,
        "provider": s.provider,
        "model": s.chat_model if s.llm_enabled else None,
        "access_code_required": bool(s.access_code),
    }


@app.exception_handler(openai.APIError)
async def ai_provider_error(request: Request, exc: openai.APIError):
    """Turn model-provider failures into messages a user can act on."""
    if isinstance(exc, openai.RateLimitError):
        status, msg = 429, ("The AI provider's usage limit was reached. Free tiers allow a limited number of "
                            "requests per day, so try again later.")
    elif isinstance(exc, (openai.AuthenticationError, openai.PermissionDeniedError)):
        status, msg = 502, "The AI provider rejected the API key configured on this server."
    elif isinstance(exc, openai.NotFoundError):
        status, msg = 502, f"The AI model '{get_settings().chat_model}' isn't available for this API key."
    else:
        status, msg = 502, "The AI provider returned an error. Try again in a moment."
    return JSONResponse({"detail": msg}, status_code=status)


@app.get("/api/cases")
def list_cases(db: Database = Depends(get_db)):
    rows = db.all(
        "SELECT c.id, c.name, c.created_at, COUNT(d.id) AS documents FROM cases c "
        "LEFT JOIN documents d ON d.case_id = c.id GROUP BY c.id ORDER BY c.id DESC"
    )
    return [dict(r) for r in rows]


@app.post("/api/cases", status_code=201)
def create_case(body: CaseIn, db: Database = Depends(get_db)):
    cur = db.execute("INSERT INTO cases (name, created_at) VALUES (?, ?)", (body.name.strip(), now()))
    db.audit(cur.lastrowid, "case.created", name=body.name.strip())
    return {"id": cur.lastrowid, "name": body.name.strip()}


@app.post("/api/cases/sample", status_code=201)
async def create_sample_case(db: Database = Depends(get_db), llm: LLM = Depends(get_llm)):
    cur = db.execute("INSERT INTO cases (name, created_at) VALUES (?, ?)", (SAMPLE_CASE_NAME, now()))
    case_id = cur.lastrowid
    db.audit(case_id, "case.created", name=SAMPLE_CASE_NAME, sample=True)
    for pdf in sorted(SAMPLE_DIR.glob("*.pdf")):
        await ingest_pdf(db, llm, case_id, pdf.name, pdf.read_bytes())
    return {"id": case_id, "name": SAMPLE_CASE_NAME}


@app.get("/api/cases/{case_id}")
def get_case(case_id: int, db: Database = Depends(get_db)):
    case = _case_or_404(db, case_id)
    return {**dict(case), "documents": _documents(db, case_id)}


@app.delete("/api/cases/{case_id}", status_code=204)
def delete_case(case_id: int, db: Database = Depends(get_db)):
    _case_or_404(db, case_id)
    db.execute("DELETE FROM cases WHERE id = ?", (case_id,))
    db.audit(None, "case.deleted", case_id=case_id)
    return Response(status_code=204)


@app.post("/api/cases/{case_id}/documents", status_code=201)
async def upload_document(
    case_id: int,
    file: UploadFile = File(...),
    db: Database = Depends(get_db),
    llm: LLM = Depends(get_llm),
):
    _case_or_404(db, case_id)
    name = file.filename or "document.pdf"
    if file.content_type != "application/pdf" and not name.lower().endswith(".pdf"):
        raise HTTPException(415, "Only PDF files can be added to a case.")
    data = await file.read()
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"{name} is larger than {settings.max_upload_mb} MB.")
    if not data.startswith(b"%PDF"):
        raise HTTPException(415, f"{name} isn't a valid PDF.")
    try:
        return await ingest_pdf(db, llm, case_id, name, data)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.get("/api/documents/{document_id}/pages/{page_no}")
def get_page(document_id: int, page_no: int, db: Database = Depends(get_db)):
    doc = db.one("SELECT id, case_id, exhibit_no, filename, pages FROM documents WHERE id = ?", (document_id,))
    if doc is None:
        raise HTTPException(404, "Document not found.")
    page = db.one("SELECT text FROM pages WHERE document_id = ? AND page_no = ?", (document_id, page_no))
    if page is None:
        raise HTTPException(404, "Page not found.")
    return {**dict(doc), "page_no": page_no, "text": page["text"]}


@app.post("/api/cases/{case_id}/ask")
async def ask(case_id: int, body: AskIn, db: Database = Depends(get_db), llm: LLM = Depends(get_llm)):
    _case_or_404(db, case_id)
    if not db.one("SELECT 1 FROM documents WHERE case_id = ?", (case_id,)):
        raise HTTPException(400, "Add at least one document to this case before asking questions.")
    result = await answer_question(db, llm, case_id, body.question.strip())
    db.audit(
        case_id,
        "question.asked",
        question=body.question.strip(),
        status=result["status"],
        citations=len(result["citations"]),
        verified=sum(c["verified"] for c in result["citations"]),
        searches=result["searches"],
    )
    return result


@app.post("/api/cases/{case_id}/chronology")
async def chronology_build(case_id: int, db: Database = Depends(get_db), llm: LLM = Depends(get_llm)):
    _case_or_404(db, case_id)
    summary = await build_chronology(db, llm, case_id)
    return {**summary, "items": list_events(db, case_id)}


@app.get("/api/cases/{case_id}/chronology")
def chronology_get(case_id: int, db: Database = Depends(get_db)):
    _case_or_404(db, case_id)
    return {"items": list_events(db, case_id)}


@app.get("/api/cases/{case_id}/chronology.csv")
def chronology_csv(case_id: int, db: Database = Depends(get_db)):
    case = _case_or_404(db, case_id)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Date", "Precision", "Event", "Exhibit", "File", "Page", "Quote"])
    for e in list_events(db, case_id):
        writer.writerow([e["date"], e["precision"], e["description"], e["exhibit_no"], e["filename"], e["page_no"], e["quote"]])
    db.audit(case_id, "chronology.exported")
    safe = "".join(ch if ch.isalnum() else "_" for ch in case["name"])[:60]
    return Response(
        buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{safe}_chronology.csv"'},
    )


@app.get("/api/cases/{case_id}/activity")
def activity(case_id: int, db: Database = Depends(get_db)):
    _case_or_404(db, case_id)
    rows = db.all("SELECT ts, action, detail FROM audit WHERE case_id = ? ORDER BY id DESC LIMIT 200", (case_id,))
    return [{"ts": r["ts"], "action": r["action"], "detail": json.loads(r["detail"])} for r in rows]


# ---------- static frontend (single-container deploys) ----------

if settings.static_dir.is_dir():
    app.mount("/_next", StaticFiles(directory=settings.static_dir / "_next"), name="next-assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        candidate = (settings.static_dir / path).resolve()
        if path and candidate.is_file() and settings.static_dir.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(settings.static_dir / "index.html")
