# V2 pivot handoff for any AI harness

## Start here

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
5. Compare identical raw text **without versus with separately generated, evidence-linked controlled tags**, including topic aliases and entity candidates. Surface-form mention extraction is not authority resolution. Loose discovery tags cannot satisfy verified speaker/date/party filters.
6. Produce a human review packet, case-by-case scorecard, exact reproduction commands, measured time/tokens/cost and an explicit recommendation: promising pivot, inconclusive, or unsuitable. Only then decide the next larger benchmark. The requested 1,000–5,000 passages / 30–50 human-labeled queries is a later benchmark tier, not the first smoke test.

## Evaluation rules

- Intended-target hit/rank is not precision/recall while other pool windows lack relevance labels. Distractors may be relevant.
- Answer string match is not semantic correctness. Exact evidence quotes do not prove entailment or correct attribution.
- Unknown/null tag families may mean **unannotated**, not verified absence. Preserve coverage and uncertainty.
- Do not collapse multiple speakers, bills, dates or topics into one scalar per page. Mention, speaker, document author, petitioner and cited authority are different roles.
- Controlled experimental IDs are not verified historical authority records. Temporal party/state relationships need independent sourced assertions.
- Lexical search success does not prove semantic/vector retrieval. Compare embedding models on the same frozen inputs and query conventions.
- The current sample is tiny and curated. Report observed throughput/cost, not a corpus-wide accuracy or guaranteed runtime. A larger representative benchmark is needed for institutional deployment.

## Before handing off again

Update `PROGRESS.md` and this file with exact run IDs, active PID/session or terminal exit, commands, results, unresolved issues and next executable step. Format Markdown with elevated `npx prettier@3.9.10 --prose-wrap never --write "**/*.md"`. Run `make gate` for code, then `git diff --check`. Commit completed units with a single-line message and no attribution. Never mark unrun controls, provider calls or vector benchmarks complete.
