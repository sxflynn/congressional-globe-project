# Congressional Globe

Turn the five parts of the 39th Congress, 1st Session into cleaned, searchable text files. Original OCR files are kept unchanged.

## 1. Set up

You need **uv** and **make**. Open a terminal in this project folder, then install the Python dependencies:

```bash
uv sync --all-groups
```

The source files belong in the project folder. The Make commands also need `artifacts/static-audit-20261011/supplemented-lexicon.txt`, the word list used for cleanup. It is already prepared on this machine; a fresh clone needs the [word-list setup](RUNBOOK.md#word-list-setup-on-macos).

## 2. Prepare the files and queue

```bash
make run-static
make status
```

This reads all five parts, fixes straightforward line-break errors, writes the output files, and queues passages needing further cleanup. It makes no model requests. Allow several minutes. `make run-workflow` does the same thing.

## 3. Run further cleanup (optional)

Choose **one** of these commands:

| Command           | What it uses                           |
| ----------------- | -------------------------------------- |
| `make run-qwen`   | Local Qwen; no API charge              |
| `make run-gemma`  | Local Gemma; no API charge             |
| `make run-openai` | OpenAI GPT-5.4 Mini; paid API requests |

For a local model, start your Ollama-compatible server at `http://127.0.0.1:11434` first. It must have `qwen3.8:27b-mlx` or `gemma4:31b-mlx` available for the corresponding command. These are the model names configured for this machine.

For OpenAI, if you do not already have `.env`, create it:

```bash
cp .env.example .env
```

Open `.env` in a text editor and replace the placeholder with your OpenAI API key. The program loads it automatically; Git ignores this file.

Each worker runs for up to **one hour or 1,000 passages**, whichever comes first. It finishes an in-flight request before stopping and saves progress as it goes. Run the same command again to continue. Run only one worker at a time.

In another terminal, check progress with:

```bash
make status
```

`pending` means work remains; `completed` means proposed corrections passed validation; `review` means the passage needs attention. A completed passage may still contain OCR errors.

`estimated_pending_hours` estimates model processing time from recorded request timings; human review and export time are extra.

## 4. Refresh and find your results

After the worker stops:

```bash
make run-static
```

This incorporates saved corrections and refreshes the files without making more model requests. Results are in **`artifacts/runs/static-final-20261011/`**:

- `canonical_pages.jsonl` — original and cleaned text, page locations, and correction history.
- `chunks.jsonl` — smaller passages for search and retrieval.
- `manual_review.jsonl` — passages still needing attention.
- `validation_report.json` — output consistency checks.
- `events.jsonl` — worker progress; new worker runs include before/after text and accepted edits.

Uncertain text and missing dates remain marked for review or unknown; validation does not mean every OCR error has been fixed.

## Check the project

```bash
make gate
```

Runs the formatters, code checks, and tests. You also need Node.js/npm for the Markdown formatter. Formatting can change files.

For troubleshooting and detailed commands, see [RUNBOOK.md](RUNBOOK.md). For model comparisons and estimated time/cost, see [HAPPY_PATH.md](HAPPY_PATH.md).
