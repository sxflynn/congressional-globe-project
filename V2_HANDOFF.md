# V2 pivot handoff for any AI harness

## Start here

**Resume from “Current harder-tier checkpoint” below and the final PROGRESS entries. Earlier command examples are historical; completed run IDs must not be launched again.**

Work in `/Users/sflynn/Downloads/congressional globe project`. Read `AGENTS.md`, the latest V2 section of `PROGRESS.md`, `V2_PIVOT.md` and `V2_EMBEDDING_MODELS.md`. New user instructions take precedence. Preserve the existing cleanup implementation, sources, queues and exports. The experiment asks whether **unchanged OCR plus organization and metadata** can support research retrieval and grounded answers without further OCR correction.

The local corpus covers **five parts of the 39th Congress, first session**, not the entire historical Congressional Globe. The multi-decade research examples are future requirements. Do small POCs; the human will launch full processing later.

## Authorization and tools

The user explicitly authorizes small GPT Mini and Ollama sampling/testing calls. Do not ask again for these bounded requests. Paid Mini calls must record tokens and cost. No full-corpus model processing is authorized. Use `uv`, Pydantic v2 and the existing sequential Ollama lock. Never print `.env` or keys. Local key is the placeholder `ollama`.

Use `UV_CACHE_DIR=/private/tmp/congressional-globe-uv-cache` if the default uv cache is sandboxed. Request elevation for loopback access, process inspection, Git writes and the required Prettier formatter if needed. Do not touch the separate OpenCode investigation in `tmp/performance/`.

## What exists

- Preserved baseline: full static canonical export, 5,412 pages / 296,995 paragraphs / 19,803 chunks. Its source/output verification is recorded in `PROGRESS.md`.
- Cleanup queue: `artifacts/runs/static-final-20261011/jobs.sqlite`. Last checked: 1,339 completed, 423 review, 20,785 pending, zero claimed. Its canonical/RAG exports are an earlier static snapshot, not refreshed from live AI results.
- V2 sample: `artifacts/v2-pivot-20261011/targets.jsonl` and `distractors.jsonl`: ten curated substantive targets and forty distractors, two targets/eight distractors per part. Raw windows are 1,911–3,499 characters. Static comparison text replays existing static ledgers; neither arm contains newly applied edits.
- Sample labels, schema, hashes, reproducible sampler, audit findings and archived label versions are in the same directory. `sample-review.json` caught attribution errors before inference. Corrected labels distinguish petitioners from Sumner, letter allegations from verified facts, and mixed speakers from scalar attribution.
- Two negative questions are in `controls.jsonl`; additional unscored metadata cases are in `control-contract.json`. Do not claim these controls were run merely because the files exist.
- Isolated QA/tag prototype: `tmp/v2_pivot_benchmark.py`, durable copy `artifacts/v2-pivot-20261011/v2_pivot_benchmark.py`. Default execution makes **no requests**. It compares BM25 top-1 context and records original input, raw/parsed response, exact quote validation, usage, time, model/prompt/schema hashes and source anchors.
- Embedding foundation is being developed in `src/congressional_globe/embeddings.py` and `tests/test_embeddings.py`. Check Git status and gate results before assuming completion. It introduces source-linked passages, a provider-neutral boundary and Ollama `/api/embed`; no vector index or full enrichment pipeline exists yet.

Artifacts and scratch files are Git-ignored and machine-local. On another machine, copy the evidence directory and original source files, or recreate the sample with its saved sampler/curation manifest. A Git checkout alone does not contain these artifacts.

## Current model inventory

The user installed `qwen3-embedding:4b` and `qwen3-embedding:8b`. Native Ollama app version 0.40.2 listens on port 11434; MLX completion and GGML embedding runners coexist in its inventory. Verified tags report:

| Model | Dimensions | Digest |
| --- | --: | --- |
| `qwen3-embedding:4b` | 2,560 | `df5bd2e3c74cd8d069d21dc038f1b359fcdc9458fce1c99bd43c9eb1518ff907` |
| `qwen3-embedding:8b` | 4,096 | `64b933495768fbd3b87c20583d379728a07471e0c66733a9df87cd1901b3c44b` |
| `qwen3.8:27b-mlx` | Completion model | `5642e97495e1a088883805981563dcdc4a040c2f53388b7a41d1f24d3622cf7e` |

Recheck `/api/tags` before resuming: tags can change. The 0.6B baseline and other families are recommendations, not confirmed installations. Do not download models automatically as part of this handoff.

## Commands and restart rules

Latest terminal checkpoint: Qwen QA/tag run `v2-qwen-pivot-20261011`, exec session **65064**, exited **1** after root stopped only child PID 80434 with SIGTERM. Three saved responses all reached the 700-token output limit; an in-flight unsaved request has unknown outcome/usage. Evidence: `runs/<run-id>/terminal-report.json`, `results.jsonl`, immutable `script-used.py`, and `artifacts/v2-pivot-20261011/qwen-pivot.log`. The trial proves a response-budget problem, not raw-OCR inadequacy. Do not repeat it unchanged; the prototype is being shortened/refactored offline. Check the latest `PROGRESS.md` before starting any local request.

**Embedding run is complete** (no worker live): `v2-embedding-dryrun-20261011-r3` finished 22/22 batches, 110 inputs, 140.867 s, 80,052 prompt-eval tokens, zero failures. Directory: **`artifacts/v2-pivot-20261011/embedding-runs/v2-embedding-dryrun-20261011-r3/`**, distinct from QA `runs/`. Rank result is a **ceiling effect** — all four configs (raw/static × full-2560/projected-1024) ranked every intended target #1 (hit@1 10/10, MRR 1.0); the sample cannot separate raw vs static or dimensionality. The 1,024 arm is a local first-1,024 projection plus L2, not a native `/api/embed` `dimensions=1024` response (still untested). Reuse the saved caches; do not re-run unchanged.

**Compact-QA retry has now run three times** (OpenCode `big-pickle`, 60 sequential local Qwen calls, $0 API, no production change). `v2-qwen-pivot-compact-live-01` reproduced the 700-token truncation (reasoning consumed the budget). Root cause: the Ollama path omitted a thinking-disable. Fix: `extra_body={"reasoning_effort":"none"}` in `_ollama_reply` (Ollama's OpenAI-compat endpoint ignores `think:false` but honors `reasoning_effort`). `live-02` then finished 20/20 `stop` but 11 failed on the 140-char `answer_evidence` cap; relaxing it to 320 gave `live-03`: 5 validated / 12 review / 3 failed, `answer_status` 17 supported. **Current prototype script is `619e542a…`** (durable copy synced); the pre-fix scripts are preserved in each run directory as `script-used.py`. Result quality is provisional and not correctness-verified; 0/20 reference exact-string matches is expected (answers paraphrase).

First inspect production state and active processes. Never overlap local model requests or restart an apparently active POC solely because a polling request timed out.

```bash
UV_CACHE_DIR=/private/tmp/congressional-globe-uv-cache uv run globe cleanup status \
  --run-directory artifacts/runs/static-final-20261011 --run-id static-final-20261011
ps -axo pid,etime,command | rg 'globe cleanup run|v2_pivot_benchmark|run_bounded_challenge'
```

Offline prototype check (choose a new unused run ID; existing IDs are intentionally rejected):

```bash
UV_CACHE_DIR=/private/tmp/congressional-globe-uv-cache uv run python tmp/v2_pivot_benchmark.py \
  --run-id v2-resume-dryrun-01 --limit 10 --arm both
```

Authorized local comparison template, **only after the latest process inspection**. `live-01/02/03` are spent; use a new run ID (the script rejects existing directories):

```bash
UV_CACHE_DIR=/private/tmp/congressional-globe-uv-cache uv run python -c 'import subprocess, sys; subprocess.run([sys.executable, "tmp/v2_pivot_benchmark.py", "--live", "--backend", "ollama", "--model", "qwen3.8:27b-mlx", "--run-id", "v2-qwen-pivot-compact-live-04", "--limit", "10", "--arm", "both", "--timeout", "45"], timeout=900, check=True)'
```

This schedules twenty sequential calls with a fifteen-minute outer deadline; thinking is disabled (`reasoning_effort`). Each result is appended to `runs/<run-id>/results.jsonl`; inspect that file even if the final report is missing. Do not repeat a spent run ID or call failed jobs automatically. Archive partial evidence before choosing a narrowly targeted follow-up. The next planned local run is the **negative/abstention controls** (`controls.jsonl`), not a repeat of the positive comparison.

For Mini, change `--backend openai --model gpt-5.4-mini`, use a new run ID and `--limit 3 --arm both` for six requests. `.env` loading is built in. Use the same frozen prompt/context when comparing providers; selected cases must be explicitly recorded. No automatic production queue draining.

The embedding runner is ready at `tmp/v2_embedding_benchmark.py`, with durable copy `artifacts/v2-pivot-20261011/embedding_benchmark.py`. Its original validated dry run made zero requests; it has now resumed live as noted above. It plans 22 sequential requests for 100 raw/static document inputs plus ten instructed queries, in batches of five. After confirming the active worker is terminal and inspecting progress/digests, this command resumes the prepared run with a hard outer deadline:

```bash
UV_CACHE_DIR=/private/tmp/congressional-globe-uv-cache uv run python -c 'import subprocess, sys; subprocess.run([sys.executable, "tmp/v2_embedding_benchmark.py", "--run-id", "v2-embedding-dryrun-20261011-r3", "--live", "--resume", "--max-input-texts", "200", "--max-seconds", "900"], timeout=900, check=True)'
```

This generates full 2,560-dimensional 4B vectors and derives a **local first-1,024-dimensions plus L2 normalization** comparison from the same vectors. It does not prove native `/api/embed` 1,024 output matches that projection. Validated batch caches are reusable; failed/unfinished batches are not silently treated as completed. Inspect `plan.json`, progress/failure records, caches and final report under the selected run directory before resuming. Restore the durable script into `tmp/` if needed; keep its path assumptions intact.

The prototype's helpers now all score at most five (`v2-qwen-pivot-compact-refactor-dryrun-20261011/complexity-report.txt`), though it is still an experimental script, **not a production-quality deliverable**, and `ty` flags typing issues in it. The normal project gate does not cover ignored scratch/artifact scripts. Its current durable hash is `619e542a…`; the pre-fix scripts are preserved per run as `script-used.py`. If the tmp copy is missing, restore its durable copy to `tmp/v2_pivot_benchmark.py` from the project directory; its default paths rely on that location.

## Ordered next work

1. [done] Compact prompt/refactor finished and the bounded local QA run was executed and debugged (`live-01/02/03`). Thinking is disabled, the evidence cap is 320, and the pipeline no longer truncates (20/20 `stop`). Still open: inspect the `live-03` answers/quotes case by case, then run the two abstention controls as a separate bounded run.
2. Use a small matched Mini sample to investigate local-model failures or attribution differences. Record observed API usage/cost and finish status; preserve malformed outputs.
3. [done] Embedding interface/gate and the frozen-pool embedding run are complete. Still open: confirm native `/api/embed` returns requested 1,024 versus full 2,560 dimensions for Qwen 4B on tiny inputs; no silent token truncation.
4. [done, saturated] The frozen fifty windows/ten queries were embedded in 22 resumable, hash-keyed batches. All four 4B configs hit@1 10/10, MRR 1.0 — no separation of raw vs static or full vs projected dimensions. Do not re-run unchanged; build a harder, relevance-labeled tier before drawing retrieval conclusions. No full indexing.
5. [done] Compare identical raw text **without versus with separately generated, evidence-linked controlled tags**, including topic aliases and entity candidates. Surface-form mention extraction is not authority resolution. Loose discovery tags cannot satisfy verified speaker/date/party filters. Deterministic tag arm did not recover static's best cases (see the tag-arm section below); a refined or model-backed tag pass remains open.
6. Produce a human review packet, case-by-case scorecard, exact reproduction commands, measured time/tokens/cost and an explicit recommendation: promising pivot, inconclusive, or unsuitable. Only then decide the next larger benchmark. The requested 1,000–5,000 passages / 30–50 human-labeled queries is a later benchmark tier, not the first smoke test.

## Evaluation rules

- Intended-target hit/rank is not precision/recall while other pool windows lack relevance labels. Distractors may be relevant.
- Answer string match is not semantic correctness. Exact evidence quotes do not prove entailment or correct attribution.
- Unknown/null tag families may mean **unannotated**, not verified absence. Preserve coverage and uncertainty.
- Do not collapse multiple speakers, bills, dates or topics into one scalar per page. Mention, speaker, document author, petitioner and cited authority are different roles.
- Controlled experimental IDs are not verified historical authority records. Temporal party/state relationships need independent sourced assertions.
- Lexical search success does not prove semantic/vector retrieval. Compare embedding models on the same frozen inputs and query conventions.
- The current sample is tiny and curated. Report observed throughput/cost, not a corpus-wide accuracy or guaranteed runtime. A larger representative benchmark is needed for institutional deployment.

## Latest implemented tier: abstention controls, native 1024, Tier-2 BM25 baseline, tag arm

All three items below are done and recorded terminally in `PROGRESS.md` (OpenCode `big-pickle`, bounded local calls, $0 API, no production change).

- **Abstention controls**: `v2-qwen-controls-live-02` (4 calls, `control-analysis.json`). All four are correct substantive abstentions but all four fail the schema-unknown contract (`answer`/`answer_evidence` must stay empty; the model writes refusal prose). Runner: `tmp/v2_controls_benchmark.py`; failed pilot documented in `runs/v2-qwen-controls-live-01/note.txt`.
- **Native `/api/embed` `dimensions=1024`**: confirmed real 1,024-dim deterministic output for `qwen3-embedding:4b` (`tmp/embed_1024.json`, `embed_1024b.json`, `embed_1024c.json`; full 2,560 in `embed_full.json`). Any bounded embedding test may now use native MRL projection instead of the local first-1,024 slice.
- **Tier-2 pool + BM25 baseline**: `tier2/pool.jsonl` = 125 windows (50 sample + 75 new, 15/part; `build-report.json`, seed 20261011, input sha `4ab8ef6b…`). `tier2-hard-queries.jsonl` has 19 hard queries (paraphrase ×10, near-miss ×4, repair_clean ×3, repair_garble ×2), all evidence quotes exact-verified. `tmp/score_tier2.py` → `tier2/bm25-report.json`: raw hit@1 **25/29 (MRR 0.931)** vs static **24/29 (MRR 0.908)** — no longer saturated; 4 queries separate raw vs static (`base-target-06` static wins; `base-target-08`, `h-paraphrase-04`, `h-repair-02` raw wins). Intended-target rank only; distractors unlabeled.

## Tag-augmented arm (done, deterministic-only)

The 125-window/29-query tag arm is executed: `raw_text` (and `static_text`) plus an evidence-anchored controlled-tag block per window, scored with the identical `score_tier2.py`/`bench._bm25` path. `tmp/tag_tier2.py` (durable `tier2/tag_tier2.py`, SHA-256 `c8326463a…`) generated `tier2/tagged_pool.jsonl` (SHA-256 `81c9a6ae7…`) plus `tier2/tag-generation-report.json` (deterministic-only, no request log, 0 anchor failures, per-window family coverage with empty families `unannotated`). `tmp/score_tag_arms.py` (durable `tier2/score_tag_arms.py`, SHA-256 `2e471e4a9…`) produced `tier2/tag-arm-report.json`; raw/static ranks reused unchanged from `bm25-report.json`.

Result: overall hit@1 unchanged at 25/29 for both tag arms but MRR drops (raw 0.931 → raw+tags 0.9164; static 0.908 → static+tags 0.9107) and hit@3/5 go 29 → 28; easy-band MRR drops (0.9000 → 0.8577) because `base-target-08` falls rank 1 → 13, while `base-target-06` (static's win) is not recovered and `h-repair-02` (repair-clean) stays rank 2. `base-target-01` improves 2 → 1 and `h-paraphrase-04` is recovered by static+tags. Full verdict sentence lives in the report. All four near-miss queries rank first in all arms; the report's verdict incorrectly calls that band failing. Dakota falls +12 positions relative to raw (1 → 13), or +11 relative to static (2 → 13). The verdict's +9 aggregate is unsupported: emitted ranks sum to +11 worse positions versus raw and +12 versus each query's better raw/static rank. This experiment tests appending tag words to BM25 text, not separate metadata filters or ranking fusion. Net: deterministic surface tags do **not** recover retrieval to static's best cases; a second lexical retry (cleaner topic tokens, pruned aliases) or model-backed tags remain testable before the pivot verdict.

Exact commands (rerun any time; `artifacts/` is gitignored so outputs are local): `uv run python tmp/tag_tier2.py` then `uv run python tmp/score_tag_arms.py`; same hashes regardless of `tmp/` refresh because durable copies live next to the report.

## Before handing off again

Update `PROGRESS.md` and this file with exact run IDs, active PID/session or terminal exit, commands, results, unresolved issues and next executable step. Format Markdown with elevated `npx prettier@3.9.10 --prose-wrap never --write "**/*.md"`. Run `make gate` for code, then `git diff --check`. Commit completed units with a single-line message and no attribution. Never mark unrun controls, provider calls or vector benchmarks complete.

## Latest checkpoint: Mini and streaming progress (supersedes older next steps)

Both Mini workers are terminal; no worker from these runs is live. `v2-mini-matched-20261011-01` (session 87477, exit 0) used six matched first-three-target raw/static calls: 16.691 seconds, 10,502 input / 1,669 output tokens, all six review, approximately $0.015387 at uncached input rates. Exact inputs/context/query and prompt/schema match the saved Qwen comparison; strict schema enforcement differs by provider. `v2-mini-prompt-retry-20261011-01` (session 50188, exit 0) used three raw calls with only clarified prompt wording: 8.259 seconds, 5,606 input / 693 output tokens, one validated/two review, approximately $0.007323. These are diagnostic cases, not held-out accuracy estimates. No source edits or production queue changes.

Evidence: `artifacts/v2-pivot-20261011/mini-matched-review/` contains selection manifest, frozen baseline/retry scripts and prompt hashes, AI reviews, six-case matched and three-case retry human packets (all pending), shell logs and gate log. Per-run results/events/terminal reports are under `runs/<run-id>/`. Cached input details were not recorded; cost figures are upper estimates at [official Mini rates](https://developers.openai.com/api/docs/models/gpt-5.4-mini), not invoices.

The current QA prototype emits flushed `events.jsonl` and stdout showing completed/total/percent, elapsed and ETA (null until the first completion), case/arm, source text and response. ETA is observed pacing, not a promise. This does not retrofit the older embedding runner or every production command. Active/durable logged QA script SHA-256 is `ecce0f203ce1fc7841015365aaae5fef2e014d6051387bee6c3078d5900e4dc0`; the revised prompt is isolated in `mini-matched-review/prompt-retry.py`, not installed as the default. Never overwrite prior frozen scripts or rerun spent IDs.

`make gate` passed (107 tests); ignored prototypes have independent fixture/Ruff/complexity evidence and are not covered by the main gate. Native 1,024/full-dimensional responses have been preserved under `native-dimensions/` with hashes, replacing scratch-only dependencies.

Next actionable unit is **offline preparation of a harder Tier-2 semantic benchmark** over `tier2/pool.jsonl` and `tier2-hard-queries.jsonl`, including compatible cache reuse, explicit dimensions/query instructions, streaming progress and a bounded-call plan. Then test separate metadata filters/fusion and review uncertain historical roles. Existing tagged BM25 results alone do not prove hybrid or hard-filter retrieval. Read the latest ordered checklist in `PROGRESS.md`; do not resume cleanup or repeat known-case prompt tuning as evidence of general quality.

## Current harder-tier checkpoint (supersedes earlier experiment commands)

The harder Tier-2 semantic POC is **terminal**, session 14242 exit 0, run `v2-tier2-embedding-dryrun-20261011-01`. Do not repeat the saturated initial run, the spent Mini diagnostics, or this completed embedding run. Evidence under `embedding-runs/<run-id>/`: 279 inputs /56 batches, 22 reused /34 new local requests, 168.743 seconds, 112,415 new prompt-eval tokens, $0 API. Native 2,560 raw/static both 27/29 intended targets first; local derived 1,024 both 28/29. All targets are within three. The derived vectors are not native 1,024 results. Independent AI review finds both native top alternatives relevant; all human verdicts remain pending.

Offline equal-weight RRF k=60 is complete: native fusion 25/29 and derived fusion 26/29, below semantic-only on this sample. Evidence: `tier2/hybrid-report.json` and `hybrid_benchmark.py`. Separate candidate filters demonstrate plumbing (Rogers 2→1) but not held-out quality; verified speaker/date coverage remains zero. Speaker cues are not resolved speakers. Evidence: `metadata-filters/{report.json,candidate_filters.json,v2_metadata_filters.py}`.

The current static RAG snapshot has 19,803 validated chunks, 63,160,061 characters. Observed new document embedding throughput projects roughly 6.08–6.31 hours for that snapshot, excluding index/export and workload changes. Evidence: `tier2/runtime-estimate/report.json`. This is not a promised full-corpus duration.

Open the **31-entry pending human review packet**:

```bash
open artifacts/v2-pivot-20261011/human-review/index.html
```

It contains 18 lexical relevance pairs, four semantic alternatives and nine Mini cases. Rate support and attribution, save notes and download draft JSON. No verified labels or canonical changes are produced automatically. Builder fixtures and JavaScript syntax passed; browser rendering was unavailable, so rendered UI is unverified. Rebuild with `UV_CACHE_DIR=/private/tmp/congressional-globe-uv-cache uv run python artifacts/v2-pivot-20261011/human-review/builder.py`.

Next bounded experiment is **source-span selection**, not another copied-quote prompt retry: five frozen contexts under `metadata-filters/span-selection/`, source IDs plus controlled roles/topics/unknown statuses. Host validation/materialization supplies literal evidence. Three known cases diagnose failures; two seeded new cases probe transfer, not a representative accuracy benchmark. Live calls remain pending at this checkpoint while root audits runner failure logging and contracts. Read the newest PROGRESS entry before executing any command. Afterwards independently review role/date meaning and add human labels; exact IDs alone are not truth.

All scripts/reports above are **gitignored machine-local artifacts**, not files delivered by cloning Git. Copy `artifacts/v2-pivot-20261011/` plus its referenced canonical snapshot when moving machines. The tracked handoff records paths and results. No inference worker is currently active; production queue inspection remains 1,339 completed /423 review /20,785 pending /zero claimed. Earlier scheduled permissions were time bounded; current small Mini/Ollama testing is authorized by the user's later direct instruction, not an extension of that schedule.

Offline span-selection expectations were frozen before live responses in `metadata-filters/span-selection/review/case-expectations.json`. All quoted excerpts match raw OCR; labels are AI-provisional, not gold. Risks: petition presenter vs petitioners; signed `M. brAyman` letter author vs Davis floor speaker; malformed `186-1` cited-event cue vs proceedings date; continued speech without identity; `Mr. Speaker`/truncated `Mr. BID` false or partial cues; modal `may` is not a date. Singular date scope and out-of-vocabulary topic coverage need a later schema revision. Do not populate authoritative filters from this smoke test. Main `make gate` passed 107 tests; gate log `tier2/gate.log`.

### Span-selection terminal checkpoint and next work

Both five-case workers are **terminal, exit 0**: Mini session45442 (`span-select-mini-20261011-01`) and Qwen session1323 (`span-select-ollama-20261011-01`). Each produced **one valid /four held failures**; valid means schema/reference checks, not verified history. Mini: 14.812 seconds, 21,823 input /2,705 output, zero cached, approximately **$0.028540** at token rates. Qwen: **220.866 seconds**, $0 API, three 45-second timeouts plus one invalid candidate kind; usage exists for only two returned responses (7,048 input /963 output), so total local token usage is unknown. Timeouts are neither historical errors nor zero-token calls. No automatic retries or further calls in this unit.

The valid shared case identifies Sumner as speaking in a citizens’ petition context; Mini additionally distinguishes the presenter role. AI review is provisional. Mini's rejected letter case still mislabels Burnett as a quoted speaker despite correctly distinguishing Brayman and Davis in other assignments. Exact IDs cannot replace role/entailment review. Raw failed/incomplete responses, usage, errors, configuration and source/result events remain under `metadata-filters/span-selection/runs/<run-id>/`. Model-server inventory `ollama-loaded-models.json` records observed local digest `5642e97495e1a088883805981563dcdc4a040c2f53388b7a41d1f24d3622cf7e`, nvfp4 MLX. Frozen runner SHA `c56f9e89899a865b2bf70e51da2e7b45279387a5ca8338298649124629ba837f`. The provider interfaces differ (Mini Responses vs local Chat Completions); timeout/cap/tokenizer differences limit timing conclusions. API cost is a token-price estimate, not an invoice.

**Ordered next steps (supersedes earlier lists):**

1. [ ] Human-review the saved 31-entry viewer and five-case span-selection packets; establish relevance/role judgments and disagreements before claiming quality.
2. [ ] Build an offline next-version contract using short request-local evidence aliases mapped to immutable paragraph/cue IDs, paragraph-specific role evidence, explicit date kind/scope, and explicit unannotated/out-of-vocabulary topics. Split dense mixed windows into smaller tasks. Preserve current frozen experiments; never silently repair IDs or weaken source validation.
3. [ ] Run a newly frozen small held-out test of that contract only after offline checks; compare Mini/local on identical cases, preserve failures and new cost/time estimates. Do not repeat this failed long-ID configuration as a general benchmark or launch full-corpus models.
4. [ ] After human standards and held-out quality are established, package the resumable pilot workflow and operator commands. Current recommendation: proceed with a **reviewed raw-text retrieval pilot**, retain cleanup for demonstrated misses; full metadata enrichment and full indexing are not ready for launch.

Offline smoke check (defaults to mock, fresh generated run ID, **zero provider calls**):

```bash
UV_CACHE_DIR=/private/tmp/congressional-globe-uv-cache uv run python artifacts/v2-pivot-20261011/metadata-filters/span-selection/run_span_selection.py
```

For existing run progress, read `runs/<run-id>/progress.json` or `tail -f runs/<run-id>/events.jsonl` under the span-selection directory. Events preserve source/result and counts/percent/elapsed/ETA; the ETA is observed pacing, not a guarantee. `--live --provider openai --model gpt-5.4-mini` or `--live --provider ollama --model qwen3.8:27b-mlx` explicitly enables a bounded five-case run; **do not rerun the spent IDs or start another test without the next-version preparation above**. A missing tmp copy is irrelevant: this durable script runs in place. These artifacts remain local/ignored; copy them for another machine/harness.

Independent two-provider review is complete at `metadata-filters/span-selection/review/two-provider-case-review.json`; five matched human entries remain pending in `two-provider-human-packet-pending.json`. These are additional to the 31 entries in the HTML viewer. All excerpts and source hashes were checked; no human or image verification is claimed. Main gate passed 107 tests; ignored POC helpers passed separate Ruff/complexity/fixture checks, not main-suite coverage.
