# Tag-augmented arm: does evidence-linked metadata recover retrieval from raw OCR?

You are continuing the V2 pivot in `/Users/sflynn/Downloads/congressional globe project`. Goal: test whether **unchanged OCR plus separately generated, evidence-linked controlled tags** retrieves as well as the cleaned static text — the decisive step in deciding whether the ~24.7-hour OCR cleanup queue is worth running.

## Start here

1. Read `AGENTS.md`, `PROGRESS.md` (latest V2 sections), `V2_HANDOFF.md`, `V2_PIVOT.md`, and `V2_EMBEDDING_MODELS.md`. Record the latest run IDs and checkpoint before starting.
2. Read the Tier-2 evidence: `artifacts/v2-pivot-20261011/tier2/{pool.jsonl,tier2-hard-queries.jsonl,bm25-report.json,build-report.json}` and the score harness `tmp/score_tier2.py` (durable copy available next to the report if `tmp/` rebuilds). The 125-window pool and 29-query manifest are already validated; do not relabel or rebuild them.
3. Confirm no benchmark/model worker or Ollama runner is active before any local request, and no production job is claimed.

## The experiment

Compare retrieval on the **same windows and queries** with four index arms so raw-vs-tags-vs-static separate cleanly:

| Arm | Document text indexed |
| --- | --- |
| `raw` | `raw_text` alone (existing baseline, do not recompute) |
| `raw+tags` | `raw_text` plus an evidence-linked tag block appended per window |
| `static` | `static_text` alone (existing baseline, do not recompute) |
| `static+tags` | `static_text` plus the same tag block (control against arm `raw+tags`) |

Use the identical BM25 scorer and metric code path already in `score_tier2.py` (intended-target rank, hit@1/3/5, MRR overall and per band; separated queries listed). Report `raw+tags` vs `raw`, then `raw+tags` vs `static`, and note which queries change rank and why.

## Tag generation requirements

- **Evidence-linked first**: every tag must anchor to text actually present in the window (surface-form mention with an exact substring or character offsets). Do not emit tags absent from the text.
- **Controlled vocabularies**: use the ten allowed topic IDs from `targets.jsonl` `expected_tags.topics` (e.g. `reconstruction_and_readmission`, `pacific_railroad_route`). Topic topics may use alias words (e.g. "reconstruction", "amendment", "railroad") to match queries.
- **Entity families**: `person_mentions`, `place_mentions`, `legislation_mentions`, `speakers`, `dates` are **candidate mentions**, not authority resolution. Do not assign one scalar to mixed passages; keep multiple candidates and record the family each came from.
- **Unknowns stay explicit**: any family with no candidates is `unannotated`, never "verified absent". Which families were empty for a window is part of the coverage report.
- **Deterministic first**: build a provider-free tagger (surface-form/lexicon matching against the controlled vocabularies, plus casing/alias handling for the ones already present in `targets.jsonl`). Only if you can show the deterministic tagger is a straw man and you have the user's bounded V2 authorization may you add a **separate, bounded** Ollama/GPT-Mini tagging pass: at most 20 sequential requests, one at a time, 45 s/request, 900 s outer deadline, new run ID (reject reused directories), long `-L` style logging of usage/time/hash/raw response, tags written as an artifact that mirrors `score_tier2.py` verification. $0 local charge expectation; paid Mini calls must record tokens/cost.
- **No corpus mutation**: write `tagged_pool.jsonl` (new `tags` block per window + `tags_hash`) under `artifacts/v2-pivot-20261011/tier2/`; never touch `raw_text`, `static_text`, hashes, anchors, the production queue, or `tmp/performance/`.

## Constraints

- Use `uv` with `UV_CACHE_DIR=/private/tmp/congressional-globe-uv-cache`; Pydantic v2 at every external-data boundary; scripts under `tmp/` with a durable copy synced into the tier-2 artifact directory; every probe and its expected evidence quote verified as an exact substring (reject anything that fails verification rather than papering over it).
- No full-corpus model work, no downloads, no re-OCR, no image validation. Do not treat `None` families, scheme-validated tags, or rank changes as historical fact.
- Keep helpers at complexity ≤5; the project gate covers `src/`/`tests/` only, but follow it for the harness too. Avoid adding broad low-value tests.

## Deliverables

1. `tier2/tag-generation-report.json`: method, providers used (or "deterministic-only"), per-window coverage per family, input/hash records, and any request log with usage/time.
2. `tier2/tag-arm-report.json`: one table for the four arms above — overall and per-band hit@1/3/5, MRR, and the full list of separated queries with their rank diffs.
3. A single-sentence verdict fabric: does `raw+tags` reach/exceed `static`? Which bands still fail (e.g. repair-clean, near-miss)? Flag anything that remains inconclusive.
4. `PROGRESS.md` + `V2_HANDOFF.md` updated with run IDs, commands, hashes, results, and the next executable step; format Markdown with `npx prettier@3.9.10 --prose-wrap never --write "**/*.md"`; then `make gate` (script mode: Ruff + ty + complexity + pytest) and `git diff --check`; commit with a single-line message and no agent attribution. Do not mark the grounded-answer/human-review scorecard complete — that remains pending.
