# V2 pivot: research-first corpus without OCR repair

## Status and hypothesis

For the local embedding-model recommendation and compatibility checks, see [V2_EMBEDDING_MODELS.md](V2_EMBEDDING_MODELS.md).

This is an alternative, unvalidated direction. It does not replace, invalidate, or authorize discarding the static cleanup, patch ledgers, queue, canonical exports, or RAG work already completed. Keep those artifacts immutable and available for comparison.

**Hypothesis:** research discovery may improve more from structuring page/turn windows and adding evidence-linked person, place, topic, and legislation tags than from spending the next iteration repairing OCR. Preserve the OCR as-is for this experiment. Do not treat normalized OCR as ground truth; the existing static and AI outputs remain separate comparison inputs.

The target remains all five parts of _The Congressional Globe_, 39th Congress, 1st Session. The pivot changes the next experiment's objective, not the historical scope or the long-term requirement for trustworthy canonical text.

## Product boundaries

- **Immutable sources:** retain hOCR, DjVu, page maps, available catalog metadata, and hashes unchanged.
- **Canonical transcription:** retain original OCR and accepted normalized revisions with existing correction ledgers. V2 adds no text edits. A passage window is a derived view with links to its ordered source paragraphs; it does not replace or merge canonical records.
- **Controlled enrichment:** store candidate person/place/topic/legislation tags separately from transcription, with vocabulary/authority version, evidence paragraph and text span, method, uncertainty, and review state. Multiple tags, no tag, unknown, and conflicting candidates must be representable.
- **Loose discovery tags:** optional free-form search hints live in a separate, explicitly unverified field/layer. They cannot satisfy structured historical filters or be presented as authority matches.
- **Retrieval and answers:** retrieval units point to canonical paragraph IDs, source item, part, scan leaf, printed page, hOCR page/line IDs, and geometry where available. Generated answers cite retrieved evidence. A retrieval chunk is not presumed to be one speaker or one topic.

### Evidence and unknowns

Date and speaker assignments require positive evidence in the cited window or an explicitly linked, reviewed boundary/continuation assertion. Record source paragraph and quoted span. Do not copy a date or speaker across a boundary just to fill a field. For mixed or uncertain windows, preserve multiple candidates or `unknown`; do not assign one speaker, chamber, party, date, topic, or bill to the whole window. Party/state affiliation is time-scoped and requires a separate sourced authority assertion. A mention of a person is not a speaker assignment; a bill mention is not proof the passage debates that bill.

## Existing contracts: useful foundation and gaps

Current support is in [models.py](src/congressional_globe/models.py), [chunking.py](src/congressional_globe/chunking.py), [structure.py](src/congressional_globe/structure.py), and [PROJECT_GOAL.md](PROJECT_GOAL.md).

- `PageRecord`, `ParagraphRecord`, `TextEdit`, and `RAGParagraphSource` preserve raw/normalized text, source identity, hOCR anchors, geometry, and cleanup provenance. These remain the source-link layer for V2.
- `RAGChunk` is page-bounded, cites its constituent paragraph IDs, and carries per-paragraph sources. This is a retrieval baseline, not yet a speaker-turn or proceeding-window model.
- `structure.py` conservatively derives some date/chamber facts and review hints. Current `context` is a string dictionary; it is not a typed, versioned historical assertion with alternatives, evidence offsets, adjudication, or authority links.
- There are no dedicated person/speaker, place, subject, legislation, affiliation, or boundary authority contracts. Current tags and context must not be stretched to imply those capabilities.

For V2, add versioned enrichment records linked to immutable source identity and a named canonical text layer/hash. Validate every evidence span against that exact text. Keep assertions append-only or versioned so a new proposal does not silently overwrite an earlier one. Full schemas are a later design unit; this note does not claim they exist.

## Comparative POC

### Question

On a small, labeled historical-query set, does an evidence-linked structured/discovery layer over unchanged page/turn windows improve finding and citing relevant material compared with text-only retrieval? Compare inputs built from (A) raw OCR and (B) the current static-normalized text. This separates the value of the V2 organization/tagging idea from the effect of existing cleanup.

### Controlled setup

1. Freeze a small, stratified set of source windows from all five parts, including proceedings, indexes, and Appendix material. Preserve paragraph order and source anchors. Include single-speaker candidates, mixed/uncertain windows, explicit dates, and windows with no safe date or speaker assignment.
2. Build both text variants from the same windows: raw OCR and the current static-normalized layer. Do not run new cleanup or edit either input. Record hashes and the canonical release/source IDs.
3. Compare a text-only baseline with page-bounded retrieval against the same retrieval plus V2 evidence-linked tags and explicit unknown/mixed handling. Keep chunk boundaries, retrieval settings, and query wording fixed across variants.
4. Use a small query set covering person/speaker, topic, place, legislation, and date/chamber filters, including ambiguous and negative cases. Human-label relevance and supported answer claims before examining system outputs; label expectations provisional, with disagreements retained.
5. For each retrieved item, inspect whether the cited paragraph/window supports the answer claim and whether its citation resolves to the exact source. Score structured tag correctness separately from loose discovery-tag usefulness.

### Decision gates

- **Integrity gate:** every returned citation resolves to a source window and exact paragraph IDs; every structured assertion has a valid evidence span, method, version, and review state. Any unsupported answer claim or falsely filled mixed/unknown field is a failure to investigate.
- **Retrieval gate:** report precision/recall at a predeclared small set of cutoffs and per-query results for raw and normalized text. Adopt no retrieval claim from aggregate scores alone; inspect misses and false positives by document type and part.
- **Tagging gate:** report precision, recall, abstention, and reviewer agreement separately for each tag family. A candidate with weak evidence must remain unknown/review, not be counted as a correct assignment.
- **Value gate:** compare against text-only retrieval on the same queries. Continue the pivot only if it improves useful discovery or grounded answer coverage without reducing source traceability or increasing unsupported structured claims. Otherwise keep the current workflow and revise the hypothesis.
- **No OCR-quality claim:** this POC measures retrieval, tagging, and answer grounding. It does not measure transcription accuracy, certify static edits, or establish image-level truth.

## Scope and handoff checklist

The user requested this exploratory POC. Current work prepares an isolated ten-query, fifty-window comparison, with at most twenty sequential local Qwen requests after preparation checks. No paid calls or full-corpus processing are part of this experiment. Production OCR, cleanup queues and exports stay intact. The first lexical retrieval baseline will not prove vector retrieval; a separate bounded embedding comparison is still needed. Exact execution state and delegate ownership are in `PROGRESS.md`.

- [x] Establish the user-requested experiment objective while preserving the cleanup path.
- [ ] Select and freeze a small, stratified set of windows and queries; record source and text-layer hashes.
- [ ] Define typed, versioned tag/assertion and evidence-span contracts, including alternatives, unknown/mixed, and review states.
- [ ] Write provisional labels and decision thresholds before running systems; keep ambiguity and reviewer disagreement visible.
- [ ] Compare raw OCR and current static-normalized inputs against the same text-only and tagged retrieval baselines.
- [ ] Report per-part/document-type errors, citations, unsupported claims, and all limitations before deciding whether to continue.

## Risks to test

The offline design audit is saved at `artifacts/v2-pivot-20261011/design-review.json`. Before deciding on the pivot, compare raw-only retrieval against the same raw text with proposed metadata; raw versus normalized text alone cannot show tagging value. Until all pool windows have relevance labels, report intended-target ranks/hits rather than precision or recall. Explicit unanswerable, mixed-speaker and unknown-date controls are required, and exact quotations need entailment review. The initial local model inventory contains no embedding-capable model; model selection research is underway separately.

- OCR errors may obscure names, dates, or legislative references; adding tags can give false confidence if evidence spans do not support them.
- Page windows can mix speakers and topics. Page-bounded chunking is a starting point, not a boundary detector.
- Historical names, offices, parties, and bill numbers require period-appropriate, sourced authorities; contemporary name matching is insufficient.
- Easy index entries may inflate results. Stratify and report by proceedings, index, and Appendix rather than only an aggregate score.
- Loose discovery labels may help search but must not leak into accepted structured filters or grounded answers.
- A small purposive POC can reject an unsafe approach or reveal a promising one; it cannot establish corpus-wide quality.
