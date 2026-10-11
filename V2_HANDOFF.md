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

Authorized local comparison, **only after checking the latest active state in PROGRESS**:

```bash
UV_CACHE_DIR=/private/tmp/congressional-globe-uv-cache uv run python tmp/v2_pivot_benchmark.py \
  --live --backend ollama --model qwen3.8:27b-mlx \
  --run-id v2-qwen-pivot-20261011 --limit 10 --arm both --timeout 45
```

This schedules twenty sequential calls with a fifteen-minute budget. Each result is appended to `runs/<run-id>/results.jsonl`; inspect that file even if the final report is missing. Do not repeat this run ID or call failed jobs automatically. Archive partial evidence before choosing a narrowly targeted follow-up.

For Mini, change `--backend openai --model gpt-5.4-mini`, use a new run ID and `--limit 3 --arm both` for six requests. `.env` loading is built in. Use the same frozen prompt/context when comparing providers; selected cases must be explicitly recorded. No automatic production queue draining.

The prototype has known complexity violations above five in several helpers. It is an experimental script, **not a production-quality deliverable**; refactoring remains required. The normal project gate does not cover ignored scratch/artifact scripts. Preserve the exact script snapshot/hash used for a measured run before refactoring it. If the tmp copy is missing, restore its durable copy to `tmp/v2_pivot_benchmark.py` from the project directory; its default paths rely on that location.

## Ordered next work

1. Check the latest labels and dry-run report, then run/reconcile the bounded local QA/tag comparison if it has not already started. Inspect every claim, not just schema success. Run the two abstention controls separately after confirming the positive run is terminal.
2. Use a small matched Mini sample to investigate local-model failures or attribution differences. Record observed API usage/cost and finish status; preserve malformed outputs.
3. Finish/review the embedding interface and run `make gate`. Confirm native `/api/embed` returns requested 1,024 versus full 2,560 dimensions for Qwen 4B on tiny inputs; no silent token truncation. Measure request time on this Mac.
4. Embed the frozen fifty windows and ten queries in small batches with resumable, hash/config-keyed output. Compare raw/static 4B at 1,024/full dimensions; normalize correctly, use Qwen query instructions, no document instruction. Keep each vector configuration in a separate namespace. Test 8B only if the 4B result warrants it; no full indexing.
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
