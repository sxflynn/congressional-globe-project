# T11: explicit pickup evidence validation

2026-10-26, Codex GPT-6. Parent M2.2. Implements the outstanding T8 source/request/reuse/budget/binary checks within the approved read-only status/verify scope. No model, network, image fetch, corpus edit, review application, helper rebuild or launch. M2 general recovery and the research-quality/P0 decisions remain open.

## What this adds

`globe reading status` and `globe reading verify` accept optional `--evidence PATH` for an explicit inspection recipe. [The named recipe](inspection.json) pins the selected journal config SHA-256 and declares exact existing artifacts, prior journal configs and runtime/counter paths. This is a read-only verification input, not a new run configuration or an authorization document. Without it the earlier unresolved-evidence behavior remains fail-closed. No latest-directory guessing, auto-discovery, repair, retry or execution wrapper was added.

The host validates the recipe with strict Pydantic v2. It requires the six primary input paths/hashes to match the immutable journal config, verifies recorded code hashes, reconstructs every exact request using existing image/model validators, verifies cached image geometry/receipts, compares full raw target and surrounding-context messages against typed frozen candidates, validates controls, and checks exact count coverage/model/unit/image/context/output-reserve arithmetic. It checks frozen protocol/source-expectation/review evidence through existing pure validators. Current `valid` replies are replayed through existing response, token-parity, patch/source and control validators; historically `invalid`/failed/timeout rows remain preserved outcomes, not silently repaired or relabeled.

Exact reused request records must match the main and prior manifests. Saved attempt identity/status/time/request fields must match the actual prior journal and its hash-bound terminal export, including the exact raw reply. Reuse consumes no new current attempt. All declared journals are read via private database/WAL copies, with source size/mtime stability checks. Current status/verify evidence uses one selected journal snapshot; no store initializer or provider transport is invoked.

Cross-run accounting deduplicates identical attempt UUID/row/call-cap references. Conflicting rows under one UUID fail. Distinct attempt UUIDs are still charged independently, even if their requests are identical. Missing elapsed time or absent replies reserve the recorded full per-call cap, taking the larger of that cap and observed elapsed time. Missing reservations fail; unknown token usage remains explicit and known input/output counts are separately summed. The result checks recorded prior narrative totals/model totals and cumulative call/time/model limits against the hash-bound budget artifact. Remaining allowance is deliberately null: historical accounting does not authorize spending.

The runtime executable and token-counter executable are each compared to their own recorded build SHA-256. Reports name both artifacts with expected/actual hashes. Matching one does not satisfy the other or prove runtime/source parity. Current process/queue observations remain unknown and launch readiness is always false. Review counts use a private copy of an explicitly named review database; no answers are applied. Master action/ownership provenance is hash-bound, plan-file age is labeled as file age, and actual checkpoint age stays unknown where no machine timestamp exists.

## Named historical run

[Two-process CLI proof](named-run.json), using `reading-quote-expansion-run-20261025-01` plus the two declared preceding journals:

- All36current request/model/source/image/count/protocol/review bindings pass;4reused requests resolve exactly;23typed source candidates are verified against their saved source/image mappings.
- Twelve prior plus36current attempts give **48 attempts /3,693.789876conservative request-seconds**. The prior recorded sum is879.895082seconds; conservative reservations raise it to908.877108seconds. All9unknown token-usage attempts remain explicit. Current known input/output usage is137,216/25,692tokens; cumulative known usage is169,973/33,837tokens.
- Status is informational (exit0); verification correctly exits1. Failures are the already-observed per-call elapsed overrun and a real counter-program hash mismatch. The runtime matches `e5c7c0f…e19e6b`; the counter expected `ff49c601…c08f41`, while the current file is `74b2046d…f7976`. No binary was replaced/rebuilt or historical evidence edited to manufacture a pass.
- Both JSON reports remain under8,192UTF-8bytes including newline. The proof measures command/output bytes without inventing a prior timed baseline. All286inspected original files, including three run directories, declared artifacts, cached image bundles, review database and both executable files, retained exact SHA-256 values.

These are engineering consistency checks. They do not certify OCR fidelity, human labels, full corpus coverage, binary/source tokenizer parity, arbitrary-crash recovery or fresh launch readiness. The recorded budget limits are verified as historical evidence, not newly granted authority. An inspection recipe is supplied by the operator and is not a signed human approval. Mutable-source/hostile-writer atomicity across every external artifact is outside this offline snapshot guarantee.

## Checks and next work

Thirty new portable synthetic cases cover a complete passing historical-binding fixture, duplicate prior references, missing files, wrong run identity, changed runtime/counter hashes, stale narrative budgets, cumulative overrun, exact reuse, source/context/control tampering, token arithmetic/model mismatch, conservative unknown usage, conflicting attempt UUIDs, valid-reply replay, retained invalid replies, in-flight work, bounded failure exits, review copying and unchanged originals with network/store initialization blocked. Together with19existing T8 cases,49focused tests pass. Synthetic fixtures create real cached geometry/receipts locally through a fake downloader; no service/model is involved and no ignored historical artifact is required by these tests.

Full gate results are in [gate.log](gate.log). The parent M2 remains PARTIAL: T12 is the next bounded proof of interruption and second-process recovery using synthetic fixtures and zero provider calls.

Full gate passed: **480 tests**, Ruff formatting/lint, ty, complexity≤5 and the required elevated Markdown formatter. Final CLI output sizes are5680bytes for status and3106bytes for verification, both including newline. Validation/code hashes: [validation.json](validation.json).
