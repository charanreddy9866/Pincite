"use client";

import { useState } from "react";
import { api, ApiError, type Answer, type CaseDetail } from "@/lib/api";
import type { ViewerTarget } from "./PageViewer";
import { AlertIcon, CheckIcon, ExhibitTag, Spinner } from "./ui";

const SAMPLE_QUESTIONS = [
  "When did Northwind first learn the harness was overheating, and what did it do next?",
  "Why was Ms. Rivera's warranty claim denied, and does any other document contradict that?",
  "What is the proposed class, and which claims does the complaint bring?",
];

type Entry = { id: number; question: string; result?: Answer; error?: string };

export default function AskPanel({ kase, aiEnabled, entries, setEntries, open }: {
  kase: CaseDetail;
  aiEnabled: boolean;
  entries: Entry[];
  setEntries: React.Dispatch<React.SetStateAction<Entry[]>>;
  open: (t: ViewerTarget) => void;
}) {
  const [question, setQuestion] = useState("");
  const busy = entries.some((e) => !e.result && !e.error);
  const isSample = kase.name.includes("(sample)");

  async function ask(q: string) {
    const text = q.trim();
    if (text.length < 3 || busy) return;
    const id = Date.now();
    setEntries((prev) => [{ id, question: text }, ...prev]);
    setQuestion("");
    try {
      const result = await api.ask(kase.id, text);
      setEntries((prev) => prev.map((e) => (e.id === id ? { ...e, result } : e)));
    } catch (err) {
      const error = err instanceof ApiError ? err.message : "Something went wrong. Try again.";
      setEntries((prev) => prev.map((e) => (e.id === id ? { ...e, error } : e)));
    }
  }

  if (kase.documents.length === 0) {
    return (
      <p className="max-w-[56ch] text-[15px] text-muted">
        This case has no documents yet. Add PDFs on the Documents tab, then come back to ask questions about them.
      </p>
    );
  }

  return (
    <div className="max-w-[52rem]">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          ask(question);
        }}
      >
        <label htmlFor="question" className="text-sm font-semibold">
          Ask about these {kase.documents.length} documents
        </label>
        <div className="mt-2 flex flex-col gap-2 sm:flex-row sm:items-end">
          <textarea
            id="question"
            rows={2}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                e.preventDefault();
                ask(question);
              }
            }}
            placeholder="e.g. What did the defendant know about the defect, and when?"
            className="min-h-[3.25rem] flex-1 resize-y rounded-lg border border-line bg-surface px-3.5 py-2.5 text-[15px] leading-6 outline-none placeholder:text-muted focus:border-brand"
          />
          <button
            type="submit"
            disabled={busy || question.trim().length < 3}
            className="h-11 rounded-lg bg-brand px-5 text-sm font-semibold text-brand-ink disabled:opacity-40"
          >
            Ask
          </button>
        </div>
        {!aiEnabled && (
          <p className="mt-2 text-xs text-muted">
            AI answers are off on this server. You&apos;ll get the passages that best match your question instead.
          </p>
        )}
      </form>

      {entries.length === 0 && isSample && (
        <div className="mt-8">
          <p className="text-sm font-semibold">Try one of these</p>
          <ul className="mt-2 divide-y divide-line border-y border-line">
            {SAMPLE_QUESTIONS.map((q) => (
              <li key={q}>
                <button
                  onClick={() => ask(q)}
                  className="w-full py-3 text-left text-[15px] hover:text-brand"
                >
                  {q}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      <ol className="mt-8 space-y-6">
        {entries.map((e) => (
          <li key={e.id} className="rounded-xl border border-line bg-surface">
            <p className="border-b border-line px-5 py-3 text-[15px] font-semibold">{e.question}</p>
            <div className="px-5 py-4">
              {!e.result && !e.error && (
                <p className="flex items-center gap-2 text-sm text-muted">
                  <Spinner /> Searching the documents and checking quotes…
                </p>
              )}
              {e.error && <p className="text-sm text-danger">{e.error}</p>}
              {e.result && <AnswerView a={e.result} open={open} />}
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}

function StatusLine({ a }: { a: Answer }) {
  const total = a.citations.length;
  const ok = a.citations.filter((c) => c.verified).length;
  const map: Record<string, [string, string, React.ReactNode]> = {
    verified: ["bg-brand-soft text-brand", `All ${total} quoted ${total === 1 ? "passage was" : "passages were"} found on the cited pages.`, <CheckIcon key="i" />],
    partially_verified: ["bg-warn-soft text-warn", `${total - ok} of ${total} quotes could not be found on the cited page. Those citations are struck through below.`, <AlertIcon key="i" />],
    unverified: ["bg-danger-soft text-danger", "None of the quotes could be found in the documents. Don't rely on this answer.", <AlertIcon key="i" />],
    not_found: ["bg-sunken text-muted", "The documents don't answer this question.", null],
    retrieval_only: ["bg-sunken text-muted", "Closest matching passages (AI answers are off).", null],
    error: ["bg-danger-soft text-danger", "The answer couldn't be checked.", <AlertIcon key="i" />],
  };
  const [cls, text, icon] = map[a.status];
  return (
    <p className={`flex items-start gap-2 rounded-md px-2.5 py-1.5 text-[13px] font-medium ${cls}`}>
      {icon && <span className="mt-[3px]">{icon}</span>}
      {text}
    </p>
  );
}

function AnswerText({ text, a, open }: { text: string; a: Answer; open: (t: ViewerTarget) => void }) {
  const paragraphs = text.split(/\n{2,}/).filter((p) => p.trim());
  return (
    <div className="space-y-3 font-serif text-[16.5px] leading-[1.7]">
      {paragraphs.map((para, i) => (
        <p key={i}>
          {para.split(/(\[\d+\])/).map((part, j) => {
            const m = part.match(/^\[(\d+)\]$/);
            if (!m) return <span key={j}>{part}</span>;
            const c = a.citations.find((x) => x.n === Number(m[1]));
            if (!c || c.document_id == null) return <sup key={j}>{part}</sup>;
            return (
              <button
                key={j}
                onClick={() => open({ docId: c.document_id!, page: c.page_no!, quote: c.quote })}
                className={`mx-0.5 rounded px-1 align-super font-sans text-[11px] font-bold ${c.verified ? "bg-exhibit text-exhibit-ink" : "bg-danger-soft text-danger line-through"}`}
                aria-label={`Open citation ${c.n}: Exhibit ${c.exhibit_no}, page ${c.page_no}`}
              >
                {c.n}
              </button>
            );
          })}
        </p>
      ))}
    </div>
  );
}

function AnswerView({ a, open }: { a: Answer; open: (t: ViewerTarget) => void }) {
  return (
    <div className="space-y-4">
      <StatusLine a={a} />
      {a.status !== "retrieval_only" && <AnswerText text={a.answer} a={a} open={open} />}

      {a.citations.length > 0 && (
        <ol className="space-y-2 border-t border-line pt-4">
          {a.citations.map((c) => (
            <li key={c.n} className="flex gap-3 text-sm">
              <span className="w-4 shrink-0 pt-0.5 text-right font-semibold text-muted tabular-nums">{c.n}</span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  {c.document_id != null ? (
                    <ExhibitTag n={c.exhibit_no} page={c.page_no} onClick={() => open({ docId: c.document_id!, page: c.page_no!, quote: c.quote })} />
                  ) : (
                    <ExhibitTag n={null} />
                  )}
                  {c.verified ? (
                    <span className="inline-flex items-center gap-1 text-xs font-medium text-brand">
                      <CheckIcon /> Quote found on page
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 text-xs font-medium text-danger">
                      <AlertIcon /> Not found on the cited page
                    </span>
                  )}
                </div>
                <blockquote className={`mt-1 font-serif italic leading-relaxed ${c.verified ? "" : "text-muted line-through"}`}>
                  &ldquo;{c.quote}&rdquo;
                </blockquote>
              </div>
            </li>
          ))}
        </ol>
      )}

      {a.status === "retrieval_only" && (
        <ol className="space-y-3">
          {a.passages.map((p, i) => (
            <li key={i} className="text-sm">
              <ExhibitTag n={p.exhibit_no} page={p.page_no} onClick={() => open({ docId: p.document_id, page: p.page_no })} />
              <p className="mt-1 line-clamp-4 font-serif leading-relaxed">{p.text}</p>
            </li>
          ))}
        </ol>
      )}

      {a.searches.length > 1 && (
        <details className="text-xs text-muted">
          <summary className="cursor-pointer select-none">
            Ran {a.searches.length} searches to answer this
          </summary>
          <ol className="mt-2 list-decimal space-y-1 pl-5">
            {a.searches.map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ol>
        </details>
      )}
    </div>
  );
}

export type { Entry };
