# Reading pilot local-model preflight

Created 2026-10-24. This is an offline preflight record for the exact frozen inputs in `reading-prepare-20261024-03`; it is not launch authorization.

## Frozen inputs

The report binds all 23 candidate IDs (18 primary, 5 confirmation) and preserves SHA-256 and byte lengths for `candidates.jsonl`, `prompt.txt`, and `reply.schema.json`. The primary raw-text selection is 6,367 words. Those counts describe the frozen source files only; no token count is inferred from words, characters, or bytes.

## Installed model evidence

Saved Ollama API snapshots from the completed October 24 vision comparison identify the exact MLX tags, SHA-256 digests, Ollama version 0.40.8, and `vision` capability:

| Model | Digest | Model context limit from saved `/api/show` | Previous probe request options |
| --- | --- | ---: | --- |
| `qwen3.8:27b-mlx` | `5642e97495e1a088883805981563dcdc4a040c2f53388b7a41d1f24d3622cf7e` | 262,144 | `num_ctx=8192`, `max_output_tokens=256`, temperature 0, JSON, thinking false |
| `gemma4:31b-mlx` | `637cc0ff15709212de4aa694be67e3af5e80533ca538c86ad69c53c511e40840` | 262,144 | `num_ctx=8192`, `max_output_tokens=256`, temperature 0, JSON, thinking false |
| `muse-glimmer:30b-mlx` | `015fa21845bead56096c2f8773aff7a2047063507fe82897e662ad544c5b2fa6` | 131,072 | `num_ctx=8192`, `max_output_tokens=256`, temperature 0, JSON, thinking false |

These are historical model and probe records, not fresh readings. The 8,192 context and 256 output values are the earlier six-case vision probe configuration; they do not establish fit for the reading prompt, schema, source windows, or future images. Previous `/api/ps` snapshots included loaded-model state from those old runs and are not used to infer current idleness.

## Token and image fit

The installed manifests do contain model-specific tokenizer/configuration assets as content-addressed blobs (including `tokenizer.json`; Qwen also has `preprocessor_config.json`, while Gemma has `processor_config.json`). The earlier statement that the model store had no tokenizer or processor files was incorrect: assets are present, but this inspection did not establish a compatible local implementation capable of counting the exact request as Ollama renders it. The `tokenizers`, `transformers`, `mlx`, and `sentencepiece` Python packages are absent. The installed Ollama binary contains MLX tokenizer code and a string for an internal runner `POST /v1/tokenize` route. The official Ollama API documentation does not document that route as public, and binary-string evidence does not establish that it can be called without loading a model or that it counts images. I did not call it.

Actual text and image token fit therefore remain **unknown** for every candidate. The exact image manifest was not part of the frozen inputs to this report, and neither word/byte counts nor model-level aggregate counts establish fit. A model-only count cannot authorize launch: authorization would require per-unit exact request/template fingerprints and exact image byte hashes, plus a model-specific tokenizer/processor identity and explicit context/output reserve. Image token cost must be derived from the exact image payload and that model's verified processor behavior; estimates based only on image dimensions or bytes are insufficient.

The named technical follow-up is **model-specific offline tokenizer/processor binding**: resolve the content-addressed tokenizer/config blobs from each exact Ollama manifest digest; use a pinned, compatible implementation and verify its chat-template parity with the installed MLX runner; bind each unit's exact prompt, OCR text, schema/template, and image-byte hashes; then record separate text/image counts and aggregate context plus output reserve. A compatible image processor path has not yet been identified. Do not install packages or call undocumented tokenization routes as a shortcut to a passing result. Until that work establishes exact per-unit fits, the typed checker must keep token budget unknown and launch readiness false.

## Runtime state and safe next steps

Elevated OS process inspection at 2026-10-24 21:48Z identified Ollama PID87597 (started Oct21 20:46:52) and review-desk PID68381. No cleanup, reading, vision, or role worker matched. Read-only `/api/tags`, `/api/show` for each exact candidate, `/api/version`, and `/api/ps` completed at 21:48:41Z; `/api/ps` returned an empty model list. The evidence and hashes are in `current-runtime/`. These are point-in-time observations. No inference, warmup, tokenization, download, or server setting change occurred.

After the image manifest is supplied, bind every requested image to exact bytes and candidate/crop source IDs, complete source expectations, then rerun the typed checker with explicit token-fit evidence. A feasible offline follow-up is to use Ollama's installed model-specific tokenizer assets through a pinned, compatible local tokenizer implementation and verify parity with the MLX runner/template; the full image processor path must also be identified and pinned. Keep each model's report separately versioned. A missing digest, unsupported tag, missing `vision` capability, unknown token budget, or unknown live process state must continue to block launch.

## Independent review of the image planner

The observed `plan-index.json` is planning evidence only: it has 18 primary units, 19 planned regions, zero fetched images, pending source expectations, and `geometry_coverage_complete=false`. Its model-independent totals cannot authorize any model run or establish text/image token fit.

Two concrete provenance/accounting issues need correction before relying on a resumed fetch report. `TransferBudget.__init__` totals every `*.receipt.json` under the output directory by parsing only the receipt's declared byte count; it does not check that the corresponding payload exists or matches that receipt. A missing or corrupted payload paired with a small/forged receipt can understate the shared transfer budget. Validate each receipt against its adjacent payload (including size and SHA-256) before accepting its bytes into the budget. Also, `new_transfer_bytes` is assigned `budget.used`, which includes receipts already present when the run starts; on a resumed fetch this reports cached bytes as newly transferred. Capture the initial persisted total separately and report actual run transfer bytes as the delta, while retaining the total for cap enforcement.

These are source-review findings, not claims that either condition occurred in the current plan-only run. The plan-only artifact shows no new image transfer and does not exercise those paths.

No inference, warmup request, tokenization request, model download, server change, review submission, or canonical source edit occurred in this unit. The machine-readable decisions and source hashes are in `report.json`.
