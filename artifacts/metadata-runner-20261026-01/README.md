# One small processing job now connects the pieces

T28/T29, 2026-10-26. The stakeholder approved moving the main processing work ahead of optional AI-tool research. The master now separates immediate tasks, work waiting on specific inputs, optional ideas and completed history. Task numbers and historical evidence are preserved.

## What changed in plain English

The software that runs a small batch can now use the newer speaker rules or the date rules. Previously, these checks existed separately from that runner. It saves the proposed answer together with the exact original words and their source location. It keeps “unknown” separate from “this paragraph received no annotation.” It also retains a bad answer and the reason it was rejected, instead of publishing it as a supported result.

For example, an existing House-opening passage contains **“Monday, December 4, 1865.”** The saved test answer assigns that date to the House passage that follows. The preceding Senate paragraphs stay unknown. When we deliberately give the software a bad test answer that carries the House date backward into the Senate text, it rejects that answer and keeps the original reply for inspection.

This was a software connection/check using existing passages and test replies. It was **not a new AI experiment**. The date answers were already hand-written test examples. The speaker answer was replayed from a saved model proposal. Neither becomes a new human-approved historical label. We have not yet established that a real AI service will accept these exact requests or answer accurately.

## Inspectable results

- [Date results with their original passages](dates/run/proposals.json): two exact existing prepared windows; explicit date plus unknowns and exact source hashes/quotes/offsets.
- [Speaker results with their original passages](roles/run/proposals.json): one exact existing cross-page window and saved Qwen reply, replayed through the newer validator. Unannotated paragraphs are listed separately.
- [Rejected date carryover](boundary-negative/run/proposals.json): deliberately wrong test answer crossing the Senate/House boundary. [Full retained test reply and rejection](boundary-negative/run/summary.json).
- [Proof summary and file hashes](proof.json), [required project checks](gate.log), and [bounded Luna review](review.json).

Each prepared directory includes its exact inputs, original source records, selected output schema, prompt, source-review status and file-hash manifest. Results come from injected offline test callers; no provider client was constructed. Any model/provider names in these fixture configurations select the existing interface shape and are not evidence of an actual service request. Historical results were replayed for validation, not represented as compatible outputs for newly changed real requests.

## Implementation and checks

The existing `role_runner` and `role_run_io` accept explicit `role-v1` (default), `role-v2` and `scoped-date-v1` contracts. The prepared schema must equal the selected existing contract. Required prepared file hashes and exact packet-to-frozen-source correspondence are checked before executing. Contract, source-review/checks and validation-code hashes enter the run identity; changed inputs/contract/code refuse reuse. Original historical preparations and schemas stay unchanged.

`metadata_results.py` routes validation to the existing host contracts and creates source-linked proposal exports. Role exports retain original window text/hash/source anchor and original span identities/offsets, with request-local aliases alongside them; the window hash is not presented as a paragraph hash. Date exports reuse `source_mapped_dates`. `proposals.json` contains validated mapped results or explicit failure records; raw replies/usage remain in `summary.json` and the run journal. The existing command remains the entry point with optional `--contract`; no new wrapper, framework, scheduler or agent tool was adopted. Live requests retain all existing opt-in controls and still need named finite readiness/authorization.

Nine added focused tests cover both date packets, role-v2 paragraph-evidence unknowns, visible unannotated targets, preserved v1 unknown rules, source and manifest tampering, schema/contract mismatch, incompatible completed-result reuse and retained rejected raw replies. The full required gate passed **520 tests**, formatting, lint, type and complexity checks. A bounded Luna preparation/code review found no concrete regression; it is not the independent human-run verdict required before adopting a new workflow.

The portable proof ran two date cases, re-opened the same completed run with **zero extra test sends**, replayed one saved speaker answer and retained one deliberately boundary-invalid date answer. [Validation](validation.json) checks original source hashes, exported bytes, roadmap links and code identities. These prove host plumbing and normal completed-result reuse, not model accuracy or arbitrary-crash recovery.

## What is still ahead

T30 connects exact request/raw-reply checkpoints and conservative cumulative budgets to this metadata path and proves interruption/recovery in fresh test processes. The older role journal currently saves raw reply and parsed disposition together; it does not yet have the stronger reading journal's raw-before-validation guarantee. It also lacks cumulative unknown-budget reconciliation. Therefore this unit does not complete M2.4 or make this path ready for a new real run.

T31 then freezes a concrete finite real-job/compatibility manifest. A real service run, historical evaluation, search and a matched raw-versus-clean comparison remain separate work. M1/M2 remain PARTIAL; P0 and all existing human judgments stay open and unchanged.
