# Project preferences

- Use `uv`; do not create or manage raw Python virtual environments.
- Use Pydantic v2 at every external-data boundary.
- Keep raw OCR and Internet Archive metadata immutable. Derived artifacts belong under `artifacts/`.
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

# Required gates

Run these before handing off code:

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

# Current corpus reminder

- This project covers the five parts of the 39th Congress, 1st Session. Do not label a single part as the entire Congressional Globe.
- Treat catalog-level and edition-level dates as separate facts; preserve both with sources.
