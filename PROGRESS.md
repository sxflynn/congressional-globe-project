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

## User-requested one-hour Qwen worker (started 2026-10-11 18:17 UTC)

The user explicitly asked Codex to run the documented long local job. Started `make run-qwen` against the existing `static-final-20261011` queue, with Qwen `qwen3.8:27b-mlx`, sequential requests, maximum 1,000 jobs or 3,600 seconds. Initial state: 686 completed, 238 review, 21,623 pending, zero claimed; both worker/request locks were available before launch.

- Execution handle: shell session **23933**; confirmed running with a job claimed.
- Log: `tmp/qwen-hour-20261011.log`.
- Live state: `make status`; inspect existing worker before starting another.
- Results save per job in the same `jobs.sqlite`; no queue recreation or provider switch. This is the newly authorized bounded production worker, separate from the earlier small POCs.
- [x] Session 23933 ended with exit 0. At 19:26 UTC status: 1,339 completed, 423 review, 20,785 pending, zero claimed; delta from launch: 653 completed and 185 review, 838 resolved. Detailed terminal report is being prepared from the saved log and read-only queue snapshot.
- [ ] After the worker exits, `make run-static` refreshes exports with accepted saved results. Published exports are not refreshed by `make run-qwen` itself.

Do not start another worker while this session is active. The user's OpenCode performance work under `tmp/performance/` remains untouched.

## Bounded local quality follow-ups (authorized 18:41 UTC)

The user authorized continued POCs and explicitly approved scheduled checks every 15 minutes for two hours, at most four additional isolated local POCs, each capped at 15 minutes/60 requests. No paid OpenAI calls or full-queue processing are authorized by this follow-up. Automation `congressional-globe-bounded-local-pocs` is active with eight 15-minute occurrences. Stop additional model experiments early on a quality plateau or unsafe accepted edits. Record the cumulative POC count here before launching each experiment so scheduled turns cannot exceed four.

- Additional scheduled POCs started: **2/4**, both terminal. Further model calls under this schedule are **stopped early** after the shared quality-gate failures and Gemma's accepted capitalization change/residual slash. Remaining scheduled checks should perform offline deterministic analysis, fixtures and review preparation only. Hour-long worker session **23933** is terminal, exit 0; no worker active.
- [x] Read-only cohort snapshot: 324 claimed IDs, 239 completed, 84 review, one claimed. Evidence: `artifacts/poc-quality-20261011/snapshot.json` and `samples.jsonl`; sampler: `tmp/snapshot_poc_quality.py`. Forty stratified samples cover all five parts, including ten completed zero-edit cases. All 30 completed sampled outputs replay their applied edits exactly; all ten sampled reviews retain raw responses. This establishes ledger consistency, not correction quality.
- [x] GPT-6 Luna text-context quality review of the 40 samples is saved in `artifacts/poc-quality-20261011/text_quality_review.json`: 24 accepted patches, 21 context-supported and three ambiguous (Pitts- burg → Pittsburgh, 19G9 → 1969, deleting ■). Fourteen completed records made no edits and may retain OCR artifacts. All ten review records withheld edits. No clearly meaning-damaging edit established, but these provisional findings do not establish corpus-wide safety or image correctness.
- [x] Run prepared isolated 12-case Qwen and Gemma challenges after the hour worker exited, with validated 900-second wrappers. Both score 6/12 exact overall and preserve three controls. Qwen offsets 0/6, correction targets 3/3; Gemma offsets 1/6, correction targets 2/3. Both fail the offset gate. Labels remain provisional; correlated examples/residual OCR are documented in the manifest. Further scheduled model calls stopped early; focus on offline fixes.
- [x] Add optional response finish reason/status to provider and benchmark records; preserve raw output and token usage on malformed/empty/truncated responses in benchmark errors. Explicit length/incomplete and other noncompleted Responses statuses fail closed. Prompt/model/token limits and queue schema remain unchanged. `make gate` passed with **88 tests**, typing, Ruff and complexity ≤5; evidence: `artifacts/poc-quality-20261011/metadata-gate.log`. Initial gate caught a mock protocol parameter mismatch, fixed before the passing run. No live provider calls for this code unit.
- [x] Extend parse-error metadata preservation to new production cleanup workers: ProviderOutputError raw output and usage persist in the review database record and response file, with finish reason/status in the result event. No queue schema changes. The active hour worker retains its already-loaded code; its earlier failures are not retroactively enriched.
- [x] Prepare `artifacts/poc-quality-20261011/human-review-packet.md` and `human-review-template.jsonl` with all 40 samples, before/after patches, source anchors and provisional findings. All human verdicts remain pending. Immutable original OCR is not embedded in the packet; retrieve it through the source anchors. No human or image verification has occurred.

The cohort resolved 323 jobs with 84 held for review (26.0%); it is predominantly early/index material, not a representative estimate of substantive debate performance. Snapshot durations total 1,250.607 seconds and available usage totals 246,032 input/29,094 output tokens. No local API charge; hardware/electricity are excluded. Published canonical/RAG files remain the earlier static snapshot until an explicit export refresh after the worker exits.

## TODO: reproducible model benchmarks with independent review

- [ ] Build a versioned benchmark suite with a predetermined task count and fixed source-anchored inputs, covering all five parts, substantive debate, indexes, difficult OCR, ambiguous cases and already-clean controls. Keep the same task set for comparing different Ollama models (Qwen variants, Muse variants and other installed candidates); record exact model tags, prompt/schema versions, parameters and input hashes.
- [ ] Run each candidate on the fixed tasks, saving original/static input, proposed and accepted output, patches, validation failures, review requests, raw responses, elapsed time, token usage and API cost. Keep failed and unchanged cases in the denominator; separate model proposals from what the workflow actually accepts.
- [ ] Have a different reviewer model evaluate a reproducible stratified sample of candidate outputs against the original input and source context. Include accepted edits, unchanged outputs and rejected/review cases; record sampling seed, inclusion rules and reviewer configuration. Use a shared rubric for correct repairs, missed errors, damaging edits, preservation of historical wording and appropriate uncertainty. Hide candidate identity where practical and retain the reviewer's evidence and uncertainty. Reviewer opinions remain provisional and must not automatically approve corpus changes.
- [ ] Provide a human review packet with before/after text, highlighted edits, source citations and model review findings. Allow the human to verify the entire benchmark or selected samples and adjudicate disagreements. Store versioned human labels and the rubric used; measure performance against those human standards, reporting human-reviewed coverage separately from model-only review. Text-context labels are not image-verified gold; ambiguous cases remain explicit.
- [ ] Produce a compact comparable scorecard: correct accepted repairs, unsafe accepted edits, residual misses, unchanged-control preservation, review/failure rates, reviewer/human disagreement, runtime, throughput and cost. Report sample sizes and uncertainty; avoid ranking models from differently configured task sets. Preserve a held-out human-reviewed set for regression checks so prompt tuning does not overfit the evaluation examples.

This is a planned evaluation workflow, not an implemented benchmark or a new model run. Next executable step: define the task manifest and human/reviewer rubric using the saved POC evidence before adding an independent local reviewer stage. Local review calls must share the existing sequential Ollama lock and stay within the authorized bounded POC budget; paid calls require separate authorization.

## Before/after events in streaming worker logs

- [x] New worker runs emit `job_result` events with `before_text` (exact statically cleaned model input), `after_text`, and accepted `applied_edits`. Include run/job IDs, composite identity, item/part/leaf/printed-page/hOCR/line/geometry anchors, model, status, timestamp and duration alongside existing lifecycle/heartbeat events.
- [x] Label accepted output as `accepted_normalized`; review/retry events show unchanged retained input as `unchanged_retained_input` with zero accepted patches. Unaccepted proposals remain in the separate raw response, with reason/status metadata. Immutable original OCR remains available through source references.
- [x] Focused mocked checks cover persisted completion, no-op, parse rejection and retry event behavior, accepted patch lists and citations. `make gate` passed: Ruff formatting/lint, ty, complexity ≤5 and **90 tests**. Evidence: `artifacts/poc-quality-20261011/result-events-gate.log`. No live provider calls or production queue writes occurred for implementation checks.

User logging feedback is implemented for subsequent workers. The active Qwen hour log/worker retains its loaded code and is unchanged. Human verification and broader benchmark quality calibration remain pending.

## Scheduled check at 18:56 UTC

Confirmed hour worker session 23933 remains active; process PID 9437 at approximately 39 minutes elapsed, with one claimed job. Read-only queue snapshot: 1,151 completed, 370 review, 21,025 pending (22,547 total). No additional isolated local POCs started (**0/4**). Read-only process inspection required elevation because sandboxed `ps` was denied; it succeeded without changing the worker.

Completed offline benchmark-metadata instrumentation and human-review scaffolding while local requests remain serialized. The sampled possible Pittsburg/Pittsburgh overcorrection, mixed alphanumeric index correction and marker removal require adjudication before any claim of a brilliantly reliable full-corpus path. Next step: inspect session 23933 on the next scheduled check; once terminal, save its outcome, run the prepared isolated Qwen challenge with a 900-second outer deadline, count it as POC 1/4 before launch, then review every challenge result against its provisional manifest. Do not refresh exports or start a second worker while the hour worker holds the run lock. Before/after streaming events remain an unchecked implementation task.

## Scheduled check at 19:11 UTC

Hour worker session 23933 remains active; elevated process inspection confirmed PID 9437 at 54 minutes elapsed. Queue snapshot at 19:16 UTC: 1,324 completed, 420 review, 20,802 pending, one claimed. Additional isolated POCs remain **0/4**. GPT-6 Luna delegates completed the before/after logging implementation, bounded challenge wrapper preparation, and read-only safeguard analysis. Required gates passed with 90 tests; no overlapping provider requests or export refresh started.

`artifacts/poc-quality-20261011/safeguard-analysis.json` analyzed 542 accepted patches from 634 completed jobs in a captured 809-job hour cohort: 128 differed from an exact hyphen/whitespace join, eight converted digit-dominated mixed strings to numeric text, nine removed symbols. These heuristic flags are **not confirmed harms**; preserved compound hyphens and legitimate glyph repairs can also be flagged. They support evaluating targeted static/review rules before scaling, not blanket rejection or historical spelling normalization.

Next check: confirm session 23933 is terminal and no job remains claimed, record hour totals, then execute the prepared isolated challenge with the deadline wrapper. Keep the production queue intact. Use `uv run python` for the wrapper; preserve its durable copy and dry-run/timeout evidence under `artifacts/poc-quality-20261011/challenge-preparation/`. New benchmark calls now capture finish reason/status; historical hour-worker records do not.

The wrapper is ready: Pydantic v2 validates plan/cases/manifest and benchmark records; its own child receives 895 seconds plus five seconds for termination. Dry-run, harmless timeout self-test, Ruff and ty passed; no model requests. After checking worker termination and reserving POC **1/4** in this file, execute:

```bash
UV_CACHE_DIR=/private/tmp/congressional-globe-uv-cache uv run python tmp/run_bounded_challenge.py \
  --model qwen3.8:27b-mlx \
  --run-id qwen-offset-challenge-20261011-run1
```

Run evidence goes to `challenge-preparation/runner-evidence/`; results go to `challenge-preparation/runs/<run-id>/`. If the scratch script is missing, use the identical durable `challenge-preparation/run_bounded_challenge.py`. Do not repeat an existing run ID or launch this while another local request worker is active.

## Scheduled check at 19:26 UTC: hour terminal and paired challenges

- [x] Reconcile the hour log's 838 unique claims against read-only SQLite: 653 completed, 185 review, no missing rows/duration mismatches; terminal queue 1,339 completed, 423 review, 20,785 pending, zero claimed. Session 23933 exited 0. Report/log: `artifacts/poc-quality-20261011/hour-terminal-report.json` and `qwen-hour-20261011.log`.
- [x] Recorded request durations sum to 3,589.441 seconds; exact shell wall time is unavailable. Usage exists for 817/838 jobs: partial totals 627,268 input and 87,196 output tokens. Review fraction is 22.1% of resolved jobs. At this cohort's mean request duration, processing the 20,785 pending jobs projects about **24.7 hours**, excluding review/retries/export/hardware and assuming the same workload mix. The queue CLI's 19.75-hour estimate uses completed-job timing and excludes review timing; neither is a whole-corpus guarantee. Local API charge is $0.
- [x] POC 1/4 `qwen-offset-challenge-20261011-run1`: session 73819, exit 0, 59.56 seconds wall, 8,747 input/1,324 output tokens; 6 accepted exact, six anchor-validation failures, controls 3/3 unchanged.
- [x] POC 2/4 `gemma-offset-challenge-20261011-run1`: session 81392, exit 0, 55.17 seconds wall, 8,991 input/765 output tokens; eight accepted but only six exact, four validation failures, controls 3/3 unchanged. Accepted nonmatches include `War` → `war` with a residual backslash and a missed wrap correction.
- [x] Review every case and save per-run `comparison_report.json` plus `challenge-preparation/paired_comparison.json`. Both use identical inputs/prompts and provisional labels. Both fail the offset threshold (Qwen 0/6; Gemma 1/6, required ≥5/6). Qwen matches three correction targets; Gemma two. All 24 responses finish with `stop`, so these failures have no truncation signal. Both isolated runs leave the production queue unchanged and cost $0 in local API charges.

**Stop condition reached:** no further model requests under this scheduled effort. Do not spend the remaining 2/4 capacity repeating providers or weaken exact-source validation to improve scores. Remaining checks can evaluate deterministic repairs, source-span contracts and focused offline fixtures. Published canonical/RAG outputs remain the earlier static snapshot; no export refresh occurred.

Next executable work: inspect the delegated static-rule analysis of these cases, then evaluate a narrowly guarded resolver/static repair on cloned fixtures only. Two repeated Leavenworth cases might permit atomic all-occurrence recovery, but that covers only 2/6 failures; nonexistent continuations, misquoted newline/tab/backslash anchors and historical capitalization must remain protected. Do not first-match or salvage partial proposals. Human reference labels remain pending; full-corpus readiness is not established. Required code gates remain the passing 90-test run from the preceding unit; this unit changes documentation/evidence only.

- [x] Save `challenge-preparation/configuration-note.json`: exact prompt/schema and hashes, cases/manifest/source hashes, Git revision, SDK version and all request/deadline settings. Model tags remain mutable; weights digests were not queried. No human/image gold labels.
- [x] Provider-free six-record static pilot: `artifacts/poc-quality-20261011/static-wrap-poc/challenge-six-report.json`. A cloned lexicon with explicit `alexandria` and `leavenworth` produced four geometry-anchored wrap edits across three records; terminal `rail-` remained untouched. Other cases require internal spacing/glyph repairs and stayed unchanged. Production sources, lexicon, queue and outputs were untouched.
- [ ] Prefer reviewing those two finite lexicon additions over a broad ambiguous-offset fallback. Check historical spelling and negative controls, measure affected candidate coverage and sample proposed static fixes before adopting. Changing the production lexicon changes the run fingerprint; do not mutate the existing compatible run or discard its saved results. Plan any migration/export refresh explicitly. Further model calls remain stopped under this schedule.

## Scheduled check at 19:41 UTC: static coverage and corrected estimates

- [x] Stream all 296,995 existing derived static rows to measure the two-form candidate lexicon, without re-parsing raw sources or rebuilding the pipeline. `artifacts/poc-quality-20261011/static-lexicon-coverage/coverage-summary.json` records input/candidate hashes and per-part counts. Candidate additions resolve 110 hints with 110 patches in 98 paragraphs: affected/patches by part are 15/17, 15/17, 12/14, 35/39 and 21/23. Routing clears for 79; 19 still have other OCR signals. This measures a fresh candidate replay, not 79 removed jobs from the current partially processed queue.
- [x] Fixed-seed sample (3911866), six paragraphs per part: `affected-sample.jsonl`. An independent Luna agent reviewed 34 new patches in 30 paragraphs against raw letters and hOCR adjacent-line/word geometry. All preserve letters/case, all ledgers replay exactly, zero sampled ambiguous/unsafe findings. `sample-review.json` records the evidence and limitations. The other 68 affected paragraphs remain unreviewed; no scan-image/human gold labels.
- [x] Five negative fixtures remained unchanged: Pitts-burg, unknown compound, terminal rail-, literal backslash/tab and already joined forms. Production lexicon, queue and outputs remain unchanged; candidate additions are not adopted.
- [x] Fix `make status` timing: means use observed nonnegative durations only, completed+review durations inform pending-work estimates, and manual-review backlog is excluded from the estimate. New fields: `average_resolved_seconds`, `timed_resolved_jobs`, `estimated_pending_hours`; legacy `estimated_remaining_hours` aliases the pending estimate. Existing counts/remaining/percent meanings stay the same. Missing timing data yields null for outstanding work; no outstanding model work yields zero.
- [x] `make gate` passes: Ruff formatting/lint, ty, complexity ≤5 and **93 tests**. Gate evidence: `static-lexicon-coverage/eta-gate.log`. Read-only live status after the fix: 1,339 completed, 423 review, 20,785 pending, zero claimed; 1,762 timed resolved jobs average 4.07 seconds, estimating **23.51 hours of pending model processing**. This broader historical sample differs from the hour cohort's 24.7-hour projection; both exclude manual review, retry/export overhead and changing workload/provider mix.

No provider requests or production corpus changes in this unit. Model POC count remains **2/4, stopped early**; no model worker is active. Next executable step: decide the versioned candidate-lexicon rollout and compatibility/migration path on cloned fixtures, using this coverage/sample evidence. Keep the existing prepared lexicon and compatible queue intact; a changed preprocessing fingerprint must not reset or silently discard saved jobs. Do not broaden correction rules or certify the corpus from these samples.

## Scheduled check at 19:56 UTC: static opportunities and rollout design

- [x] Delegate offline investigations to three GPT-6 Luna agents. Elevated process inspection found no cleanup/benchmark worker or Ollama runner. Read-only production status remains 1,339 completed, 423 review, 20,785 pending and zero claimed; estimated pending model time remains 23.51 hours. Additional model POCs remain **2/4, stopped early**. No provider calls, queue writes, production lexicon changes or export refresh.
- [x] Verify rollout behavior against code: changed lexicon/configuration fingerprints require a new run ID. Existing runs retain their saved results, but there is **no implemented cross-run result migration command**. `artifacts/poc-quality-20261011/static-lexicon-coverage/rollout-plan.json` records isolated static validation commands and the proposed compatibility/reuse unit. Those commands were not run. Reuse would require exact identity/input matches, source integrity checks, current patch validation and preserved old-run provenance; never silently copy results or reset the old queue.
- [x] Save `artifacts/poc-quality-20261011/span-contract-proposal.json`, explicitly **not implemented**: host-generated source-span candidate IDs and constrained replacement choices would remove model-generated offsets. Reject stale, unknown, duplicate, missing or conflicting decisions atomically; preserve existing patch validation and unsupported continuations. This design needs offline fixtures before any provider evaluation and does not establish historical correctness.
- [x] Inventory residual line-end wrap hints in the existing derived corpus: 17,902 paragraphs, 21,980 hints, 8,730 distinct alphabetic forms. `static-lexicon-coverage/candidate-inventory.json` ranks 20 hypotheses using intact-word evidence, per-part counts and anchored examples. All 20 fail current lexicon membership; all 40 retained examples repair successfully with temporary candidate entries and matching source spans/adjacent-line geometry. There is no OCR-confidence threshold in this normalizer. Two examples per form do not validate every occurrence or establish job savings.
- [ ] Review ordinary/legal forms first: conferred, postponed, bounties, commenced, supplies, preemption, recommitted, declaring, excluded, securities, salaries and enemies. Keep compound/spelling questions explicit (especially preemption). Proper names/places require separate contextual evidence: Morrill, Hubbell, Patterson, Ashley, Washburn, Oregon, Shellabarger and Woodbridge. Nothing from this inventory is adopted yet.

Next executable unit: build a cloned candidate lexicon for a small reviewed subset of ordinary forms, measure actual routing changes, and inspect a seeded sample across all five parts plus negative controls. Preserve the earlier two-form evidence; do not repeat model benchmarks. Then implement and verify compatible-result reuse on synthetic/cloned queues before adopting changed preprocessing. Source-span response contracts remain a separate proposed improvement. This check changes documentation/evidence only; the latest code gate remains the passing 93-test run. README operator commands are unchanged.
