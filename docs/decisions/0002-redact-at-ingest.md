# 2. Sensitive identifiers are redacted once, at ingest

**Status:** accepted

## Context
Case files contain Social Security numbers, bank and card numbers, phone numbers and emails. Those values almost never matter to a litigation question, and each place they're stored or sent (database, search index, model prompts, logs, UI) is a place they can leak.

## Decision
Redaction runs on the extracted page text before anything is stored. SSNs, Luhn-valid card numbers, labeled account/routing numbers, phone numbers and emails become `[REDACTED SSN]` and similar. Counts per document are recorded and shown to the user and in the activity log.

## Consequences
- Nothing downstream can leak an original value, because nothing downstream has it. The eval suite asks for the SSN on the sample claim form and expects "not found."
- Redaction is pattern-based. It favors not destroying legal identifiers (case numbers, Bates numbers, serial numbers, dates), which are covered by tests. Unlabeled account numbers can slip through; a named-entity model or a review queue would be the next step.
- Originals are not kept. A production system would store the original PDF encrypted with access controls, separate from the AI pipeline.
