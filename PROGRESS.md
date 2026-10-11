# Progress and handoff

Updated: 2026-10-11. Read this before doing project work. Follow the ordered checklist below; preserve completed evidence and honor new user instructions. This file records execution state; `RUNBOOK.md` contains detailed findings and `README.md` contains usage. The user is conserving five-hour credits: avoid repeating analysis, provider POCs, or already passed checks without a concrete reason.

## Current outcome

The static-first, resumable one-command workflow is implemented. Small OpenAI and local Ollama POCs ran; **no full-corpus model run is authorized or has run**. Export validation establishes record/ledger consistency, not complete OCR correctness. The corpus still needs quality calibration and image review.

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
3. [ ] Before expanding cleanup, create human/image-reviewed labels across indexes, proceedings, Appendix, date transitions, and low-confidence text. Quantify router misses and false positives. Do not equate current model-assisted samples with gold labels.
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
