"use client";

import { useRef, useState } from "react";
import { api, ApiError, type CaseDetail } from "@/lib/api";
import type { ViewerTarget } from "./PageViewer";
import { ExhibitTag, Spinner, redactionSummary } from "./ui";

export default function DocumentsPanel({ kase, onChanged, open }: {
  kase: CaseDetail;
  onChanged: () => void;
  open: (t: ViewerTarget) => void;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [queue, setQueue] = useState<string[]>([]);
  const [errors, setErrors] = useState<string[]>([]);
  const [dragging, setDragging] = useState(false);

  async function add(files: FileList | File[]) {
    const pdfs = Array.from(files);
    if (!pdfs.length) return;
    setErrors([]);
    setQueue(pdfs.map((f) => f.name));
    for (const f of pdfs) {
      try {
        await api.upload(kase.id, f);
      } catch (err) {
        setErrors((prev) => [...prev, err instanceof ApiError ? err.message : `${f.name} couldn't be added.`]);
      }
      setQueue((prev) => prev.slice(1));
      onChanged();
    }
  }

  return (
    <div className="max-w-[56rem]">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          add(e.dataTransfer.files);
        }}
        className={`flex flex-col items-start gap-3 rounded-xl border-2 border-dashed px-5 py-5 sm:flex-row sm:items-center sm:justify-between ${dragging ? "border-brand bg-brand-soft" : "border-line"}`}
      >
        <div className="text-sm">
          <p className="font-semibold">Add PDFs to this case</p>
          <p className="mt-0.5 text-muted">
            Drop files here. Scanned pages are read with OCR. Social Security, account, card and phone numbers are
            redacted before anything is stored.
          </p>
        </div>
        <button
          onClick={() => input.current?.click()}
          disabled={queue.length > 0}
          className="inline-flex h-10 shrink-0 items-center gap-2 rounded-lg bg-brand px-4 text-sm font-semibold text-brand-ink disabled:opacity-50"
        >
          {queue.length > 0 && <Spinner />}
          {queue.length > 0 ? `Adding ${queue.length}…` : "Choose PDFs"}
        </button>
        <input
          ref={input}
          type="file"
          accept="application/pdf,.pdf"
          multiple
          className="hidden"
          onChange={(e) => {
            if (e.target.files) add(e.target.files);
            e.target.value = "";
          }}
        />
      </div>
      {queue.length > 0 && <p className="mt-2 text-sm text-muted">Reading {queue[0]}…</p>}
      {errors.map((e) => (
        <p key={e} className="mt-2 text-sm text-danger">
          {e}
        </p>
      ))}

      {kase.documents.length > 0 && (
        <div className="mt-6 overflow-x-auto rounded-xl border border-line bg-surface">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-line text-muted">
              <tr>
                <th className="px-4 py-2.5 font-medium">Exhibit</th>
                <th className="px-4 py-2.5 font-medium">File</th>
                <th className="px-4 py-2.5 font-medium">Pages</th>
                <th className="px-4 py-2.5 font-medium">Processing</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {kase.documents.map((d) => {
                const red = redactionSummary(d.redactions);
                return (
                  <tr key={d.id}>
                    <td className="px-4 py-3">
                      <ExhibitTag n={d.exhibit_no} />
                    </td>
                    <td className="px-4 py-3">
                      <button onClick={() => open({ docId: d.id, page: 1 })} className="text-left font-medium hover:text-brand hover:underline">
                        {d.filename}
                      </button>
                    </td>
                    <td className="px-4 py-3 tabular-nums">{d.pages}</td>
                    <td className="px-4 py-3 text-muted">
                      {d.ocr_pages > 0 && <p>{d.ocr_pages === d.pages ? "Scanned, read with OCR" : `${d.ocr_pages} scanned pages read with OCR`}</p>}
                      {red && <p>Redacted {red}</p>}
                      {!d.ocr_pages && !red && <p>Text extracted</p>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
