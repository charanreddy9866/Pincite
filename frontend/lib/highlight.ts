/**
 * Locate a quote inside page text the same way the server verifies it (case-insensitive,
 * whitespace and smart-quote tolerant, "..." for elisions), and return ranges in the ORIGINAL text.
 */
const MAP: Record<string, string> = {
  "‘": "'",
  "’": "'",
  "“": '"',
  "”": '"',
  "–": "-",
  "—": "-",
  " ": " ",
};

function normalizeWithIndex(text: string, skipLineNumbers = false): { norm: string; index: number[] } {
  let norm = "";
  const index: number[] = [];
  let lastSpace = true;
  for (let i = 0; i < text.length; i++) {
    if (skipLineNumbers && (i === 0 || text[i - 1] === "\n")) {
      // Deposition transcripts number every line; skip "12 " at the start of a line.
      const m = /^[ \t]*\d{1,2}[ \t]+/.exec(text.slice(i, i + 8));
      if (m) i += m[0].length;
      if (i >= text.length) break;
    }
    let ch = MAP[text[i]] ?? text[i];
    if (/\s/.test(ch)) {
      if (lastSpace) continue;
      ch = " ";
      lastSpace = true;
    } else {
      lastSpace = false;
    }
    norm += ch.toLowerCase();
    index.push(i);
  }
  return { norm, index };
}

export function findQuote(text: string, quote: string): [number, number][] {
  const exact = locate(text, quote, false);
  return exact.length ? exact : locate(text, quote, true);
}

function locate(text: string, quote: string, skipLineNumbers: boolean): [number, number][] {
  const { norm, index } = normalizeWithIndex(text, skipLineNumbers);
  const parts = quote
    .split(/\.\.\.|…/)
    .map((p) => normalizeWithIndex(p.trim()).norm.replace(/^[\s.,;:"']+|[\s.,;:"']+$/g, ""))
    .filter(Boolean);
  const ranges: [number, number][] = [];
  let from = 0;
  for (const part of parts) {
    const at = norm.indexOf(part, from);
    if (at < 0) return [];
    ranges.push([index[at], index[at + part.length - 1] + 1]);
    from = at + part.length;
  }
  return ranges;
}
