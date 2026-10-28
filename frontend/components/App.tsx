"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiError, setAccessCode, type CaseDetail, type CaseSummary, type Health } from "@/lib/api";
import ActivityPanel from "./ActivityPanel";
import AskPanel, { type Entry } from "./AskPanel";
import ChronologyPanel from "./ChronologyPanel";
import DocumentsPanel from "./DocumentsPanel";
import PageViewer, { type ViewerTarget } from "./PageViewer";
import { Spinner } from "./ui";

type Tab = "ask" | "chronology" | "documents" | "activity";
const TABS: [Tab, string][] = [
  ["ask", "Ask"],
  ["chronology", "Chronology"],
  ["documents", "Documents"],
  ["activity", "Activity"],
];

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [locked, setLocked] = useState(false);
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [kase, setKase] = useState<CaseDetail | null>(null);
  const [tab, setTab] = useState<Tab>("ask");
  const [viewer, setViewer] = useState<ViewerTarget | null>(null);
  const [entries, setEntries] = useState<Record<number, Entry[]>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [navOpen, setNavOpen] = useState(false);

  const loadCases = useCallback(async () => {
    try {
      setCases(await api.cases());
      setLocked(false);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) setLocked(true);
      else setError(err instanceof ApiError ? err.message : "Couldn't load cases.");
    }
  }, []);

  const openCase = useCallback(async (id: number, nextTab?: Tab) => {
    try {
      const detail = await api.getCase(id);
      setKase(detail);
      if (nextTab) setTab(nextTab);
      setViewer(null);
      setNavOpen(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't open that case.");
    }
  }, []);

  useEffect(() => {
    api
      .health()
      .then(setHealth)
      .catch(() => setError("Can't reach the Pincite server."));
    // Loading the case list on mount is a subscription to the server, not derived state.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadCases();
  }, [loadCases]);

  async function run(label: string, fn: () => Promise<void>) {
    setBusy(label);
    setError(null);
    try {
      await fn();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setBusy(null);
    }
  }

  const loadSample = () =>
    run("sample", async () => {
      const { id } = await api.createSample();
      await loadCases();
      await openCase(id, "ask");
    });

  const newCase = () => {
    const name = window.prompt("Case name", "Smith v. Acme Corp.");
    if (!name?.trim()) return;
    run("new", async () => {
      const { id } = await api.createCase(name.trim());
      await loadCases();
      await openCase(id, "documents");
    });
  };

  const removeCase = () => {
    if (!kase || !window.confirm(`Delete "${kase.name}" and all its documents? This can't be undone.`)) return;
    run("delete", async () => {
      await api.deleteCase(kase.id);
      setKase(null);
      await loadCases();
    });
  };

  if (locked) return <AccessGate onUnlock={loadCases} />;

  return (
    <div className="flex h-dvh">
      {/* Case list */}
      <nav
        className={`${navOpen ? "fixed inset-0 z-30 flex" : "hidden"} w-full flex-col border-r border-line bg-surface md:static md:flex md:w-64 md:shrink-0`}
        aria-label="Cases"
      >
        <div className="flex items-center justify-between px-5 pt-5 pb-4">
          <Wordmark />
          <button className="text-sm text-muted md:hidden" onClick={() => setNavOpen(false)}>
            Close
          </button>
        </div>
        <div className="flex gap-2 px-4">
          <button
            onClick={newCase}
            disabled={!!busy}
            className="h-9 flex-1 rounded-lg bg-brand text-sm font-semibold text-brand-ink disabled:opacity-50"
          >
            New case
          </button>
        </div>
        <ul className="mt-4 flex-1 overflow-y-auto px-2">
          {cases.map((c) => (
            <li key={c.id}>
              <button
                onClick={() => openCase(c.id)}
                aria-current={kase?.id === c.id ? "page" : undefined}
                className={`w-full rounded-lg px-3 py-2.5 text-left ${kase?.id === c.id ? "bg-brand-soft" : "hover:bg-sunken"}`}
              >
                <span className={`block truncate text-sm ${kase?.id === c.id ? "font-semibold text-brand" : "font-medium"}`}>
                  {c.name}
                </span>
                <span className="text-xs text-muted">
                  {c.documents} {c.documents === 1 ? "document" : "documents"}
                </span>
              </button>
            </li>
          ))}
        </ul>
        <div className="border-t border-line px-5 py-3 text-xs text-muted">
          {health ? (
            health.ai_enabled ? (
              <>AI answers on ({health.model})</>
            ) : (
              <>AI answers off. Search, OCR and redaction still work.</>
            )
          ) : (
            "Connecting…"
          )}
        </div>
      </nav>

      {/* Main */}
      <main className="flex min-w-0 flex-1 flex-col">
        <div className="flex items-center gap-3 border-b border-line px-4 py-3 md:hidden">
          <button onClick={() => setNavOpen(true)} className="rounded-md border border-line px-2.5 py-1 text-sm">
            Cases
          </button>
          <Wordmark />
        </div>

        {error && (
          <p role="alert" className="border-b border-line bg-danger-soft px-6 py-2 text-sm text-danger">
            {error}
          </p>
        )}

        {kase ? (
          <>
            <header className="border-b border-line px-6 pt-6">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <h1 className="font-serif text-[1.75rem] leading-tight font-semibold">{kase.name}</h1>
                  <p className="mt-1 text-sm text-muted">
                    {kase.documents.length} {kase.documents.length === 1 ? "exhibit" : "exhibits"},{" "}
                    {kase.documents.reduce((n, d) => n + d.pages, 0)} pages
                  </p>
                </div>
                <button onClick={removeCase} className="text-sm text-muted hover:text-danger">
                  Delete case
                </button>
              </div>
              <div role="tablist" className="mt-5 flex gap-1 overflow-x-auto">
                {TABS.map(([id, label]) => (
                  <button
                    key={id}
                    role="tab"
                    aria-selected={tab === id}
                    onClick={() => setTab(id)}
                    className={`-mb-px border-b-2 px-3 pb-2.5 text-sm font-semibold ${tab === id ? "border-brand text-brand" : "border-transparent text-muted hover:text-text"}`}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </header>
            <div className="flex min-h-0 flex-1">
              <section className="min-w-0 flex-1 overflow-y-auto px-6 py-6" role="tabpanel">
                {tab === "ask" && (
                  <AskPanel
                    kase={kase}
                    aiEnabled={!!health?.ai_enabled}
                    entries={entries[kase.id] ?? []}
                    setEntries={(u) =>
                      setEntries((prev) => ({
                        ...prev,
                        [kase.id]: typeof u === "function" ? u(prev[kase.id] ?? []) : u,
                      }))
                    }
                    open={setViewer}
                  />
                )}
                {tab === "chronology" && <ChronologyPanel kase={kase} aiEnabled={!!health?.ai_enabled} open={setViewer} />}
                {tab === "documents" && (
                  <DocumentsPanel
                    kase={kase}
                    open={setViewer}
                    onChanged={() => {
                      openCase(kase.id);
                      loadCases();
                    }}
                  />
                )}
                {tab === "activity" && <ActivityPanel key={`${kase.id}-${Object.values(entries).flat().length}`} kase={kase} />}
              </section>
              {viewer && (
                <PageViewer
                  key={`${viewer.docId}-${viewer.page}-${viewer.quote ?? ""}`}
                  target={viewer}
                  onClose={() => setViewer(null)}
                  onNavigate={setViewer}
                />
              )}
            </div>
          </>
        ) : (
          <Welcome busy={busy} onSample={loadSample} onNew={newCase} hasCases={cases.length > 0} />
        )}
      </main>
    </div>
  );
}

function Wordmark() {
  return (
    <span className="flex items-center gap-2 text-[17px] font-bold tracking-tight">
      <svg width="20" height="20" viewBox="0 0 20 20" aria-hidden>
        <rect x="2" y="3" width="12" height="15" rx="1.5" fill="none" stroke="var(--brand)" strokeWidth="1.8" />
        <rect x="9" y="1" width="9" height="6" rx="1" fill="var(--exhibit)" />
      </svg>
      Pincite
    </span>
  );
}

function Welcome({ busy, onSample, onNew, hasCases }: {
  busy: string | null;
  onSample: () => void;
  onNew: () => void;
  hasCases: boolean;
}) {
  return (
    <div className="flex flex-1 overflow-y-auto px-6 py-12">
      <div className="m-auto w-full max-w-[44rem]">
        <h1 className="max-w-[20ch] font-serif text-[2.6rem] leading-[1.1] font-semibold sm:text-[3.1rem]">
          Answers from the case file, with the page to prove it.
        </h1>
        <p className="mt-5 max-w-[56ch] text-[17px] leading-relaxed text-muted">
          Add a case&apos;s PDFs, ask questions in plain English, and get answers where every quote is checked against
          the page it came from. Build a chronology of every dated event in one click.
        </p>

        <figure className="mt-9 rounded-xl border border-line bg-surface p-5" aria-label="Example answer">
          <p className="text-sm font-semibold">When did Northwind first learn the harness was overheating?</p>
          <p className="mt-3 font-serif text-[16.5px] leading-[1.7]">
            Its thermal test report came back on August 2, 2021, showing the harness running more than 30 percent above
            spec
            <span className="mx-0.5 rounded bg-exhibit px-1 align-super font-sans text-[11px] font-bold text-exhibit-ink">1</span>
            . Three days later, operations declined to pause shipments before the Q4 sales push
            <span className="mx-0.5 rounded bg-exhibit px-1 align-super font-sans text-[11px] font-bold text-exhibit-ink">2</span>.
          </p>
          <figcaption className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-xs text-muted">
            <span>
              <span className="font-semibold text-text">1</span> Ex. 2, p. 1, quote found on page
            </span>
            <span>
              <span className="font-semibold text-text">2</span> Ex. 3, p. 1, quote found on page
            </span>
          </figcaption>
        </figure>

        <div className="mt-9 flex flex-wrap items-center gap-3">
          <button
            onClick={onSample}
            disabled={!!busy}
            className="inline-flex h-11 items-center gap-2 rounded-lg bg-brand px-5 text-[15px] font-semibold text-brand-ink disabled:opacity-60"
          >
            {busy === "sample" && <Spinner />}
            {busy === "sample" ? "Loading 5 exhibits…" : "Open the sample case"}
          </button>
          <button onClick={onNew} disabled={!!busy} className="h-11 rounded-lg border border-line px-5 text-[15px] font-semibold hover:bg-surface">
            Start a new case
          </button>
        </div>
        <p className="mt-4 max-w-[60ch] text-sm text-muted">
          The sample is a fictional consumer class action: a complaint, a deposition excerpt, an internal email, a
          warranty claim with personal data to redact, and a scanned fire report that needs OCR.
          {hasCases && " Or pick an existing case from the list."}
        </p>
      </div>
    </div>
  );
}

function AccessGate({ onUnlock }: { onUnlock: () => void }) {
  const [code, setCode] = useState("");
  return (
    <div className="grid h-dvh place-items-center px-6">
      <form
        className="w-full max-w-sm"
        onSubmit={(e) => {
          e.preventDefault();
          setAccessCode(code.trim());
          onUnlock();
        }}
      >
        <Wordmark />
        <label htmlFor="code" className="mt-6 block text-sm font-semibold">
          Access code
        </label>
        <p className="mt-1 text-sm text-muted">This workspace is private. Enter the code you were given.</p>
        <input
          id="code"
          type="password"
          autoFocus
          value={code}
          onChange={(e) => setCode(e.target.value)}
          className="mt-3 h-11 w-full rounded-lg border border-line bg-surface px-3 outline-none focus:border-brand"
        />
        <button className="mt-3 h-11 w-full rounded-lg bg-brand text-sm font-semibold text-brand-ink">Open workspace</button>
      </form>
    </div>
  );
}
