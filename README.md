# Congressional Globe research foundation

Prepare the five parts of the 39th Congress, first session for keyword, OCR-tolerant and semantic search, with historical filters and precise source citations. The data/backend workflow is under development; a complete research search service or web interface is not shipped yet.

**[MASTER_PLAN.md](MASTER_PLAN.md)** contains the goal, current results, remaining milestones, commands and progress. All agents follow and update that one document.

## Get started

Install **uv** and **make**, then run from this folder:

```bash
uv sync --all-groups
```

Original source files and generated artifacts are not bundled in Git. On another machine, copy the sources and required resources or follow the [setup and operator notes](MASTER_PLAN.md#8-operator-commands-and-current-limitations). The prepared machine already has the canonical files and experiment evidence.

## Read the current data

Under `artifacts/runs/static-final-20261011/`:

- `canonical_pages.jsonl`: original/accepted text, source locations and correction history.
- `chunks.jsonl`: existing page-bounded retrieval passages and citations.
- `manual_review.jsonl` and `validation_report.json`: review items and consistency checks.

The export is a saved snapshot; it does not automatically reflect later cleanup-worker results. Missing dates and uncertain metadata remain explicit. Validation does not certify historical accuracy.

## Existing cleanup commands

```bash
make status
```

This reads the existing cleanup queue. If you deliberately want to prepare or refresh the existing static export, run `make run-static`. It makes no model requests but can update generated files.

Optional `make run-qwen`, `make run-gemma` and `make run-openai` resume **OCR cleanup**, for up to one hour/1,000 requests. They do not run the future tagging/search workflow. Run one worker at a time. Local workers need the configured Ollama server/models; OpenAI needs `OPENAI_API_KEY` in ignored `.env` and incurs API charges. See the master plan before starting or resuming a job.

## Check changes

```bash
make gate
```

Runs formatting, code checks and tests. Node.js/npm is needed for the Markdown formatter; formatting may change files. Detailed experiment results, human-review instructions and the next development task are maintained only in the master plan.
