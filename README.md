# Congressional Globe corpus factory

This project creates a provenance-first, RAG-ready corpus from Internet Archive hOCR, DjVu XML, and page-number maps. It does not alter source OCR files and does not submit AI jobs unless an operator explicitly requests it.

For cloud commands, copy `.env.example` to `.env` and set `OPENAI_API_KEY` locally. The CLI loads that file automatically; `.env` is ignored by Git. Never paste an API key into chat or commit it.

## Quick start

```bash
uv sync --all-groups
uv run globe inventory
uv run globe extract --identifier congressionalglo7395unit
uv run globe build-rag --run-id local-demo
```

The output is written to `artifacts/<run-id>/`. See `RUNBOOK.md` for source context and `AGENTS.md` for required workflow gates.

## Commands

- `inventory` validates expected source files and can calculate SHA-256 checksums.
- `extract` writes canonical page and paragraph JSONL for one downloaded part.
- `build-rag` creates page-bounded retrieval chunks and a collection manifest.
- `prepare-ai` creates OpenAI Batch-compatible requests locally; it makes no API calls.
- `submit-batch` requires `OPENAI_API_KEY` and `--confirm-submit`.
- `reconcile-ai` validates Batch results, applies only validated patches, and sends malformed responses to a separate review queue. It never changes raw OCR or canonical extraction.

## Resumable local or cloud cleanup

The cleanup queue is a typed SQLAlchemy/SQLite job store. It lets a local or cloud worker claim only unfinished records from the same run. Ollama is always sequential; it uses the required non-secret client placeholder `api_key="ollama"` and never reads `OPENAI_API_KEY`.

```bash
uv run globe cleanup init --run-directory artifacts/runs/local-v1 --run-id local-v1 \
  --paragraphs artifacts/extraction/congressionalglo7395unit_paragraphs.jsonl
uv run globe cleanup run --run-directory artifacts/runs/local-v1 --run-id local-v1 \
  --backend ollama --model qwen3.8:27b-mlx --limit 100 --progress-interval 30
uv run globe cleanup status --run-directory artifacts/runs/local-v1 --run-id local-v1
uv run globe cleanup export --run-directory artifacts/runs/local-v1 --run-id local-v1 \
  --output artifacts/runs/local-v1/normalized.jsonl
```

To continue the same unfinished queue with the cloud API, replace `--backend ollama` with `--backend openai` and provide an OpenAI model. The ordinary cloud path requires `OPENAI_API_KEY`; the existing Batch commands remain a separate, explicit cost-optimized export/submission path. `gpt-5.4-mini` is the validated cloud default; the Responses path pins `temperature=0` and uses a strict JSON schema shared with the Batch request builder. The cleanup prompt defines `expected` as the complete replaced span, forbids no-op and duplicate edits, and asks for every confident line-wrap join.

Each run records `jobs.sqlite`, `events.jsonl`, provider response files, and an exportable derived JSONL result. A record with malformed JSON, an invalid patch, or a provider failure becomes `review`; raw hOCR is never changed. Resolved edits are de-duplicated and sorted deterministically before application. `RUNBOOK.md` records a static-cleanup investigation that would resolve most dehyphenation without a model call once the extractor retains word geometry.

## Required checks

```bash
uv run ruff format --check .
uv run ruff check .
uv run ty check
uv run complexipy src tests --max-complexity-allowed 5
uv run pytest
npx prettier@3.9.10 --prose-wrap never --write "**/*.md"
```
