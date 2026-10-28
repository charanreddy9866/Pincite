"use client";

import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import { api, ApiError, type Page } from "@/lib/api";
import { findQuote } from "@/lib/highlight";
import { ExhibitTag, Spinner } from "./ui";

export type ViewerTarget = { docId: number; page: number; quote?: string };

export default function PageViewer({ target, onClose, onNavigate }: {
  target: ViewerTarget;
  onClose: () => void;
  onNavigate: (t: ViewerTarget) => void;
}) {
  const [page, setPage] = useState<Page | null>(null);
  const [error, setError] = useState<string | null>(null);
  const markRef = useRef<HTMLElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    let live = true;
    api
      .page(target.docId, target.page)
      .then((p) => live && (setPage(p), setError(null)))
      .catch((e) => live && setError(e instanceof ApiError ? e.message : "Couldn't open this page."));
    return () => {
      live = false;
    };
  }, [target.docId, target.page]);

  useEffect(() => {
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const current = page && page.id === target.docId && page.page_no === target.page ? page : null;
  const ranges = useMemo(
    () => (current && target.quote ? findQuote(current.text, target.quote) : []),
    [current, target.quote],
  );

  useEffect(() => {
    markRef.current?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [ranges]);

  const pieces: React.ReactNode[] = [];
  if (current) {
    let at = 0;
    ranges.forEach(([s, e], i) => {
      pieces.push(<Fragment key={`t${i}`}>{current.text.slice(at, s)}</Fragment>);
      pieces.push(
        <mark key={`m${i}`} ref={i === 0 ? markRef : undefined}>
          {current.text.slice(s, e)}
        </mark>,
      );
      at = e;
    });
    pieces.push(<Fragment key="end">{current.text.slice(at)}</Fragment>);
  }

  return (
    <aside
      className="drawer-in fixed inset-0 z-40 flex flex-col bg-surface shadow-2xl lg:static lg:inset-auto lg:z-auto lg:w-[30rem] lg:border-l lg:border-line lg:shadow-none"
      aria-label="Document page"
    >
      <header className="flex items-center gap-3 border-b border-line px-5 py-3">
        {current ? (
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <ExhibitTag n={current.exhibit_no} page={current.page_no} />
              <span className="text-xs text-muted">of {current.pages}</span>
            </div>
            <p className="mt-1 truncate text-sm font-medium">{current.filename}</p>
          </div>
        ) : (
          <div className="flex-1 text-sm text-muted">{error ? "Page unavailable" : "Opening page…"}</div>
        )}
        <button
          ref={closeRef}
          onClick={onClose}
          className="grid size-8 place-items-center rounded-md text-muted hover:bg-sunken hover:text-text"
          aria-label="Close page"
        >
          <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden>
            <path d="M1 1l10 10M11 1L1 11" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
          </svg>
        </button>
      </header>

      {target.quote && current && (
        <p
          className={`border-b border-line px-5 py-2 text-xs ${ranges.length ? "bg-brand-soft text-brand" : "bg-danger-soft text-danger"}`}
        >
          {ranges.length
            ? "The cited quote is highlighted on this page."
            : "The cited quote isn't on this page. Don't rely on this citation."}
        </p>
      )}

      <div className="flex-1 overflow-y-auto px-6 py-6">
        {error && <p className="text-sm text-danger">{error}</p>}
        {!current && !error && <Spinner className="text-muted" />}
        {current && (
          <div className="mx-auto max-w-[62ch] whitespace-pre-wrap font-serif text-[15px] leading-[1.75]">
            {pieces}
          </div>
        )}
      </div>

      {current && current.pages > 1 && (
        <footer className="flex items-center justify-between border-t border-line px-5 py-2.5 text-sm">
          <button
            disabled={current.page_no <= 1}
            onClick={() => onNavigate({ docId: current.id, page: current.page_no - 1 })}
            className="rounded-md px-2.5 py-1 font-medium text-brand hover:bg-brand-soft disabled:opacity-30"
          >
            Previous page
          </button>
          <span className="text-muted tabular-nums">
            Page {current.page_no} of {current.pages}
          </span>
          <button
            disabled={current.page_no >= current.pages}
            onClick={() => onNavigate({ docId: current.id, page: current.page_no + 1 })}
            className="rounded-md px-2.5 py-1 font-medium text-brand hover:bg-brand-soft disabled:opacity-30"
          >
            Next page
          </button>
        </footer>
      )}
    </aside>
  );
}
