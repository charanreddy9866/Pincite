import type { Redactions } from "@/lib/api";

/** Styled after a court exhibit sticker: the visual signal for "this came from the record". */
export function ExhibitTag({ n, page, onClick }: { n: number | null; page?: number | null; onClick?: () => void }) {
  const body = (
    <>
      <span className="font-bold">Ex. {n ?? "?"}</span>
      {page != null && <span className="font-medium opacity-80">p. {page}</span>}
    </>
  );
  const cls =
    "inline-flex shrink-0 items-center gap-1.5 rounded-[5px] bg-exhibit px-1.5 py-0.5 text-[12px] leading-4 text-exhibit-ink tabular-nums";
  return onClick ? (
    <button type="button" onClick={onClick} className={`${cls} hover:brightness-95`}>
      {body}
    </button>
  ) : (
    <span className={cls}>{body}</span>
  );
}

const LABELS: Record<string, [string, string]> = {
  SSN: ["Social Security number", "Social Security numbers"],
  ACCOUNT: ["account number", "account numbers"],
  CARD: ["card number", "card numbers"],
  PHONE: ["phone number", "phone numbers"],
  EMAIL: ["email address", "email addresses"],
};

export function redactionSummary(r: Redactions): string | null {
  const parts = Object.entries(r)
    .filter(([, n]) => n)
    .map(([k, n]) => `${n} ${LABELS[k]?.[n === 1 ? 0 : 1] ?? k.toLowerCase()}`);
  return parts.length ? parts.join(", ") : null;
}

export function Spinner({ className = "" }: { className?: string }) {
  return (
    <svg className={`size-4 animate-spin ${className}`} viewBox="0 0 24 24" fill="none" aria-hidden>
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeOpacity="0.25" strokeWidth="3" />
      <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}

export function CheckIcon({ className = "" }: { className?: string }) {
  return (
    <svg className={className} width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden>
      <path d="M3 8.5l3.2 3L13 4.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function AlertIcon({ className = "" }: { className?: string }) {
  return (
    <svg className={className} width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden>
      <path d="M8 1.8l6.5 11.4H1.5L8 1.8z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
      <path d="M8 6.3v3.2M8 11.4v.1" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

export function formatDate(iso: string, precision: "day" | "month" | "year" = "day") {
  const [y, m, d] = iso.split("-").map(Number);
  const date = new Date(Date.UTC(y, (m || 1) - 1, d || 1));
  const opts: Intl.DateTimeFormatOptions =
    precision === "year"
      ? { year: "numeric", timeZone: "UTC" }
      : precision === "month"
        ? { month: "short", year: "numeric", timeZone: "UTC" }
        : { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" };
  return date.toLocaleDateString("en-US", opts);
}
