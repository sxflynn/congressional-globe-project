# Project goal

Build a high-quality, portable, structured historical corpus from all five locally collected parts of the 39th Congress, 1st Session of _The Congressional Globe_, supporting historical research, full-text and structured queries, semantic/vector search, and RAG independently of embedding models, vector databases, or search frameworks. Canonical JSON/JSONL remains authoritative for original and accepted cleaned text, immutable-source references, and correction provenance. Separate, versioned authority and enrichment datasets provide evidence-backed speakers, temporal party/state/service affiliations, subjects, legislation, entities, dates and boundaries. Derived retrieval units retain exact canonical/source links; embeddings and indexes are disposable, rebuildable products.

Codex builds the disciplined, reproducible workflow: schemas, prompts, orchestration, validation, retry/batching, incremental caching, call audits, provenance, review and exports. Future explicitly authorized LLM and deterministic/authority-backed stages perform substantive enrichment with well-defined inputs and structured outputs. Preserve model/prompt/configuration versions, evidence, uncertainty and prior results; never silently overwrite canonical text or equate model proposals with verified facts. Do not assign a single speaker, party, topic, bill or date to mixed passages or invent dates for coverage. Finish the reliable corpus first; the expanded goal does not authorize immediate full enrichment, re-OCR, or original-image visual validation.

Read `PROJECT_GOAL.md` for the full architectural requirements, current schema mapping and phased roadmap. Use it to guide short-term cleanup, identity, provenance and chunking decisions without implementing the entire roadmap automatically.

Read `V2_PIVOT.md` for the active alternative experiment: organize and enrich untouched OCR for retrieval rather than require further OCR repair first. Preserve the existing cleanup path and outputs. Use Luna delegates for bounded sample preparation, evaluation and documentation; track exact experiment state in `PROGRESS.md`. Evaluate retrieval, controlled tagging and grounded answers separately before recommending a pivot.

# Project preferences

- Read `PROGRESS.md` before starting work and `PROJECT_GOAL.md` before making architectural/schema decisions. Follow its ordered next-step checklist and resume commands; do not repeat completed POCs or start full-corpus model processing. New user instructions take precedence.
- Update `PROGRESS.md` after each unit of work and before handing off: record completed checks, exact run IDs, active or stopped processes, evidence paths, limitations, and the next executable step. Keep README usage and RUNBOOK findings consistent with it; never mark an unchecked result complete.

- Use `uv`; do not create or manage raw Python virtual environments.
- Use Pydantic v2 at every external-data boundary.
- Keep raw OCR and Internet Archive metadata immutable. Derived artifacts belong under `artifacts/`.
- Use `tmp/` for disposable scratch files, POC outputs, and intermediate experiments that should not be committed. Git ignores its contents except `tmp/.gitkeep`; retain durable benchmark evidence and final derived artifacts under `artifacts/`.
- AI work is opt-in: never submit an API request or alter corpus text without an explicit command.
- AI text cleanup must be patch-based, validated, and recorded in an edit ledger.
- Prefer streaming parsers for hOCR/DjVu sources; the files are large.
- Preserve source anchors: Internet Archive identifier, part, scan leaf, printed page, hOCR IDs, and geometry.
- Cleanup state lives in `artifacts/runs/<run-id>/jobs.sqlite`; inspect its status before starting another worker.
- Ollama uses the non-secret placeholder API key `ollama` and must run one request at a time.
- Reuse an existing cleanup run ID to resume pending jobs or change provider; do not recreate its queue.
- Benchmark substantive paragraphs before scaling a local model across the corpus.
- Always run `npx prettier@3.9.10 --prose-wrap never --write "**/*.md"` when editing markdown files, and if you are Codex, request elevated permissions to run it.
- After completing a unit of work, commit it using a single line commit message, with no agent attribution.

## Required gates

Run `make gate` before handing off code (with elevated permissions for its Prettier formatter). It applies Ruff/Markdown formatting and executes all checks/tests below; use it as the single gate entry point. The individual required checks are:

```bash
uv run ruff format --check .
uv run ruff check .
uv run ty check
uv run complexipy src tests --max-complexity-allowed 5
uv run pytest
npx prettier@3.9.10 --prose-wrap never --write "**/*.md"
```

- Maximum permitted cyclomatic complexity is **5**. Refactor instead of adding an exception.
- Keep tests focused on core behavior and failure modes; do not add broad low-value test suites.

## Current corpus reminder

- This project covers the five parts of the 39th Congress, 1st Session. Do not label a single part as the entire Congressional Globe.
- Treat catalog-level and edition-level dates as separate facts; preserve both with sources.
