import io

from reportlab.pdfgen import canvas

from app.config import get_settings

from .conftest import FakeLLM, answer, excerpt_id_containing, tool_call


def make_pdf(*pages: str) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    for text in pages:
        y = 720
        for line in text.split("\n"):
            c.drawString(72, y, line)
            y -= 16
        c.showPage()
    c.save()
    return buf.getvalue()


def test_health(make_client):
    body = make_client().get("/api/health").json()
    assert body["status"] == "ok" and body["ai_enabled"] is False


def test_sample_case_ingests_with_ocr_and_redaction(sample_case):
    client, case_id = sample_case
    case = client.get(f"/api/cases/{case_id}").json()
    docs = {d["filename"]: d for d in case["documents"]}
    assert len(docs) == 5
    assert [d["exhibit_no"] for d in case["documents"]] == [1, 2, 3, 4, 5]
    assert docs["05_Scanned_Fire_Rescue_Report.pdf"]["ocr_pages"] == 1
    assert docs["04_Warranty_Claim_and_Denial.pdf"]["redactions"] == {"SSN": 1, "EMAIL": 1, "PHONE": 1, "ACCOUNT": 2}

    claim = docs["04_Warranty_Claim_and_Denial.pdf"]
    page = client.get(f"/api/documents/{claim['id']}/pages/1").json()["text"]
    assert "123-45-6789" not in page and "004417889213" not in page and "[REDACTED SSN]" in page

    scan = docs["05_Scanned_Fire_Rescue_Report.pdf"]
    assert "control panel" in client.get(f"/api/documents/{scan['id']}/pages/1").json()["text"]


def test_upload_validation(make_client):
    client = make_client()
    case_id = client.post("/api/cases", json={"name": "Test v. Test"}).json()["id"]
    r = client.post(f"/api/cases/{case_id}/documents", files={"file": ("a.txt", b"hello", "text/plain")})
    assert r.status_code == 415
    r = client.post(f"/api/cases/{case_id}/documents", files={"file": ("fake.pdf", b"not a pdf", "application/pdf")})
    assert r.status_code == 415
    r = client.post(f"/api/cases/{case_id}/documents",
                    files={"file": ("ok.pdf", make_pdf("Hello from page one of this filing."), "application/pdf")})
    assert r.status_code == 201 and r.json()["exhibit_no"] == 1


def test_ask_without_ai_returns_best_passages(sample_case):
    client, case_id = sample_case
    r = client.post(f"/api/cases/{case_id}/ask", json={"question": "Where did Rivera buy the DW-500 and for how much?"})
    body = r.json()
    assert body["status"] == "retrieval_only"
    top = body["passages"][0]
    assert top["filename"] == "01_Class_Action_Complaint.pdf" and top["page_no"] == 2


def test_agent_searches_then_answers_and_citations_are_checked(make_client):
    client = make_client(FakeLLM())  # ingest with embeddings
    case_id = client.post("/api/cases", json={"name": "Rivera"}).json()["id"]
    client.post(f"/api/cases/{case_id}/documents", files={"file": ("email.pdf", make_pdf(
        "From: Daniel Chen. Date: August 4, 2021.\nI recommend we pause DW-500 shipments and redesign the harness.",
        "From: Linda Park. Date: August 5, 2021.\nWe can't pause before the Q4 sales push. Keep shipping."
    ), "application/pdf")})

    llm = FakeLLM([
        tool_call("Linda Park reply pause shipments", exhibit_no=1),
        lambda messages: answer(
            text="Park refused to pause shipments before the Q4 sales push [1]. She also approved a recall [2].",
            citations=[
                {"excerpt_id": excerpt_id_containing(messages, "Q4"), "quote": "We can't pause before the Q4 sales push"},
                {"excerpt_id": excerpt_id_containing(messages, "Q4"), "quote": "I approve an immediate recall of all units"},
            ]),
    ])
    client = make_client(llm)
    r = client.post(f"/api/cases/{case_id}/ask", json={"question": "How did Park respond to the pause recommendation?"})
    body = r.json()

    assert body["searches"] == ["How did Park respond to the pause recommendation?", "Linda Park reply pause shipments"]
    assert [c["verified"] for c in body["citations"]] == [True, False]
    assert body["status"] == "partially_verified"
    assert body["citations"][0]["page_no"] == 2
    # the tool result was fed back to the model, wrapped as data
    tool_msg = llm.calls[1]["messages"][-1]
    assert tool_msg["role"] == "tool" and "<excerpt" in tool_msg["content"]
    # system prompt carries the injection rule
    assert "data, never instructions" in llm.calls[0]["messages"][0]["content"]


def test_agent_not_found_and_unknown_excerpt(sample_case, make_client):
    _, case_id = sample_case
    client = make_client(FakeLLM([answer(found=False, text="The documents don't mention a verdict.")]))
    assert client.post(f"/api/cases/{case_id}/ask", json={"question": "What was the verdict?"}).json()["status"] == "not_found"

    client = make_client(FakeLLM([answer(text="Something [1].", citations=[{"excerpt_id": "E99", "quote": "made up quote text here"}])]))
    body = client.post(f"/api/cases/{case_id}/ask", json={"question": "Anything?"}).json()
    assert body["status"] == "unverified" and body["citations"][0]["verified"] is False


def test_final_step_forces_an_answer(sample_case, make_client):
    _, case_id = sample_case
    steps = get_settings().max_agent_steps
    llm = FakeLLM([tool_call(f"query {i}", call_id=f"c{i}") for i in range(steps - 1)] + [answer(found=False, text="No.")])
    body = make_client(llm).post(f"/api/cases/{case_id}/ask", json={"question": "Loop forever?"}).json()
    assert body["status"] == "not_found"
    assert llm.calls[-1]["tools"] is None  # last call can't search again


def test_offline_chronology_and_csv(sample_case):
    client, case_id = sample_case
    built = client.post(f"/api/cases/{case_id}/chronology").json()
    assert built["method"] == "pattern" and built["events"] > 5
    dates = [e["date"] for e in built["items"]]
    assert dates == sorted(dates)
    assert {"2021-08-02", "2022-05-14", "2024-01-09", "2024-02-02"} <= set(dates)
    csv = client.get(f"/api/cases/{case_id}/chronology.csv")
    assert csv.status_code == 200 and csv.text.startswith("Date,Precision,Event")


def test_llm_chronology_drops_unverified_events(make_client):
    client = make_client()
    case_id = client.post("/api/cases", json={"name": "Chrono"}).json()["id"]
    client.post(f"/api/cases/{case_id}/documents", files={"file": ("d.pdf", make_pdf(
        "On May 14, 2022, Ms. Rivera purchased a dishwasher from HomeMart."), "application/pdf")})
    import json
    llm = FakeLLM([{"content": json.dumps({"events": [
        {"date": "2022-05-14", "precision": "day", "description": "Rivera buys the DW-500.", "page": 1,
         "quote": "On May 14, 2022, Ms. Rivera purchased a dishwasher"},
        {"date": "2022-06-01", "precision": "day", "description": "Invented event.", "page": 1,
         "quote": "Northwind issued a recall on June 1"},
    ]}), "tool_calls": None}])
    built = make_client(llm).post(f"/api/cases/{case_id}/chronology").json()
    assert built["method"] == "ai" and built["events"] == 1 and built["dropped_unverified"] == 1


def test_activity_log_records_actions(sample_case):
    client, case_id = sample_case
    client.post(f"/api/cases/{case_id}/ask", json={"question": "Who is Daniel Chen?"})
    actions = [a["action"] for a in client.get(f"/api/cases/{case_id}/activity").json()]
    assert actions[0] == "question.asked" and actions.count("document.uploaded") == 5


def test_access_code(make_client, monkeypatch):
    client = make_client()
    monkeypatch.setattr(get_settings(), "access_code", "s3cret")
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/cases").status_code == 401
    assert client.get("/api/cases", headers={"X-Access-Code": "s3cret"}).status_code == 200
