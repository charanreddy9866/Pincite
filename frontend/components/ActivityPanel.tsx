"use client";

import { useEffect, useState } from "react";
import { api, type Activity, type CaseDetail } from "@/lib/api";
import { redactionSummary } from "./ui";

function describe(a: Activity): string {
  const d = a.detail as Record<string, never>;
  switch (a.action) {
    case "case.created":
      return `Case created${d.sample ? " from the sample files" : ""}`;
    case "document.uploaded": {
      const red = redactionSummary(d.redactions ?? {});
      return `Added ${d.filename} (${d.pages} ${d.pages === 1 ? "page" : "pages"}${d.ocr_pages ? `, ${d.ocr_pages} via OCR` : ""})${red ? `. Redacted ${red}` : ""}`;
    }
    case "question.asked":
      return `Asked "${d.question}" (${d.verified} of ${d.citations} quotes verified, ${String(d.status).replace(/_/g, " ")})`;
    case "chronology.built":
      return `Built chronology: ${d.events} events${d.dropped_unverified ? `, ${d.dropped_unverified} unverified events left out` : ""}`;
    case "chronology.exported":
      return "Exported chronology to CSV";
    default:
      return a.action;
  }
}

export default function ActivityPanel({ kase }: { kase: CaseDetail }) {
  const [items, setItems] = useState<Activity[] | null>(null);

  useEffect(() => {
    let live = true;
    api
      .activity(kase.id)
      .then((r) => {
        if (live) setItems(r);
      })
      .catch(() => {
        if (live) setItems([]);
      });
    return () => {
      live = false;
    };
  }, [kase.id]);

  if (!items) return null;
  return (
    <div className="max-w-[52rem]">
      <p className="max-w-[62ch] text-sm text-muted">
        Every upload, question and export on this case is recorded here, so you can show how an answer was produced.
      </p>
      <ol className="mt-5 divide-y divide-line rounded-xl border border-line bg-surface">
        {items.map((a, i) => (
          <li key={i} className="grid gap-1 px-4 py-3 text-sm sm:grid-cols-[11rem_1fr] sm:gap-4">
            <time dateTime={a.ts} className="text-muted tabular-nums">
              {new Date(a.ts).toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}
            </time>
            <span>{describe(a)}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}
