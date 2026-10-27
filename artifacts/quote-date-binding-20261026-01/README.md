# The software now locates quoted words itself

T35, 2026-10-26. This is an offline implementation of the next step after the [actual failed AI check](../metadata-live-20261026-01/README.md). No new model request, retry or image fetch occurred.

## The same concrete example

The earlier AI correctly quoted **“January 2, 1900”**, but pointed to the wrong place in this short made-up sentence:

> Synthetic transport check only. The meeting was held January 2, 1900.

The new path asks an AI for the exact words and the paragraph they came from. Ordinary software then finds those words in the original paragraph. For this example, it finds positions53–68, the correct location.

It accepts a source link only when the quoted words appear **exactly once in the stated paragraph** and that paragraph matches the expected source hash. If the words are absent, appear twice (including overlapping matches), or come from a different paragraph, it refuses the link. It does not guess, tidy the OCR, normalize Unicode or choose the first of several matches.

The old AI answer remains saved and rejected. We did not silently fix it or call it a successful AI result. [The example record](example.json) shows the old error, a separately labelled new test input without character positions, and the software-generated positions. This new input is a constructed offline example, not a newly generated AI reply.

## What is working and what remains unproved

The new path is connected to the existing small-job runner. It saves the original offset-free reply and a separately labelled source-linked result with software-generated positions. It also recovers a saved reply in a new process without repeating the test request.

After finding the quote, the software still applies all the previous date rules. A date must actually be supported by the quoted words. It cannot travel backward from a later heading or cross a Senate/House boundary. Every paragraph must receive a supported date proposal or an explicit unknown. Conflicting alternatives remain unresolved. Correctly finding words does not make an AI's interpretation historically correct or human-approved.

The full project checks passed **562 tests**, including27new cases for this change. The checks cover missing/repeated/overlapping quotes, wrong paragraphs/hashes, non-English characters and combining marks, ambiguous references, alternatives, date support, full paragraph coverage, Senate/House and backward stops, both fake transport clients, ordinary result reuse and a fresh-process interruption. They also verify that the original failed reply stays invalid and unchanged.

The new request/output format has **not** been tried against a real AI. The earlier stopped run is still stopped; we have not spent its unused request slot. The real House-opening passage remains unsent. The next task freezes a separate, small live check for the new version before any further request.

## Version and evidence details

`quote_dates.py` defines strict `QuoteDateEvidence`, `QuoteDateAlternative`, `QuoteDateAssignment` and `QuoteDateResult` boundaries for **`scoped-date-quotes-v1`**. Evidence accepts only `paragraph_id`, `raw_sha256` and a nonempty exact `quote`; `start`/`end` are forbidden, including in alternatives. Date values still have ISO `value.start`/`value.end` fields; only evidence coordinates are removed from the model's responsibility.

A second exact search begins one Unicode codepoint after the first hit, so overlapping occurrences count as ambiguity. Uniqueness is per declared paragraph, not across unrelated paragraphs in a window. The typed original input and matching raw hash bind the source; derived coordinates are fed into unchanged `validate_date_result` and `source_mapped_dates`. The generic old schema and source artifacts were not edited.

Exports use `source-mapped-scoped-date-quotes-v1`, label the model and derived contracts separately, mark the coordinate method `host_unique_exact_quote_in_declared_raw_paragraph`, and retain the parsed offset-free `model_proposals`. The raw reply text, usage and journal checkpoints stay unchanged. The new contract rejects old offset-bearing replies; it is not a fallback that salvages failed v1 records. All outputs remain proposals, never human-reviewed history.

The existing runner has an explicit new contract choice. Prepared schema equality and request/input/contract/code fingerprints prevent old runs/results from being quietly reused with the new semantics. Provider specialization follows assignment/evidence schema references so the old and new date schemas get the correct paragraph enums; quote-specific instructions distinguish evidence coordinates from date endpoints. Fake-client checks prove request construction only, not remote constrained-schema support. The Ollama path still uses JSON-object mode plus local host validation.

Portable records:

- [New quote-only schema](schema.json), [offline proof summary](proof.json) and [bounded Luna review](review.json).
- [New prepared source packets and schema manifest](offline-run/prepared/manifest.json), [source-review status](offline-run/prepared/source-review.json), and [prospective prompt](offline-run/prepared/prompt.txt). These are explicitly offline fixtures, not launch-ready model requests or new human labels.
- [Offset-free replies and retained results](offline-run/run/summary.json), [source-linked export](offline-run/run/proposals.json), and [full check log](gate.log). The original colored check log is retained compressed; the readable copy only removes terminal coloring and trailing spaces.
- [Validation hashes](validation.json) bind the final code, portable evidence and unchanged earlier failure records.

The separate Luna code review found no correctness issue; this is not historical grading or the independent adoption verdict for a new workflow. The change extends the existing validated runner and adds no command, framework, supervisor or new provider dependency. M1/M2/P0 remain open. T32's old offset-based live check stays blocked; the next new-version readiness task is T36.
