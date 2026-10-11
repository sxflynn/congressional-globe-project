# Progress and handoff

Updated: 2026-10-11. Read this before doing project work. Follow the ordered checklist below; preserve completed evidence and honor new user instructions. This file records execution state; `RUNBOOK.md` contains detailed findings and `README.md` contains usage. The user is conserving five-hour credits: avoid repeating analysis, provider POCs, or already passed checks without a concrete reason.

## Current outcome

The static-first, resumable one-command workflow is implemented. Small OpenAI and local Ollama POCs ran; **no full-corpus model run is authorized or has run**. Export validation establishes record/ledger consistency, not complete OCR correctness. The corpus still needs quality calibration. Original-image visual validation and re-OCR are outside the newly clarified immediate scope.

## Completed

- [x] Preserve all five parts, raw source text, source anchors, hOCR IDs, geometry, and correction provenance.
- [x] Add ignored `tmp/` scratch folder with tracked `.gitkeep`; keep durable evidence under ignored `artifacts/`.
- [x] Use `npx prettier@3.9.10` without `--yes`, with elevated permissions.
- [x] Run full static audit: 15 source derivatives, 5,412 pages, 296,995 paragraphs; baseline elapsed 260.849 s.
- [x] Create reproducible random audit samples: 300 baseline patches, 150 flagged paragraphs, 100 unflagged paragraphs, 100 supplemental patches; seed 3911866, stratified by part.
- [x] Review samples with GPT-6 Luna delegation. Text-context verdicts are provisional; no scan-image gold labels. Preserve ambiguous compounds.
- [x] Add reviewed 44-form static lexicon supplement: 7,545 additional patches, 5,575 fewer candidate requests (19.9%) under the earlier router.
- [x] Rerun stricter mixed-letter/digit router: 22,547 candidates over supplemental static output (68 additional flags).
- [x] Benchmark five contextual problems and three controls with mini, Qwen, Gemma; retest mini punctuation preservation. No further POC repetition is needed for this unit.
- [x] Add punctuation/numeric safeguards, unsafe legacy-result revalidation, atomic materialization, and shared sequential Ollama request lock.
- [x] Fix extraction to preserve hOCR block order; remove pixel threshold that interleaved columns.
- [x] Export sourced date/chamber facts, scoped from their heading onward; retain unknown/conflicting facts and review reasons.
- [x] Verify bounded one-command export and provider switching without recreating queue: 20 pages, 1,035 paragraphs, 73 chunks, 85 jobs; three Qwen then three mini requests. Final status: 79 pending, five review, one completed, zero claimed.
- [x] Independently replay bounded static/AI ledgers; check source equality, coverage, Pydantic models, anchors, geometry, heading order, export hashes.
- [x] Run required code gates: Ruff format/check, ty, complexity ≤5, pytest **81 passed**. Markdown formatting is required again after final status edits.

## Runs and evidence

| Path under `artifacts/` | Purpose and state |
| --- | --- |
| `runs/static-full-audit-20261011/` | Historical full extraction/static audit, plan-only. Do not resume it with changed preprocessing. |
| `static-audit-20261011/` | Samples, reviews, source fingerprints, supplemental lexicon/output, current-router count. |
| `benchmarks/context-audit-20261011/` | Eight-case provider comparisons, one-case mini retest, anchors and raw results. |
| `runs/e2e-final-20261011/` | Terminal bounded POC queue, exports, provider reports, `independent_verification.json`. No worker active. |
| `runs/static-final-20261011/` | Terminal full static-only canonical/RAG export; built-in validation passed. |

Scratch verification scripts: `tmp/verify_final_poc.py` and `tmp/verify_full_export.py`. Copy durable scripts into the corresponding artifact run when finished. Scratch logs: `tmp/e2e-final-{static,qwen,mini}.log` and `tmp/static-final.log`. Large artifacts are intentionally uncommitted and exist on this machine; do not assume a fresh clone contains them.

## Time, cost, and limitations

Eight-case projections for 22,547 sequential candidates: mini **9.0 hours / $18.53**, Qwen **40.7 hours / $0 API**, Gemma **33.1 hours / $0 API**. These are tiny, purposive-sample extrapolations. Retries, image review, export overhead, local electricity/hardware are excluded. The harder bounded POC took 50.44 s for three local requests plus export versus 7.99 s for three mini requests plus export; five results required review. Actual full-run time and quality may differ substantially.

Qwen agreed with all eight provisional expected outputs; Gemma missed one glyph error; mini had six accepted agreements, with two held for review. The revised mini prompt passed the one-case index retest. A completed job means its accepted patches passed validation, **not that all paragraph errors were corrected**. Unflagged text is not certified clean. Low-confidence flags are broad and must not all be sent to a model automatically.

Raw IA metadata files are unavailable locally for all five parts and explicitly recorded as unavailable. Date/chamber facts are conservative; they are not inferred across scan leaves. Historical audit counts used earlier extraction/classification code; the final static export counts must be reported separately.

## Ordered next steps

1. [x] Finish full static export and save `terminal_report.json`: 5,412 pages, 296,995 paragraphs, 19,803 RAG chunks; built-in validation passed.
   - [x] Independent full verification passed: all source identities/raw text, 209,609 static patches, Pydantic records, output hashes, and all 15 raw source fingerprints. Evidence: `artifacts/runs/static-final-20261011/independent_verification.json`.
2. [x] Format all Markdown, check `git diff --check`, and commit implementation/user changes: `24ba80d`. Repeat formatting and commit for later handoff corrections.
3. [ ] Before expanding cleanup, define reviewed text-context evaluation labels across indexes, proceedings, Appendix, date transitions, and low-confidence text. Quantify router misses and false positives; preserve ambiguity. Do not equate model-assisted samples with verified historical facts or image gold. Re-OCR/original-image visual validation is outside current scope.
4. [ ] Evaluate further static repairs on anchored examples, retain ambiguous compounds, then measure reduction and review a new random sample before adopting each rule.
5. [ ] Only after a new explicit user command, process a bounded additional model sample or scale the residual queue. Inspect queue status first; reuse compatible run IDs and matching provider benchmarks. Never automatically drain the full queue as a continuation of this handoff.
6. [ ] Profile Python CPU utilization and evaluate multi-core multiprocessing and threading: user observes about 99% CPU on one Mac core. Measure extraction, static cleanup, JSON/Pydantic serialization, SQLite merge, and export separately; compare process workers for CPU-bound work and threads for I/O. Preserve bounded memory, deterministic source/paragraph order, validation, and edit ledgers. Keep Ollama requests strictly sequential. Benchmark before adopting concurrency.
7. [ ] Optional future work: obtain/preserve raw IA metadata with sources, integrate Batch with the same SQLite queue if needed, add a dashboard only if CLI status proves insufficient.

## Exact resume commands

Static-only full output command (safe from model calls):

```bash
UV_CACHE_DIR=/private/tmp/congressional-globe-uv-cache uv run globe static-first \
  --root . --run-id static-final-20261011 \
  --lexicon artifacts/static-audit-20261011/supplemented-lexicon.txt \
  --backend none --ai-limit 0
```

First inspect state if resuming model work later:

```bash
UV_CACHE_DIR=/private/tmp/congressional-globe-uv-cache uv run globe cleanup status \
  --run-directory artifacts/runs/e2e-final-20261011 --run-id e2e-final-20261011
```

The bounded POC used `--start-leaf 114 --page-limit 4`; those inputs must stay identical when resuming it. Provider changes retain the same queue. Preprocessing/lexicon/source changes require a new run ID. `--ai-limit` omitted with a provider drains the pending snapshot, so **keep a bounded limit unless the user explicitly authorizes scaling**.

## Final handoff state

Implementation and user changes are committed; timed Qwen worker and composite lookup indexes are implemented. Full static export finished successfully (session 38960, exit 0), with 5,412 pages, 296,995 paragraphs, 19,803 chunks, 22,547 pending model jobs, and zero model requests. Cached resume/export took 447.34 seconds; this excludes the earlier extraction and interrupted slow lookup attempt. Built-in validation passed. Date remains unknown on 5,321 pages and chamber on 5,173; 152,889 records carry review reasons. Raw IA metadata remains unavailable.

The independent full verifier finished successfully (session 78974, exit 0) before the stop request reached it. Its terminal log and `independent_verification.json` confirm all 209,609 static patches replay, complete source coverage, output hashes, and all 15 raw source fingerprints. No Codex workers remain active. Work is paused at the user's credit-conservation wrap-up request; the OpenCode performance agent and any user-started Ollama worker are separate.

## Operator's one-hour Qwen command

Requested by the user for them to run manually; do not automatically start it:

```bash
uv run globe cleanup run --run-directory artifacts/runs/static-final-20261011 \
  --run-id static-final-20261011 --backend ollama --model qwen3.8:27b-mlx \
  --limit 1000 --max-seconds 3600 --progress-interval 30
```

The time budget is checked between requests, so the last request may extend beyond one hour. Inspect `cleanup status` first. Rerunning continues the same queue. Afterward, the static-only resume command above refreshes canonical/RAG exports using saved accepted patches and preserves review records. The user has asked for this command; no hour-long worker was started by Codex.

## Concurrent performance investigation

The user has another agent (OpenCode) working in `tmp/performance/` to test performance. That directory belongs to its ongoing investigation: do not edit, clean, delete, or commit its files. Coordinate through the user before overlapping performance work. Review its findings when available before implementing the multi-core checklist item; do not assume its experiments are validated production changes.

## Reviewed OpenCode performance POC

Read `tmp/performance/PARALLELIZATION_PROPOSAL.md` and supporting logs. Independently hashed parallel canonical/chunk outputs: both exactly match the published production hashes. Preserved the report, five logs, and review under `artifacts/performance-review-20261011/`; no benchmark or model calls were rerun, and no files under `tmp/performance/` were changed.

Reported full-corpus sequential → parallel timings with 14 process workers: extraction 148.580 → 18.367 s; static cleanup 45.845 → 6.734 s; routing 34.327 → 4.882 s; materialization 67.269 → 6.593 s; merge 216.369 → 33.865 s; RAG 50.492 → 7.402 s. Summed stages project 563.5 → 78.5 s (7.18×); this is not a measured complete workflow invocation and excludes some orchestration/validation overhead.

- [x] Read external performance POC and confirm final output hash equivalence independently.
- [ ] Integrate opt-in process workers into production after authorization; preserve sequential compatibility, ordered output, bounded memory, source fingerprints, run locking and staged validation. Test completed/review/legacy jobs, worker failures, and unmatched/duplicate records before claiming production readiness. Full-scale materialization evidence covers a pending-only queue. Keep Ollama strictly sequential. Do not rerun a sequential golden pipeline on every production run merely to establish hashes, since that would erase much of the speedup; use verified baseline comparisons during rollout and retain runtime integrity checks.

The performance checklist now has strong POC evidence; production adoption remains pending. Threads are not the primary approach for the CPU-bound stages on the reported GIL-enabled Python build.

## Updated project goal and architecture (2026-10-11)

The user expanded the long-term goal to a portable, model/framework-independent historical research corpus. `PROJECT_GOAL.md` records the end state, research questions, current-schema support and gaps, layered data products, proposed metadata/call-audit contracts, stage design, retrieval semantics and phased roadmap. `AGENTS.md` now requires architectural decisions to follow it; README/RUNBOOK are aligned. This unit changes documentation only; no enrichment pipeline, historical assignments, model calls, re-OCR or image-validation runs were performed.

- [x] Update the project goal and map existing contracts to future requirements.
- [x] Define canonical vs authority vs enrichment vs retrieval/index responsibilities, temporal affiliations, speaker/mention distinction, evidence/version semantics, unknown/mixed filters, reproducible call auditing and independent reprocessing requirements.
- [ ] Next architectural unit when requested: formalize versioned collection/release/identity/evidence/assertion and call-audit schemas with compatibility/migration examples and synthetic fixtures for the representative research questions. Keep the reliable corpus and verified multiprocessing rollout as near-term engineering work; the enrichment roadmap is not an automatic instruction to implement everything.

The project's architectural goal in repository documents is updated. The documentation update did not implement the broader enrichment roadmap. The desktop cleanup/workflow goal retains its original objective; the later completion audit below addresses that implemented workflow, not all future enrichment.

## Final cleanup workflow audit and operator path

- [x] Recheck original workflow goal against actual code, saved small-provider POCs, full static and bounded AI exports, independent verification scripts/results, and current artifact/source hashes. All 15 raw source fingerprints and both runs' published output hashes still match. Required code gates pass on the current tree: Ruff format/lint, ty, complexity ≤5, **81 tests**. No new tests added for this audit.
- [x] Add `HAPPY_PATH.md` with the full one-command opt-in workflow, one-hour Qwen worker, export refresh, current limitations, and comparative sample timing/cost/validation results. The human starts production processing; do not run it automatically.
- [x] Test one additional installed candidate, Muse Glimmer, on eight cases only: 71.273 s, five schema/JSON failures, one accepted miss, two exact control agreements. $0 API charge; usage available for only three valid responses. Preserve results under `artifacts/benchmarks/context-audit-20261011/providers/context-random-muse-20261011/`. No model calls were made against the production queue. Qwen remains the preferred local POC candidate; Mini is the faster paid candidate, subject to validation/review.

Queue snapshot at this audit: `static-final-20261011` has 686 completed, 238 review, 21,623 pending, zero claimed. These additional saved results appeared outside Codex's POCs; the existing canonical/RAG export is still the earlier static snapshot, not a refreshed representation of this live queue. Locks were available before the isolated Muse benchmark; that benchmark is now terminal (session 61112, exit 0). No Codex model worker remains active. No full-corpus worker was started or queue recreated in this unit. Current local model inventory has Qwen, Gemma and Muse; a specific Meta Llama benchmark requires a specified available model.

The original deliverable is the implemented, exercised cleanup workflow and operator command, not a claim that every historical paragraph is clean or that future enrichment is finished. Evidence for the completion audit is saved in `artifacts/workflow-completion-audit-20261011.json`. Remaining quality calibration, multiprocessing production integration, and the `PROJECT_GOAL.md` enrichment roadmap stay unchecked.

## Basic Makefile entry points

- [x] Add a small literal-command Makefile: `gate`, `run-workflow` (static alias), `run-static`, `status`, `run-qwen`, `run-gemma`, and `run-openai`. No variable matrix. Model workers inspect status first, reuse the existing queue, and are bounded to one hour/1,000 requests. Make recipes are serialized.
- [x] Document targets and static → model worker → static export refresh in README, HAPPY_PATH and RUNBOOK; AGENTS now directs agents to `make gate`.
- [x] `make gate` passed: both formatters, Ruff format/lint checks, ty, complexity ≤5, and all 81 tests. Dry-ran every workflow target with `make -n`; no production worker started and no corpus regeneration performed. Gate log: `tmp/make-gate.log`; session 23129 exited 0.

## Human-oriented README tutorial

- [x] Replace the long README with a focused four-step tutorial: install dependencies, prepare static outputs/queue, choose an optional local/cloud worker, then refresh/find results. Keep architecture, internal schemas, benchmark detail and agent-specific instructions in their dedicated documents.
- [x] Document prerequisites, local endpoint/model names, first-time `.env` setup, one-hour/1,000-passage limits, resumability, status meanings, output files and `make gate`.
- [x] Add a linked macOS word-list setup section to RUNBOOK for fresh checkouts. Compared reconstruction against the existing prepared lexicon in memory; bytes match. No source files, queues, outputs, or performance-agent files changed; no model requests or production runs started.

Documentation-only unit; Markdown formatting and diff checks run before commit. No code/test changes.
