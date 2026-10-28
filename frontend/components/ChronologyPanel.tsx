"use client";

import { useEffect, useState } from "react";
import { api, ApiError, downloadChronologyCsv, type CaseDetail, type ChronoEvent } from "@/lib/api";
import type { ViewerTarget } from "./PageViewer";
import { ExhibitTag, Spinner, formatDate } from "./ui";

export default function ChronologyPanel({ kase, aiEnabled, open }: {
  kase: CaseDetail;
  aiEnabled: boolean;
  open: (t: ViewerTarget) => void;
}) {
  const [items, setItems] = useState<ChronoEvent[] | null>(null);
  const [building, setBuilding] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    api
      .chronology(kase.id)
      .then((r) => {
        if (live) setItems(r.items);
      })
      .catch(() => {
        if (live) setItems([]);
      });
    return () => {
      live = false;
    };
  }, [kase.id, kase.documents.length]);

  async function build() {
    setBuilding(true);
    setError(null);
    try {
      const r = await api.buildChronology(kase.id);
      setItems(r.items);
      setNote(
        r.method === "ai"
          ? r.dropped_unverified
            ? `${r.events} events. ${r.dropped_unverified} more were left out because their quotes couldn't be found in the documents.`
            : `${r.events} events, each backed by a quote found in the documents.`
          : `${r.events} dated passages found by pattern matching. Turn on AI for written event summaries.`,
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't build the chronology.");
    } finally {
      setBuilding(false);
    }
  }

  if (kase.documents.length === 0) {
    return <p className="text-[15px] text-muted">Add documents to this case to build a chronology.</p>;
  }

  const byYear = new Map<string, ChronoEvent[]>();
  for (const e of items ?? []) {
    const y = e.date.slice(0, 4);
    byYear.set(y, [...(byYear.get(y) ?? []), e]);
  }

  return (
    <div className="max-w-[52rem]">
      <div className="flex flex-wrap items-center gap-3">
        <button
          onClick={build}
          disabled={building}
          className="inline-flex h-10 items-center gap-2 rounded-lg bg-brand px-4 text-sm font-semibold text-brand-ink disabled:opacity-50"
        >
          {building && <Spinner />}
          {items?.length ? "Rebuild chronology" : "Build chronology"}
        </button>
        {!!items?.length && (
          <button
            onClick={() => downloadChronologyCsv(kase.id, kase.name).catch(() => setError("Couldn't export the chronology."))}
            className="h-10 rounded-lg border border-line px-4 text-sm font-semibold hover:bg-surface"
          >
            Export CSV
          </button>
        )}
        <p className="text-sm text-muted">
          {building
            ? aiEnabled
              ? "Reading every page and checking each event's quote…"
              : "Finding dated passages…"
            : note}
        </p>
      </div>
      {error && <p className="mt-3 text-sm text-danger">{error}</p>}

      {items && items.length === 0 && !building && (
        <p className="mt-8 max-w-[56ch] text-[15px] text-muted">
          A chronology lists every dated event in the case file in order, each linked to the page it came from.
          Build one to start.
        </p>
      )}

      {[...byYear.entries()].map(([year, events]) => (
        <section key={year} className="mt-8">
          <h3 className="font-serif text-2xl font-semibold text-brand">{year}</h3>
          <ol className="mt-3 border-l-2 border-line">
            {events.map((e) => (
              <li key={e.id} className="relative grid gap-1 py-3 pl-5 sm:grid-cols-[7.5rem_1fr] sm:gap-4">
                <span className="absolute top-[1.15rem] -left-[5px] size-2 rounded-full bg-brand" aria-hidden />
                <time dateTime={e.date} className="text-sm font-semibold tabular-nums">
                  {formatDate(e.date, e.precision)}
                </time>
                <div>
                  <p className="font-serif text-[15.5px] leading-relaxed">{e.description}</p>
                  <div className="mt-1.5 flex items-center gap-2">
                    <ExhibitTag n={e.exhibit_no} page={e.page_no} onClick={() => open({ docId: e.document_id, page: e.page_no, quote: e.quote })} />
                    <span className="truncate text-xs text-muted">{e.filename}</span>
                  </div>
                </div>
              </li>
            ))}
          </ol>
        </section>
      ))}
    </div>
  );
}
