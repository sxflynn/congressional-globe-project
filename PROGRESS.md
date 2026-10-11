# Progress and handoff

Updated: 2026-10-11. Read this before doing project work. Follow the ordered checklist below; preserve completed evidence and honor new user instructions. This file records execution state; `RUNBOOK.md` contains detailed findings and `README.md` contains usage. The user is conserving five-hour credits: avoid repeating analysis, provider POCs, or already passed checks without a concrete reason.

## Current outcome

**Active priority: V2_PIVOT exploration, requested by the user.** Read [V2_PIVOT.md](V2_PIVOT.md). Preserve the completed cleanup work while testing whether unchanged OCR plus organization and separate evidence-linked metadata can support useful research retrieval and answers. The earlier scheduled cleanup-model stop remains in effect for that effort; this is a separate experiment. No pivot decision or full enrichment run has been made.

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

## V2_PIVOT: active exploratory work

- [x] Preserve existing cleanup outputs, queue and implementation; current baseline commit `c414db9`.
- [x] Create `V2_PIVOT.md`, linked from agent instructions, with alternative architecture, experiment controls, unknown/mixed metadata rules and decision criteria. This is an unvalidated hypothesis, not an adopted replacement.
- [ ] Luna `static_review`: prepare ten source-anchored raw/static window pairs (two per part), provisional queries/labels and forty distractor windows, deterministic seed 3911866. Own evidence under `artifacts/v2-pivot-20261011/`; no production mutations.
- [ ] Luna `benchmark_harness`: prepare isolated, explicit opt-in local Qwen experiment, at most twenty requests sequentially, 45-second request timeout and fifteen-minute outer deadline. Validate schemas, exact quote evidence, model configuration and audit outputs. Prepare offline lexical retrieval comparison; do not present it as vector-search validation. No paid API calls.
- [ ] Run offline preparation checks and review samples before launching local evaluation. Record exact command, run ID, live process/session and outcomes here. Then inspect accepted, failed and abstained cases before deciding the next POC.
- [ ] Compare raw/static retrieval ranks, grounded answers and metadata quality independently. Add controlled-tag retrieval and a bounded embedding experiment before concluding that the proposed complete RAG path works. Human labels and broad historical authority resolution remain pending.

No V2 provider requests yet. Existing production status remains 1,339 completed / 423 review / 20,785 pending / zero claimed. The next executable step is to inspect the delegated sample manifest and dry-run harness when they finish; do not resume the old OCR model queue. Scripts/evidence are isolated and machine-local; committed documents must carry a reconstructible handoff.

- [x] Independent Luna design review saved at `artifacts/v2-pivot-20261011/design-review.json`: intended-target ranks are not relevance precision/recall; quote matching is not entailment; raw/static alone does not measure tagging value. Required later comparison: identical raw text without versus with proposed metadata, plus explicit unanswerable/mixed/unknown controls. No pivot adoption conclusion yet.
- [x] Read-only local `/api/tags` inventory: Qwen, Gemma and Muse completion models only; no embedding-capable model listed. Qwen digest `5642e97495e1a088883805981563dcdc4a040c2f53388b7a41d1f24d3622cf7e`. Sandbox loopback access failed; elevated GET succeeded. No inference requests.
- [ ] User requested an embedding-model recommendation for an M4 Mac mini with 64 GB RAM. Luna `v2_embedding_choice` is researching the six screenshot families from official sources and will write `V2_EMBEDDING_MODELS.md`. No download/install authorized or started. Verify compatibility with the current MLX-backed server before presenting a native Ollama command as sufficient setup.

### Model-call authorization for V2

The user explicitly authorized GPT Mini and Ollama requests in small quantities for sampling/testing. This supersedes any requirement to ask again for these bounded V2 POCs, including paid Mini requests. Keep requests isolated from production cleanup and log configuration, usage, observed time/cost and quality. Initial local comparison budget: at most twenty sequential requests and fifteen minutes. A subsequent Mini comparison should use a selected four-to-six-case sample with the same prompt/schema/context. This permission does not authorize full-corpus model processing, automatic downloads or replacing the existing corpus. No V2 inference requests have run yet; manifest/harness preparation remains active.

- [x] Luna prepared and checked ten target windows plus forty distractors, two targets/eight distractors per part; 1,911–3,499 raw characters. Evidence: `artifacts/v2-pivot-20261011/{targets,distractors}.jsonl`, `selection-report.json`, `integrity-report.json`, `curation-manifest.json`, `sample-schema.json`, `prepare_sample.py`. All 100 text hashes recompute; source input hash matches the existing static canonical release. Static comparison text is reconstructed from static ledgers, not live AI results. Labels remain provisional. The sampler recreates its temporary candidate reservoir under `tmp/`, then `--finalize` exports the fifty-window sample. Two optional unanswerable prompts are recorded but not yet scored by the harness.
- [x] Embedding recommendation documented in [V2_EMBEDDING_MODELS.md](V2_EMBEDDING_MODELS.md): compare Qwen3 0.6B/4B, with BGE-M3 as another family. Published general benchmarks favor 4B; corpus accuracy and actual M4 throughput remain unmeasured. Root verified native Ollama app binary/version 0.40.2 and its listener on 11434; MLX runner labels do not prove a separate incompatible server. No download or embedding request.
- [ ] `benchmark_harness` has saved a draft in `tmp/v2_pivot_benchmark.py`; input parsing and offline BM25/dry-run checks are underway. `pipeline_audit` independently reviews source labels before inference. Once both pass, inspect processes and production queue again, reserve exact run ID, then run isolated Qwen comparison. Unannotated tag families must not be treated as verified negatives; answer string match alone is not quality.

Independent review completed: `sample-review.json` identifies target-02's petitioners-versus-Sumner attribution error, target-03's reported allegation/signature distinction, raw/static evidence differences in targets 02/08, and mixed speaker windows in 01/08/09. `static_review` is correcting labels with archived originals and explicit text-layer/label-coverage metadata. `benchmark_harness` is adding negative-control handling and preserving unannotated fields. Hold live inference until those corrections and dry-run checks finish; no V2 inference has run. These findings are evidence of evaluation/attribution risks, not a failed raw-OCR model experiment.

### Cross-harness handoff checkpoint

Read [V2_HANDOFF.md](V2_HANDOFF.md) for the executable continuation path, authorization, preserved baseline, artifact dependencies, evaluation caveats and ordered next work. User credit-conservation request makes this handoff a priority.

- [x] Corrected labels archived as `runs/sample-v2-audit-corrected/`; originals remain `sample-v1-pre-audit/`. All ten positive queries remain in the first twenty-call comparison. Two negative controls are separate later four-call work. Per-family coverage distinguishes unannotated fields; mixed speaker states, presenter versus petitioner and letter-author roles remain explicit.
- [x] Final prototype dry-run `v2-qwen-pivot-dryrun-final3`: no requests; twenty planned. BM25 intended-target hit@1: raw 10/10, static 9/10; both 10/10 at @3/@5. This is not true relevance recall/precision or semantic search evidence. Script/durable copy are saved; several prototype helpers still exceed complexity five and require refactoring before production adoption. Do not claim the main gate covers ignored scripts.
- [x] User installed Qwen3 embedding 4B/8B. Read-only inventory verifies 4B digest `df5bd2e3c74cd8d069d21dc038f1b359fcdc9458fce1c99bd43c9eb1518ff907` (2,560 full dimensions), 8B digest `64b933495768fbd3b87c20583d379728a07471e0c66733a9df87cd1901b3c44b` (4,096). Native Ollama 0.40.2 serves both GGML embeddings and MLX completion models. No embedding inference has run yet.
- [x] Add `embeddings.py`: source-linked passage/input hash and explicit unknown/mixed metadata; provider-neutral embedding protocol/configuration identity; strict Pydantic Ollama response validation; sequential shared lock, explicit dimensions and `truncate:false`, query/document prefix distinction, count/dimension/finiteness/zero-norm checks and L2 normalization. Fourteen focused mocked tests pass. Initial full gate caught a typing error in a test helper; corrected and ty passed. Full gate rerun is in progress; record its terminal result before code handoff.
- [ ] Reserve/execute `v2-qwen-pivot-20261011` after checking no active worker. Last process/queue inspection found none, with production status unchanged at 1,339 completed / 423 review / 20,785 pending / zero claimed. Use the exact command in V2_HANDOFF; twenty paired requests, 45-second request timeout, fifteen-minute budget. No V2 inference has started at this checkpoint.

Full gate is terminal, exit 0: Ruff formatting/lint, ty, complexity at most five in source/tests, **107 tests passed**. Evidence: `artifacts/v2-pivot-20261011/embedding-interface-gate.log`. Next step: commit this checkpoint, then launch/reconcile the bounded Qwen comparison and tiny 4B dimension sanity check sequentially. Update active handles immediately. Preserve this state if credits run out; no model download or full indexing is needed to continue.

### Active Qwen pivot comparison

Checkpoint committed as `8dc1a24`. Launched the authorized twenty-request local comparison, run **`v2-qwen-pivot-20261011`**, exec session **65064**. Shell log: `artifacts/v2-pivot-20261011/qwen-pivot.log`; per-call audit: `artifacts/v2-pivot-20261011/runs/v2-qwen-pivot-20261011/results.jsonl`. The command in `V2_HANDOFF.md` runs inside `subprocess.run(..., timeout=900, check=True)` for an outer fifteen-minute deadline. Do not overlap embedding or completion requests and do not restart this run until its handle/process is confirmed terminal. Source/production queue remains untouched. At this launch checkpoint no results have been reviewed.

Luna `v2_embedding_interface` is preparing a separate offline embedding benchmark runner over the frozen fifty-window pool. It must send no requests while session 65064 is active. Next: poll that exact session or inspect its process; after terminal exit, reconcile all saved results and inspect raw/static answers, quotations and tag proposals. Then perform the tiny native 4B dimension sanity check and run the prepared bounded embedding comparison if ready. Record Mini/negative-control calls separately; none have run yet.

### Terminal pivot trial and credit-conservation handoff

Qwen run `v2-qwen-pivot-20261011` is **stopped**, session 65064 terminal exit 1. Root stopped only its identified child PID 80434 after repeated output-limit failures; Ollama and the corpus queue were not terminated or changed. Three saved calls all have `finish_reason: length` at 700 output tokens, with 100.56 seconds summed duration and 4,065 input / 2,100 output tokens. Local API charge $0. Any in-flight unsaved call has unknown usage/outcome. Partial answers suggest comprehension, but no valid completed comparison or tagging quality claim follows. Evidence: per-run `terminal-report.json`, `results.jsonl` and frozen `script-used.py` (SHA-256 `189d1ffd2fba203c62366adaa7a6410c1a31c55669c20fd1309d152a867e13f3`). Do not repeat unchanged.

Active offline delegates at this checkpoint:

- Luna `benchmark_harness`: shorten answer/evidence/tag output, refactor every helper to complexity at most five, dry-run/mock-check. No provider calls; do not alter the frozen first-trial script.
- Luna `v2_embedding_interface`: prepare isolated cache/resume/rank benchmark over fifty raw/static windows, full 4B vectors plus explicitly labeled 1,024-dimension Matryoshka projection. No model requests. Native 1,024 output still requires runtime confirmation.

The committed source embedding foundation has passed the complete 107-test gate. GPT Mini, abstention controls and embedding inference have **not** run. Next executable step for any harness: inspect delegate files/reports and process state, finish the compact prompt/refactor or embedding dry-run, then launch the corresponding small POC under a new run ID. Follow `V2_HANDOFF.md`; preserve current work rather than restarting the cleanup workflow. Goal remains active and pivot viability remains unproven.

Embedding runner preparation is now complete: `tmp/v2_embedding_benchmark.py`, durable `artifacts/v2-pivot-20261011/embedding_benchmark.py`, SHA-256 `a8e09122713b92c3e3dc6b9e6990d2869768d54c39f6980bad124e2ac6a53b72`. Ruff, ty and complexity at most five passed for the prototype. Dry-run `v2-embedding-dryrun-20261011-r3` validates fifty windows/ten queries, plans 110 inputs in 22 requests, and reports zero live calls/cache batches. `V2_HANDOFF.md` now contains the exact live/resume command with an outer subprocess timeout. It compares full 4B vectors with locally projected 1,024-dimension vectors; native 1,024 output remains untested. The QA worker is terminal; recheck current processes and installed model digest before launching. No inference is active at this recorded checkpoint; the QA prompt/refactor delegate remains offline work.

### Active embedding POC — latest state

The prepared embedding run **`v2-embedding-dryrun-20261011-r3`** has resumed **live**, session **16163**, confirmed child PID **83016**. Uses the exact subprocess-wrapped 900-second command in `V2_HANDOFF.md`. Log: `artifacts/v2-pivot-20261011/embedding-poc.log`; artifacts: **`artifacts/v2-pivot-20261011/embedding-runs/v2-embedding-dryrun-20261011-r3/`**. Last read-only snapshot: three completed/successful request batches, confirming valid native 2,560-dimensional 4B responses on this machine. Retrieval ranks and throughput are not yet final. Do not overlap another local request, restart the run or assume failure because the shell log is quiet.

QA compact-output dry run/mocked checks passed; live retry is not started. The frozen truncated-trial script remains unchanged. `benchmark_harness` continues offline complexity refactoring; several helpers still need to reach five before prototype production readiness. Next action: poll session 16163 or inspect PID/progress/cache; after terminal exit inspect all final rank/usage/timing reports and then choose the next small test. Native 1,024 response verification, Mini, negative controls and tag-augmented retrieval remain pending. This latest paragraph supersedes earlier no-inference checkpoints.

### Embedding POC complete and compact-QA retry ready (reconciliation)

Recorded by the OpenCode `big-pickle` agent after the prior harness ran out of credits. Reconciled on-disk state against the records above; **this section supersedes the "active embedding POC" checkpoints.**

- [x] Embedding run `v2-embedding-dryrun-20261011-r3` **completed**: 22/22 batches, 110 inputs, worker elapsed 140.867 s (`retrieval-report.json`), 80,052 prompt-eval tokens, zero failures. Directory: `artifacts/v2-pivot-20261011/embedding-runs/v2-embedding-dryrun-20261011-r3/`. Native Qwen 4B returned 2,560-dimensional vectors on this machine; `derived_is_native_mrl` is false and the 1,024 arm is a local first-1,024 projection plus L2, **not** a native `/api/embed` `dimensions=1024` response.
- [x] Result is a **ceiling effect**: `raw_2560`, `static_2560`, `raw_1024_derived` and `static_1024_derived` each ranked all ten intended targets first — hit@1 10/10, MRR 1.0. The frozen ten-query/fifty-window sample is too easy to separate raw vs static or full vs projected dimensions. This is a plumbing validation, not pivot evidence; `claims` explicitly notes only intended-target rank, no precision/recall because distractors are unlabeled.
- [x] Compact/refactor dry-run `v2-qwen-pivot-compact-refactor-dryrun-20261011`: `live_requests_enabled` false, `requests_planned` 20, `requests_completed` 0. Every helper now scores at most five (`complexity-report.txt`); `mock-check.json` validates complete vs truncated handling (truncated fails closed, raw retained, usage kept), a two-sentence answer cap and a two-topic cap. Prompt `e14d5597…`, script `67d1d351…`.
- [x] No benchmark worker active at reconciliation (only `ollama serve` and a warm `llama-server`). Production queue unchanged: 1,339 completed / 423 review / 20,785 pending / zero claimed. First-trial evidence `v2-qwen-pivot-20261011` remains truncated and unchanged; do not repeat it.
- [ ] Next executable step: launch the bounded compact-QA retry under a **new** run ID (20 sequential local Qwen calls, 45 s/request, 900 s outer deadline), then inspect every claim, quote and abstention — not schema pass alone. Then run the two negative controls separately, and design the harder retrieval tier so raw/static and tagging value become measurable rather than saturated.

This reconciliation unit is documentation only; no provider request, download or production change occurred.

### Compact-QA retry executed: truncation root-caused and fixed (OpenCode `big-pickle`)

Following the reconciliation above, the OpenCode `big-pickle` agent launched the bounded compact-QA retry and iterated on the blocker. Three live runs, 60 sequential local Qwen calls total, **$0 API charge**, no downloads, no production/queue change. All use the frozen ten targets × two arms (raw/static), 45 s/request, 900 s outer deadline.

- **Retry 1 — `v2-qwen-pivot-compact-live-01`** (pre-fix script `67d1d351…`): 20/20 jobs failed with `finish_reason: length` at exactly 700 output tokens, empty `content`, 27,695 input / **14,000 output** tokens fully wasted. The compact prompt did **not** shorten generation. Root cause identified: the prototype's Ollama path set `max_tokens=700` but did not disable Qwen3.8 thinking; reasoning consumed the whole budget before any answer. Frozen script preserved as `runs/v2-qwen-pivot-compact-live-01/script-used.py`.
- **Diagnosis** (bounded direct calls, no harness): on Ollama's OpenAI-compatible endpoint `reasoning_effort:"none"` disables thinking (trivial prompt: `finish=stop`, `completion_tokens=1`, no `reasoning` field), while `think:false` is **ignored** there. The OpenAI path already passed `reasoning={"effort":"none"}`; the Ollama path omitted the equivalent.
- **Fix A** (script `9c4c53ef…`): added `extra_body={"reasoning_effort": "none"}` to `_ollama_reply`. **Retry 2 — `v2-qwen-pivot-compact-live-02`**: 20/20 `stop`, no truncation, 27,735 input / 7,479 output, 368.1 s. Now 4 validated / 5 review / 11 failed — **all 11 failures were schema validation, not length**: `answer_evidence` exceeded the 140-character cap. Frozen script preserved in that run directory.
- **Fix B** (script `619e542a…`): relaxed `answer_evidence` max length 140→320 in both schema and prompt. **Retry 3 — `v2-qwen-pivot-compact-live-03`**: 20/20 `stop`, 27,795 input / 7,788 output, 363.8 s. Result: **5 validated / 12 review / 3 failed** (two still `answer_evidence`-too-long, one other). `answer_status` = 17 `supported`, 3 unparsed. Non-empty families: `topic_tags` 17, `person_mentions` 15, `place_mentions` 13, `speakers` 11, `dates` 6, `legislation_mentions` 3.
- **Qualitative** (provisional, not endorsed): real evidence-grounded answers with verbatim quotes appeared and read on-topic — e.g. target-03 (Brayman letter / Burnett resignation), target-04 (additional `$30,000` cash capital amendment), target-08 (Dakota forced-relocation consequences), target-09 (Cowan on removal vs. withholding salary), target-10 (four North Carolina collection districts).
- **Caveats:** 0/20 reference exact-string matches — the benchmark explicitly states this is **not** correctness (answers paraphrase). Raw validated 2 vs static validated 3 is far too small to compare arms. "validated" means schema plus quote validation passed, not historical truth; speaker/date/tag fields are candidate proposals, and `None` families are unannotated, not verified absence. Entailment, attribution and human review remain pending.

Evidence: `runs/v2-qwen-pivot-compact-live-0{1,2,3}/{run.json,results.jsonl}`, shell logs `qwen-pivot-compact-live-0{1,2,3}.log`, durable script now `619e542a…`. Production queue unchanged at 1,339 completed / 423 review / 20,785 pending / zero claimed.

- [ ] Next executable steps, in order: (1) run the two negative/abstention controls as a separate bounded run; (2) native `/api/embed` `dimensions=1024` confirmation; (3) build a harder, relevance-labeled retrieval tier so raw vs static and dimensionality separate (current sample is saturated); (4) the tag-augmented arm (same raw text without vs with evidence-linked tags) to test the actual pivot hypothesis; (5) a small matched Mini sample only to explain local-model failures.

### Abstention controls, native 1024-dim, and Tier-2 harder retrieval tier (OpenCode `big-pickle`)

Steps 1–3 of the checklist above are now implemented and terminally recorded (step 3 filled in the harder pool and lexical rank baseline; step 4 the deterministic tag arm is executed below, step 5 Mini remains).

- [x] **Negative/abstention controls run** `v2-qwen-controls-live-02` (4 sequential local Qwen calls, $0 API, no production change): all four substantive abstentions — `answer_status "unknown"` with no fabrications (no invented dates/names). But all four `model status "failed"`: the schema `unknown` contract requires `answer` and `answer_evidence` empty, and the model wrote refusal prose into those fields, so Pydantic rejected them (`Value error, answer fields conflict with answer_status`). Evidence verified in 3/4 arms (target-08 raw fails because the model normalizes the hyphenated `Secretary of the Inte- rior`). Dry run `v2-controls-dryrun-20261011` validated the plan. Analysis: `runs/v2-qwen-controls-live-02/control-analysis.json` (4/4 substantive abstention, 0/4 schema-unknown satisfied); failed pilot `v2-qwen-controls-live-01` documented in its `note.txt` (one lost provider call from a `_score`-returns-`{}` bug, fixed before the live run). Runner `tmp/v2_controls_benchmark.py` maxes 6 controls/12 requests.
- [x] **Native `/api/embed` `dimensions=1024`**: `qwen3-embedding:4b` returns an actual 1,024-dimensional vector when asked (deterministic across two calls, `truncate:false`); without the parameter it returns the full 2,560. Evidence: `tmp/embed_full.json`, `embed_1024.json`, `embed_1024{b,c}.json`. This replaces the earlier local first-1,024 projection assumption for any bounded embedding test.
- [x] **Tier-2 harder retrieval pool** built by `tmp/build_tier2.py` (streaming `canonical_pages.jsonl`, input sha `4ab8ef6b…`): `artifacts/v2-pivot-20261011/tier2/pool.jsonl` with **125 windows** (the 50 sample windows plus 75 new, 15 per part; `build-report.json`, seed 20261011; excludes the 175-window candidate reservoir). 29 labeled queries scored (10 base from `targets.jsonl` band `easy`, 19 hard in `tier2-hard-queries.jsonl`): paraphrase ×10, near-miss ×4, repair_clean ×3, repair_garble ×2; every `evidence_quote` verifies as an exact substring of the assigned window.
- [x] **BM25 baseline** `tmp/score_tier2.py` → `tier2/bm25-report.json` no longer saturates, and raw vs static now separate on 4 queries: overall raw hit@1 **25/29 (MRR 0.931)**, static **24/29 (MRR 0.908)**; easy 8/10 both arms; paraphrase raw 9/10 vs static 8/10; near-miss 4/4 both; repair_clean 2/3 both (h-repair-02: raw rank 2 vs static 3); repair_garble 2/2 both. Separated queries: `base-target-06` (static wins), `base-target-08` (raw wins), `h-paraphrase-04` (raw wins), `h-repair-02` (raw wins). Surprise: the raw arm is not uniformly worse lexically — hyphenated raw can outrank its static form on queries whose tokens land mid-word (target-08), while static wins when the query uses the joined clean form. Intentional-target rank only; distractors remain unlabeled.
- [x] **Tag-augmented arm executed (deterministic-only)** — see the next dedicated section for the full result; step 4 of the checklist is now done, step 5 (small matched Mini sample) and the human-review scorecard/pivot recommendation remain.
- [ ] Next: step 5 Mini matched sample, then a human-review scorecard and explicit pivot recommendation.

All of the above is provider-free/offline after the 4-call controls run; no production queue change, no downloads. Existing queue still 1,339 completed / 423 review / 20,785 pending / zero claimed.

### Tag-augmented arm: deterministic evidence-linked tags on Tier-2 (OpenCode `big-pickle`)

Step 4 executed without any provider call: the same 125 windows and 29 queries were re-ranked with an evidence-anchored controlled-tag block appended to both raw and static text, using the identical BM25 scorer/metric path as `score_tier2.py`. This directly tests the pivot hypothesis: can unchanged OCR plus separately generated metadata match the cleaned static arm?

- [x] **Tagger** `tmp/tag_tier2.py` (durable copy `tier2/tag_tier2.py`, SHA-256 `c8326463a…`), run as `uv run python tmp/tag_tier2.py`: deterministic-only lexicon/surface-form tagger, providers `["deterministic-only"]`, empty request log. Six families — `topics` (the ten controlled IDs via fixed alias words: railroad, dakota, reconstruction, insurance, navy yard, collection districts, …), `person_mentions` (curated + `Mr. <SURNAME>`-derived), `place_mentions`, `legislation_mentions` (bill-number pattern), `speakers`, `dates` — all candidates, never authority. Every tag carries the exact `raw_text` substring plus `[start,end)` offsets; the tagger folds OCR end-of-line hyphens (e.g. `Whit- ney`) for lexicon lookup but still anchors to the original surface. Output `tier2/tagged_pool.jsonl` (125 rows, `tags` + `tags_block` + `tags_hash` per window; output SHA-256 `81c9a6ae7af7b101b8a4b85020d42ebc2b715b340c7283b4a59977952290735b` over `pool.jsonl` `aad18d072…`); `tag-generation-report.json` records per-window coverage per family, input/output hashes, script hash, and verification (0 anchor failures).
- [x] **Coverage**: family totals over 125 windows — topics 191, person_mentions 1069, place_mentions 191, legislation_mentions 103, speakers 526, dates 382. Empty families stay explicit `unannotated` (e.g. legislation_mentions empty in 106 windows, dates in 24, person_mentions in 1); never "verified absent".
- [x] **Tag-arm scoring** `tmp/score_tag_arms.py` (durable copy `tier2/score_tag_arms.py`, SHA-256 `2e471e4a9…`), run as `uv run python tmp/score_tag_arms.py` → `tier2/tag-arm-report.json`; raw/static ranks reused unchanged from `bm25-report.json` (not recomputed), tag arms scored with the same `bench._bm25` call. The same tag block is appended to both `raw+tags` and `static+tags`.
- [x] **Result**: raw+tags keeps overall hit@1 equal to raw (25/29) but lowers MRR (0.931 → 0.9164) and drops hit@3/5 from 29 to 28; static+tags ties raw at 25/29 (MRR 0.9107, hit@3/5 28). Per band: easy — both tag arms keep 8/10 hit@1 but MRR 0.9000 → 0.8577; paraphrase — raw+tags = raw (9/10, 0.95), static+tags recovers `h-paraphrase-04` to rank 1 (static-only was 8/10); near-miss, repair_clean, repair_garble unchanged (4/4, 2/3, 2/2).
- [x] **Separated queries**: `base-target-01` improves 2 → 1 in both tag arms; `base-target-06` is NOT recovered (raw 2, raw+tags 2; static 1, static+tags 2) — the static arm's clean-form win stays unclaimed; `base-target-08` collapses raw 1 → raw+tags 13 (topic tags fired on many distractor windows that share `dakota`/`indian`, so topic-id words add discrimination-diluting tokens); `h-paraphrase-04` rank equals raw in both tag arms; `h-repair-02` unchanged (raw 2, static 3).
- [x] **Interpretation corrected after read-only review**: raw+tags ties raw at 25/29 intended targets ranked first, but lowers MRR from 0.931 to 0.9164. `base-target-08` drops raw rank 1 → 13 (+12 positions); static rank 2 → 13 is +11. The report's +9 aggregate is unsupported: recomputing the emitted ranks gives +11 summed positions versus raw and +12 versus each query's better raw/static rank. All four near-miss queries rank first in every arm, so near-miss is not a failing band. The report's verdict prose overstates that limitation; its numeric tables remain the evidence. Tags do not recover `base-target-06` (raw rank 2 versus static rank 1), and `h-repair-02` remains rank 2 on raw/raw+tags. This tests appending deterministic tag tokens to BM25 text; it does not decide the value of separate metadata filters, ranking fusion or evidence-backed model tags.
- [ ] Next executable step: step 5 small matched GPT Mini sample (bounded, usage/cost recorded) to explain local-model failures, or a refined tagger retry (stopword-free topic tokens, pruned aliases, query-adjacent alias choices) if a second lexical tag pass is desired; then the human-review scorecard and explicit pivot recommendation (pending, do not mark complete).

### Tag-arm handoff review

Commit `7eb1571` and its numeric tag-arm report were inspected; working tree was clean before this review. No provider requests, experiment reruns, source edits or worker launches occurred. Corrected the interpretation above and in `V2_HANDOFF.md`: near-miss is fully successful on this small benchmark, and the Dakota rank regression is +12 relative to raw. Intended-target ranks are not corpus-wide relevance accuracy. Luna independently confirmed these issues and found the speaker regex matches `Mr. NAME` anywhere in the window, including mentions; these labels are speaker-cue candidates, not resolved speakers. Next executable experiment remains a small matched GPT Mini sample with frozen inputs/prompt and recorded usage, followed by the human-review scorecard. No full-corpus readiness claim is justified.

### Matched Mini diagnostic sample launched

Run `v2-mini-matched-20261011-01`, exec session **87477**, is active at this checkpoint: six requests only (`target-01/02/03` × raw/static), GPT-5.4 Mini, reasoning none, temperature zero, 700 output-token cap, 45-second request timeout, no SDK retries, 900-second outer deadline. Selection manifest and frozen runner: `artifacts/v2-pivot-20261011/mini-matched-review/`. Audit/results: `runs/v2-mini-matched-20261011-01/`; streaming log: `mini-matched-review/mini-live.log`. No other worker was active at launch; production queue unchanged (1,339 completed / 423 review / 20,785 pending / zero claimed). Poll this session; do not duplicate the run.

Luna's provisional Qwen audit is `mini-matched-review/qwen-review.json`: all six intended contexts retrieved; answers are substantially supported, but surface capitalization, evidence-length/exactness and letter-author-as-speaker errors block acceptance. Answers already distinguish petitioners and Brayman's allegations; do not falsely report those attribution errors in the prose answer. This is diagnostic replication, not a held-out accuracy estimate or human verification. Mini uses strict Responses JSON Schema whereas Ollama used JSON-object mode; record that enforcement difference when comparing validation rates.

Luna added flushed prototype events (`events.jsonl` and stdout): request started/completed status, completed/total/percent, elapsed/ETA, source text, raw output and parsed answer when available. Prompt/schema unchanged. Frozen runner hash `ecce0f203ce1fc7841015365aaae5fef2e014d6051387bee6c3078d5900e4dc0`; offline fixture, Ruff and prototype complexity ≤5 passed. This applies to the QA prototype, not every existing worker or embedding runner. Previous native dimension responses were copied from scratch to `artifacts/v2-pivot-20261011/native-dimensions/` with hashes; no new embedding calls.

### Matched Mini terminal result

Session **87477 is terminal, exit 0**; `v2-mini-matched-20261011-01` saved all six responses and twelve progress events. Summed request time **16.691 s** versus **116.463 s** for the same six saved Qwen calls; this is a tiny diagnostic comparison, not a throughput guarantee. Usage **10,502 input / 1,669 output tokens**; upper token-price estimate **$0.015387** at uncached rates ($0.75/M input, $4.50/M output; [official model page](https://developers.openai.com/api/docs/models/gpt-5.4-mini)). Cached-input details are absent, so this is not an invoice. Exact query/context/input equality against Qwen was checked for every pair.

All six Mini outputs are **review**, none accepted. It largely understands these raw/static passages but adds quotation delimiters to evidence, sometimes changes source name case/spelling, and raw target-03 still labels Brayman's signature as a floor speaker. Strict JSON Schema alone did not enforce evidence fidelity. Luna's independent provisional `mini-review.json` separates literal exactness, semantic answer support and attribution; paired `human-review-packet.jsonl` has six cases, all human statuses pending. Source/production outputs unchanged.

Next bounded diagnostic: three raw-only Mini calls under `v2-mini-prompt-retry-20261011-01`, with an explicitly versioned prompt that demands literal contiguous source evidence, exact surface spelling/case and floor-speaker versus letter-author separation. Preserve schema/validators/settings; never trim quotes or normalize source to make outputs pass. This is prompt tuning on known cases, not held-out proof. No retry calls have started at this checkpoint.

Prompt-only diagnostic launched as **`v2-mini-prompt-retry-20261011-01`**, session **50188**, three raw requests maximum and 900-second outer deadline. Frozen runner `mini-matched-review/prompt-retry.py`; log `mini-matched-review/mini-prompt-retry.log`; prompt/schema/input hashes and dry-run checks in `prompt-change-report.json`. Only the prompt string differs from the matched run. Poll session 50188 before any repeat.

### Prompt diagnostic terminal and current handoff

Session **50188 terminal, exit 0**. Run `v2-mini-prompt-retry-20261011-01` saved three raw-only calls and six progress events: **1 validated / 2 review**, **5,606 input / 693 output tokens**, **8.259 s** summed request time, **$0.007323** upper token-price estimate. Total Mini spend estimate for this unit: **$0.022710**, nine calls; no more calls in this unit. Prompt change and frozen hashes are preserved. Target-03 now has literal evidence and excludes Brayman from floor speakers, but omits Davis; literal `186-1` remains an uncertain OCR cue, not a resolved date. Target-01 still changes name case; target-02 still changes/truncates evidence. Validators and source text were not relaxed.

Luna's `prompt-retry-review.json` and `prompt-retry-human-packet.jsonl` record these distinctions. Both human packets remain entirely pending; no human/image verification claimed. The revised prompt is an experimental runner only, not the active production cleanup prompt or a proven complete enrichment stage.

Required `make gate` terminal exit 0: Ruff, ty, complexity ≤5 in source/tests and **107 tests**. Log `artifacts/v2-pivot-20261011/mini-matched-review/gate.log`; ignored prototypes have separate offline Ruff/complexity checks and fixtures, not main-test coverage. No model worker remains live in this unit; production queue was unchanged at launch and never written. Native response evidence is now durable under `native-dimensions/`.

**Ordered next work (supersedes older checklists):**

1. Prepare an offline, resumable embedding comparison for the existing 125-window/29-query Tier-2 pool; reuse compatible old cached vectors, with explicit new input/query/config hashes and progress events. Confirm no live worker before any bounded calls. First run raw/static native 4B dimensions with identical query instructions; label intended-target rank only until relevance review exists. Do not repeat the saturated fifty-window run.
2. Build a separate metadata filter/ranking-fusion arm rather than appending broad tags. Distinguish mentions, floor speakers, letter authors, proceedings dates and OCR date cues; unknown/unannotated/mixed values cannot satisfy verified filters. Evaluate those roles independently, not through quote match alone.
3. Complete human review of the saved matched packets and independent relevance labels for held-out cases; report disagreement and coverage. Further prompt tuning on existing cases cannot count as held-out quality evidence.
4. Publish the case-by-case pivot recommendation and reproducible operator commands after these checks. Current direction: promising for raw-text discovery and grounded summaries, inconclusive for the full metadata/vector workflow; no full-corpus launch recommendation.
