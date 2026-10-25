# Congressional Globe research foundation

Prepare the five parts of the 39th Congress, first session for keyword, OCR-tolerant and semantic search, with historical filters and precise source citations. The data/backend workflow is under development; a complete research search service or public research interface is not shipped yet.

**[MASTER_PLAN.md](MASTER_PLAN.md)** contains the goal, current results, remaining milestones, commands and progress. All agents follow and update that one document.

Use the browser review desk below to answer questions and grade samples. Agents pick up submitted answers when they next work on the project.

## Get started

Install **uv** and **make**, then run from this folder:

```bash
uv sync --all-groups
```

Original corpus source files and most generated artifacts are not bundled in Git. The small Wikipedia authority-candidate bundle below is included. On another machine, copy the sources and required resources or follow the [setup and operator notes](MASTER_PLAN.md#8-operator-commands-and-current-limitations). The prepared machine already has the canonical files and experiment evidence.

## Review samples

```bash
make review
```

Open [the review desk on this Mac](http://127.0.0.1:8501), or [from another device on the same network](http://10.0.0.56:8501). Choose a pending review, enter your name, read the source excerpts, and answer the questions. **Save draft** saves unfinished answers; **Submit review** sends a completed review to the agent inbox. Unsaved typing is not preserved. Submitted answers appear under **Submitted**, then **History** after an agent applies them. You can submit a revision without erasing your previous answer.

To try an invented practice example first, use `make review-demo`. It does not call a model or change historical data. Stop the server with Ctrl+C. The desk is available on your local network. No login or access code is needed for this single-user local tool. The LAN IP may change when your network changes.

Saved reviews live in `artifacts/human-review/reviews.sqlite`, outside Git. Stop the desk before copying that file as a backup or transferring it to another machine. Agents archive submitted answers as portable JSON alongside plan updates. Existing paper reviews are linked from [HUMAN_REVIEW.md](HUMAN_REVIEW.md).

## Compare OCR with the scan

Open [Source images](http://10.0.0.56:8501/?view=source-images) in the review desk. Four small examples show unchanged OCR and the corresponding original print, including the damaged petition and an individual number. Images are cached locally; opening this view makes no model request or external download.

To retrieve another paragraph from the local OCR sources:

```bash
uv run globe scan crop --item congressionalglo7392unit --leaf 328 --paragraph par_000328_000032 --output artifacts/my-scan --fetch
```

Without `--fetch`, this only prepares an offline plan. Repeating the same command verifies and reuses cached files. A different target needs a new output directory. For a precise word/patch, add `--start 34 --end 37 --expected GCO --padding 16`; offsets refer to the **original OCR**, not corrected text. The tool downloads only requested image regions and records source identity, hashes and geometry. An image view does not apply a correction. Details and limits are in the master plan's **S0** section. A tiny local Qwen vision test also corrected the damaged number and recovered a missing word from the scan; results, repeatable commands and limitations are in **S1**. This is a review experiment, not automatic corpus correction.

## Read the current data

Under `artifacts/runs/static-final-20261011/`:

- `canonical_pages.jsonl`: original/accepted text, source locations and correction history.
- `chunks.jsonl`: existing page-bounded retrieval passages and citations.
- `manual_review.jsonl` and `validation_report.json`: review items and consistency checks.

The export is a saved snapshot; it does not automatically reflect later cleanup-worker results. Missing dates and uncertain metadata remain explicit. Validation does not certify historical accuracy.

## Look up congressional members

A small, source-linked Wikipedia dataset is included for member and district lookups:

```bash
uv run python -m congressional_globe.wikipedia query artifacts/authorities/wikipedia-39th-20261022/dataset/records.jsonl --where name=Stevens
```

It contains unverified source-derived candidates, not completed speaker attribution. [Replay commands and limitations](MASTER_PLAN.md#query-and-rebuild-the-wikipedia-mini-dataset) are in the master plan.

## Existing cleanup commands

```bash
make status
```

This reads the existing cleanup queue. If you deliberately want to prepare or refresh the existing static export, run `make run-static`. It makes no model requests but can update generated files.

Optional `make run-qwen`, `make run-gemma` and `make run-openai` resume **OCR cleanup**, for up to one hour/1,000 requests. They do not run the future tagging/search workflow. Run one worker at a time. Local workers need the configured Ollama server/models; OpenAI needs `OPENAI_API_KEY` in ignored `.env` and incurs API charges. See the master plan before starting or resuming a job.

## Query Ollama logs

Retrieve only matching events, with a hard8KB JSON response limit:

```bash
uv run globe ollama logs query --include "context canceled" --limit 3 --raw-bytes 160 --max-output-bytes 8192
```

Add ISO8601 `--since` / `--until` bounds, or `--status 500`, to narrow the query. Pass `--cursor` from `next_cursor` with the same filters for the next page. The tool is read-only. If one event cannot fit, it returns a small error; it never overrides the output cap. A change during a query returns `source_changed`; retry deliberately when the log is stable. Oversized-record errors are terminal, not cursors to repeat. Full options: `uv run globe ollama logs query --help`.

## Check changes

```bash
make gate
```

Runs formatting, code checks and tests. Node.js/npm is needed for the Markdown formatter; formatting may change files. Project status and the next development task are maintained in the master plan.
