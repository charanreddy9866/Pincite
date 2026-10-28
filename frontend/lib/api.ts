const BASE = (process.env.NEXT_PUBLIC_API_URL || "").replace(/\/$/, "");
const CODE_KEY = "pincite:access-code";

export type Health = { status: string; ai_enabled: boolean; model: string | null; access_code_required: boolean };
export type CaseSummary = { id: number; name: string; created_at: string; documents: number };
export type Redactions = Partial<Record<"SSN" | "CARD" | "ACCOUNT" | "PHONE" | "EMAIL", number>>;
export type Doc = {
  id: number;
  exhibit_no: number;
  filename: string;
  pages: number;
  ocr_pages: number;
  redactions: Redactions;
  created_at: string;
};
export type CaseDetail = { id: number; name: string; created_at: string; documents: Doc[] };
export type Citation = {
  n: number;
  quote: string;
  verified: boolean;
  document_id: number | null;
  exhibit_no: number | null;
  filename: string | null;
  page_no: number | null;
};
export type Passage = { document_id: number; exhibit_no: number; filename: string; page_no: number; text: string };
export type AnswerStatus =
  | "verified"
  | "partially_verified"
  | "unverified"
  | "not_found"
  | "retrieval_only"
  | "error";
export type Answer = {
  question: string;
  status: AnswerStatus;
  answer: string;
  citations: Citation[];
  passages: Passage[];
  searches: string[];
};
export type ChronoEvent = {
  id: number;
  date: string;
  precision: "day" | "month" | "year";
  description: string;
  document_id: number;
  exhibit_no: number;
  filename: string;
  page_no: number;
  quote: string;
  method: "ai" | "pattern";
};
export type ChronoBuild = { events: number; dropped_unverified: number; method: "ai" | "pattern"; items: ChronoEvent[] };
export type Page = { id: number; exhibit_no: number; filename: string; pages: number; page_no: number; text: string };
export type Activity = { ts: string; action: string; detail: Record<string, unknown> };

export class ApiError extends Error {
  constructor(message: string, public status: number) {
    super(message);
  }
}

export function getAccessCode(): string {
  try {
    return localStorage.getItem(CODE_KEY) || "";
  } catch {
    return "";
  }
}

export function setAccessCode(code: string) {
  try {
    localStorage.setItem(CODE_KEY, code);
  } catch {}
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const code = getAccessCode();
  if (code) headers.set("X-Access-Code", code);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");

  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, { ...init, headers });
  } catch {
    throw new ApiError("Can't reach the Pincite server. Check your connection and try again.", 0);
  }
  if (!res.ok) {
    let msg = `The server returned an error (${res.status}).`;
    try {
      const body = await res.json();
      if (typeof body.detail === "string") msg = body.detail;
    } catch {}
    throw new ApiError(msg, res.status);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const api = {
  health: () => request<Health>("/api/health"),
  cases: () => request<CaseSummary[]>("/api/cases"),
  createCase: (name: string) => request<{ id: number }>("/api/cases", { method: "POST", body: JSON.stringify({ name }) }),
  createSample: () => request<{ id: number }>("/api/cases/sample", { method: "POST" }),
  getCase: (id: number) => request<CaseDetail>(`/api/cases/${id}`),
  deleteCase: (id: number) => request<void>(`/api/cases/${id}`, { method: "DELETE" }),
  upload: (caseId: number, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<Doc>(`/api/cases/${caseId}/documents`, { method: "POST", body: form });
  },
  page: (docId: number, page: number) => request<Page>(`/api/documents/${docId}/pages/${page}`),
  ask: (caseId: number, question: string) =>
    request<Answer>(`/api/cases/${caseId}/ask`, { method: "POST", body: JSON.stringify({ question }) }),
  chronology: (caseId: number) => request<{ items: ChronoEvent[] }>(`/api/cases/${caseId}/chronology`),
  buildChronology: (caseId: number) => request<ChronoBuild>(`/api/cases/${caseId}/chronology`, { method: "POST" }),
  activity: (caseId: number) => request<Activity[]>(`/api/cases/${caseId}/activity`),
};

/** CSV download goes through fetch so the access-code header is sent. */
export async function downloadChronologyCsv(caseId: number, caseName: string) {
  const headers: HeadersInit = getAccessCode() ? { "X-Access-Code": getAccessCode() } : {};
  const res = await fetch(`${BASE}/api/cases/${caseId}/chronology.csv`, { headers });
  if (!res.ok) throw new ApiError("Couldn't export the chronology.", res.status);
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = `${caseName.replace(/[^\w]+/g, "_").slice(0, 60)}_chronology.csv`;
  a.click();
  URL.revokeObjectURL(url);
}
