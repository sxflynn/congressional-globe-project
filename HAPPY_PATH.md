# Operator happy path

Updated: 2026-10-11. The implemented workflow builds canonical/RAG files. Codex benchmarks small samples and builds the tooling; the human explicitly starts production processing. The larger historical-enrichment architecture in `PROJECT_GOAL.md` remains a roadmap.

## Model choice from small POCs

| Model | Eight-case elapsed time | Provisional expected-text agreement accepted | Failures/holds | Decision |
| --- | --: | --: | --- | --- |
| Ollama `qwen3.8:27b-mlx` | 51.97 s | 8/8 | No benchmark failures/holds | Preferred local POC candidate; $0 API charge |
| OpenAI `gpt-5.4-mini` | 11.51 s | 6/8 | One image-review hold; one punctuation proposal withheld by later validation | Faster cloud candidate; about $0.00657 for these eight calls |
| Ollama `gemma4:31b-mlx` | 42.31 s | 7/8 | Missed the index glyph error | Alternative local candidate |
| Ollama `muse-glimmer:30b-mlx` | 71.27 s | 2/8 | Five schema/JSON failures; one accepted response missed an error | Do not use for this workflow with the tested configuration |

These are five problem paragraphs plus three controls, with provisional text-context expectations, not image gold or a statistically representative performance sample. Qwen/Gemma/initial Mini used the earlier prompt; Muse used the current punctuation-preserving prompt. A one-case Mini retest with the revised prompt corrected the index glyph while preserving its comma (1.37 s, about $0.00080). The comparison is therefore exploratory rather than a controlled same-prompt model ranking. The stronger bounded runtime check also demonstrated review/failure handling: six requests, one completed patch result, five review records. A completed record does not mean every OCR error was fixed.

The local inventory lists Qwen, Gemma and Muse, with no separately named Meta Llama model. Do not download a model or claim a Llama result without a specified model and a new explicit request. Never repeat these POCs merely because a goal continuation arrives.

For 22,547 candidate calls, earlier eight-case means projected about 9.0 hours/$18.53 for Mini and 40.7 hours/$0 API charge for Qwen. These exclude retries, review, export, local electricity/hardware and paragraph-length variability. Harder bounded examples took longer and produced more holds. Estimate commands and benchmark evidence are described in `RUNBOOK.md`; these figures are planning estimates, not completion promises.

## One command to run the full implemented workflow

From this locally prepared project directory, the human can explicitly opt into Qwen processing:

```bash
uv run globe static-first --root . --run-id static-final-20261011 \
  --lexicon artifacts/static-audit-20261011/supplemented-lexicon.txt \
  --backend ollama --model qwen3.8:27b-mlx \
  --benchmark-summary artifacts/benchmarks/context-audit-20261011/providers/context-random-qwen-20261011/summary.json
```

Inspect `globe cleanup status --run-directory artifacts/runs/static-final-20261011 --run-id static-final-20261011` first and wait for any existing worker to exit. This command verifies inputs/caches, resumes the same residual queue, records a preflight estimate, processes the pending snapshot sequentially, validates patches, then exports canonical pages, RAG chunks, manual review and a validation report under the run directory. It can run for many hours. Codex has not started it. To switch to Mini, replace backend/model and use the matching Mini benchmark summary; the run/inputs remain identical. Provider/model identity matching is validated. Missing metadata, unknown dates, pending jobs and review decisions remain explicit.

The lexicon and benchmark evidence are local ignored artifacts; this command assumes the prepared machine. A future portable corpus release must bundle manifests/required resources or documented reconstruction steps. Do not assume a fresh Git clone includes these artifacts.

## Run for about an hour instead

```bash
uv run globe cleanup run --run-directory artifacts/runs/static-final-20261011 \
  --run-id static-final-20261011 --backend ollama --model qwen3.8:27b-mlx \
  --limit 1000 --max-seconds 3600 --progress-interval 30
```

This saves results per job and stops claiming jobs after one hour or 1,000 requests. The last in-flight request can finish past the time budget. Rerun to resume. This worker updates SQLite; it does not regenerate exports. After it exits, refresh exports without new model calls:

```bash
uv run globe static-first --root . --run-id static-final-20261011 \
  --lexicon artifacts/static-audit-20261011/supplemented-lexicon.txt \
  --backend none --ai-limit 0
```

A passing validation report proves record/ledger consistency, not full OCR accuracy. Review records are part of the output; they are not automatically resolved by draining the queue. Rich historical attribution/tagging/search stages remain future work. Embeddings are not required to consume canonical/RAG JSONL.

## Evidence and current boundaries

- Full static exports: 5,412 pages, 296,995 paragraphs, 209,609 static patches, 19,803 chunks; independent ledger/source verification passed.
- Full audit and supplemental word-list work reduced model load without broad confidence-based submission. Static source fingerprints and current exported hashes were rechecked during the final workflow audit.
- Small benchmark evidence: `artifacts/benchmarks/context-audit-20261011/`; bounded provider-switch/export proof: `artifacts/runs/e2e-final-20261011/`.
- The current production SQLite queue has additional saved model results since the original static snapshot. Those human-run results are separate from Codex's small POCs; refresh exports explicitly to include them. The original static snapshot remains verified.
- Multiprocessing POC is verified against production output hashes, but its production integration and failure-state checks remain pending. Ollama stays sequential.
