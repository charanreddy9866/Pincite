# How Pincite works, for the people who rely on it

Pincite reads the documents in a case and answers questions about them. It is a research assistant, not a decision-maker. Here is who does what.

## What the AI decides
- **How to look.** It chooses what to search for, and can search again with different words or within a single exhibit if the first results aren't enough.
- **What the documents say.** It writes the answer in plain English.
- **Which passages support each statement.** For every statement it must point to a passage and copy the exact words.

## What the software decides (and the AI can't override)
- **What the AI is allowed to see.** Only excerpts from this case. Social Security, account, card and phone numbers were removed when the documents were added, so the AI never sees them.
- **Whether each quote is real.** After the AI answers, the software checks every quote against the actual page. If the words aren't on that page, the citation is struck through and the answer is flagged.
- **Instructions hidden in documents are ignored.** A document can contain text like "ignore your instructions." The AI is told that document text is evidence, never instructions. The sample case includes exactly this trap.
- **Everything is logged.** Each upload, question, and export is recorded on the Activity tab.

## What you verify
- **Click any citation.** The page opens with the quote highlighted, so you can read it in context and judge whether it supports the statement. The software proves the quote exists; only a person can judge whether it means what the answer says.
- **Read the status line.** Green means every quote was found. Amber means some weren't. Red means none were, so don't rely on that answer.
- **"Not found" is a real answer.** If the documents don't say, Pincite says so instead of guessing.
