# Commands and local setup

Read this only when your task needs it. [MASTER_PLAN.md](../../MASTER_PLAN.md) owns current tasks, ownership, progress and next actions; this file owns detailed reference material.

**Run from the repository root. Commands below describe capabilities, not permission or a task queue.** Saved pilot runs and the prepared36-call expansion are complete: do not relaunch them. Model/worker examples require an explicit current task, recorded bounds and fresh runtime checks. For routine Ollama logs use the [bounded query CLI](log-query.md).

## 8. Operator commands and current limitations

Run commands from the repository root using `uv`. A uv cache permission error is not evidence that dependencies are missing. Use the harness permission mechanism, or explicitly set `UV_CACHE_DIR` to an allowed writable scratch path such as repo-local `tmp/uv-cache`; do not assume home or `/private/tmp` is writable, and do not reinstall dependencies merely to fix cache access. A clean clone does **not** contain ignored artifacts, source derivatives or local prototypes. Prepare/copy them deliberately before expecting old run IDs to work.

| Command | Current implemented behavior |
| --- | --- |
| `uv sync --all-groups` | Install project dependencies; use uv, not manually managed virtual environments |
| `make review` / `make review-demo` | Start the single-user LAN browser desk without login / register a clearly synthetic practice packet then start it; no model calls |
| `uv run globe review inbox` | Latest unapplied human submissions, JSON, for every harness startup |
| `make status` | Read the existing cleanup queue; this is not a research-enrichment status dashboard |
| `make run-static` / `make run-workflow` | Existing static-first cleanup/export path, no model requests; can refresh exports with saved accepted edits, so it is not a read-only inspection command |
| `make run-qwen` / `make run-gemma` / `make run-openai` | Existing cleanup worker only; up to 1 hour / 1,000 requests; explicit model operation, not a corpus tagging/search pipeline |
| `make v2-sample` | Offline subject exclusions/sample preparation; outputs already exist here, so **do not rerun** against those paths |
| `globe subject-review-template` / `globe subject-review-import` via `uv run` | Explicit offline human-label preparation/validation; exact sample/vocabulary binding, no provider requests |
| `make gate` | Formats and runs all required implementation checks/tests; can change formatting |

No installed one-command full enrichment/search pipeline exists yet. Do not present the cleanup Make targets as if they implement that deliverable.

### On-demand source scan crops

```bash
# Offline source/geometry preparation, no image request.
uv run globe scan crop --item congressionalglo7392unit --leaf 328 --paragraph par_000328_000032 --output artifacts/my-scan
# Explicit bounded image request; same compatible path resumes verified cache.
uv run globe scan crop --item congressionalglo7392unit --leaf 328 --paragraph par_000328_000032 --output artifacts/my-scan --fetch
# Exact ORIGINAL OCR Unicode span (expected text is required).
uv run globe scan crop --item congressionalglo7392unit --leaf 328 --paragraph par_000328_000032 --start 34 --end 37 --expected GCO --padding 16 --output artifacts/my-word-scan --fetch
# Offline cache inspection; does not need the large raw sources.
uv run globe scan inspect artifacts/scans/scan-poc-20261024-01/petition
```

Do not refetch the four tracked examples merely to show them. New targets need item hOCR/page-map files under `--root` or its `downloads/` child (repository default). Padding defaults64pixels (0–256); output width defaults1600 (100–2000), without upscaling a crop. Use raw text/span/hash references; reverse mapping of current cleaned-text patches is not implemented. Cache includes `target.json`, `info.json`, receipts, `crop-NN.jpg`, `bundle.json`, and `events.jsonl`. Preserve failures and incompatible results. Investigate frame/leaf mismatches rather than guessing. These commands make no model request or corpus correction.

### Clean-reading pilot preparation (offline)

Current inputs: `artifacts/reading-prepare-20261024-03/candidates.jsonl`; source hashes/geometry checked in `source-binding-proof.json`. They are source candidates, not launch-ready model requests. Read `review.json` before use. Earlier manifests01/02 preserve selection history; their exact rejection audits are tracked as `.jsonl.gz` (decompress and verify the uncompressed SHA-256 from the manifest if restoring). Source snapshots, current prompt/reply schema and partial image review are tracked. The scorecard remains unchanged at its human-approved design hash; the master records current decisions; the review-effort revision was applied through HR-009 and must not be requested again.

The preparation module never calls a model or fetches an image. It refuses an existing output directory. Reuse03rather than rescanning unchanged sources. For a deliberate changed selection only:

```bash
uv run python -m congressional_globe.reading_preparation --pages artifacts/runs/static-final-20261011/canonical_pages.jsonl --exclusions artifacts/v2-subject-exclusions.json artifacts/v2-subject-review/review_packets.jsonl artifacts/role-alias-preparation-20261023-02/frozen-inputs.jsonl artifacts/scans/*/*/target.json --source-manifest artifacts/runs/static-final-20261011/workflow_manifest.json --output artifacts/NEW-UNIQUE-READING-PREPARATION
```

`reading_contracts.py` validates exact raw/static hashes, patch replay, target-only references, source-image raw-span/hash coverage, explicit uncertainty and raw-to-clean offset mapping. Coverage must come from verified source bundles; caller-supplied IDs are not a substitute for image binding or visual evidence. `reading_run_store.py` records immutable tasks/configuration, commits exact requests before dispatch, saves raw replies/usage before parsing, refuses changed saved replies, and blocks new claims behind an unresolved attempt. It is a journal, not a live provider runner: request/runtime/token/image preflight and bounded transport integration remain required. Tests/proof use synthetic data and zero model requests.

### Whole-unit reading images and input-fit checks

The fixed18primary candidates are covered in `artifacts/reading-images-20261024-01/index.json`; `coverage-proof.json` binds the exact index hash, every target raw span/hash, saved image bytes, dimensions and native source regions. `index-first-fetch.json` preserves original fetch accounting; current index records cumulative image-set bytes separately from the current replay’s new bytes. Receipts are verified against actual saved payload size/hash before reuse/accounting. First-fetch code/launch intent and cache proof remain saved. Image coverage does not certify the transcription or source expectations.

No new fetch is needed. Validate cached bindings without network or original corpus parsing:

```bash
uv run python -c 'from pathlib import Path; from congressional_globe.reading_contracts import ReadingCandidate; from congressional_globe.reading_images import verify_index; units=[ReadingCandidate.model_validate_json(line) for line in Path("artifacts/reading-prepare-20261024-03/candidates.jsonl").read_text().splitlines()]; print(verify_index(Path("artifacts/reading-images-20261024-01/index.json"),units)["geometry_coverage_complete"])'
```

`reading_requests.py` is offline only. Freeze requests with:

```bash
uv run python -m congressional_globe.reading_requests --prepared artifacts/reading-prepare-20261024-03 --images artifacts/reading-images-20261024-01/index.json --output artifacts/reading-fit-20261025-01/requests.json
```

It refuses differing manifest replacement. `materialize_record(record)` reconstructs the exact body from stored text and hash-checked cached images, rejecting changed bytes/configuration; it does not send it. Request hashes include base64 image bytes, while readable manifests retain image paths/hashes rather than duplicate large payloads. Do not reuse a text count from one model/unit for another request. All token counts remain null until a matching implementation supplies evidence.

`reading_preflight.py` reads recorded current runtime evidence and exact frozen source/image hashes; it does not send a model request. All3MLX tags/digests and vision support were observed at21:48Z. Exact token counts remain unknown: `Tokenizer.from_file` can at most tokenize an already rendered text segment, while Ollama uses model-specific renderer/parser paths and image expansion needs matching processor implementations. Qwen/Gemma have processor configs; Muse has vision parameters but no processor config layer. Raw model context limits and prior8192/256probe settings do not prove fit for the16384/4096reading envelope. Do not invoke the discovered internal `/v1/tokenize` route until its loading and image-count behavior are established. Recheck runtime/queues immediately before any later inference; a loaded model alone is not busy/idle evidence.

### Query and rebuild the Wikipedia mini-dataset

The human requested these three specific Wikipedia pages. Three Luna delegates extracted/audited the House, Senate and district lists; root added validated records, hash-checked snapshot replay and local queries. **No LLM/API/Ollama requests or corpus changes occurred.** The selected authority bundle is tracked in Git despite the usual artifacts ignore rule, so a fresh harness has the data and replay sources.

`artifacts/authorities/wikipedia-39th-20261022/dataset/` contains `records.jsonl` (949 records), `record.schema.json`, `manifest.json` (source URLs/revisions/hashes and extractor hashes), `coverage-review.json`, and `actions.json` (recorded argv recipes). The sibling `sources/` contains all three exact HTML snapshots and their metadata. Wikipedia contributors are attributed with revision links and CC BY-SA 4.0 licensing. Source-layout review is not historical validation.

- **People:** 202 representatives, 9 delegates, 58 senators. All named source rows extracted; party labels, district/state codes, person links, displayed cells and source row locators retained. House previous-service text and departure notes remain separate. Senate rowspan values retain their originating row indices. These pages cover **both sessions of the 39th Congress**, so inclusion alone does not prove first-session attendance or speaker attribution. Seniority is not a complete service interval; individual service endpoints remain null. Party codes are preserved as listed, without inventing temporal party histories or Bioguide identifiers.
- **District directory:** 680 linked entries across 50 states plus non-voting delegations, 679 unique URLs. Both Dakota contexts are retained. Current/historical year wording is preserved, but 39th applicability stays null; exact historical boundaries are not supplied. The two unlinked Cherokee/Choctaw non-voting entries and current overview-table population/area fields are excluded and reported. No linked district pages were crawled.
- **Query semantics:** case-insensitive literal substrings; repeated `--where FIELD=TEXT` filters use AND; null does not match. State uses displayed two-letter state/territory codes; one delegate with a different source code remains null. Original values remain in `source_details`. Local IDs identify source-derived candidates, not verified people authorities.

From the repository root:

```bash
# Offline: find Stevens, with evidence and linked Wikipedia page.
uv run python -m congressional_globe.wikipedia query artifacts/authorities/wikipedia-39th-20261022/dataset/records.jsonl --where name=Stevens
# Offline: the source-listed Ohio senators (Wade and Sherman).
uv run python -m congressional_globe.wikipedia query artifacts/authorities/wikipedia-39th-20261022/dataset/records.jsonl --where kind=senator --where state=OH
# Offline replay: verifies saved source hashes; always use a fresh output directory.
uv run python -m congressional_globe.wikipedia extract --sources artifacts/authorities/wikipedia-39th-20261022/sources --output tmp/wiki-replay
# Explicit network action only when refreshing: fetches the same three live pages.
uv run python -m congressional_globe.wikipedia fetch --sources tmp/wiki-new-sources
```

Queries/extraction use no model. Fetching creates a new snapshot and may yield changed Wikipedia content; replaying saved sources preserves exact inputs. Neither command overwrites an existing output directory. Gates cover source tampering, query failures/nulls, member/delegate parsing, Senate rowspans and mixed historical district listings. **Next authority work:** independently crosscheck official identities and service intervals before promoting candidates, then use them as bounded hints for evidence-backed M1 attribution. This does not decide P0 or satisfy human semantic grading.

### Inspect first, resume existing cleanup only when instructed

```bash
uv run globe cleanup status --run-directory artifacts/runs/static-final-20261011 \
  --run-id static-final-20261011
```

When the human explicitly chooses an hour of cleanup, the existing command is:

```bash
uv run globe cleanup run --run-directory artifacts/runs/static-final-20261011 \
  --run-id static-final-20261011 --backend ollama --model qwen3.8:27b-mlx \
  --limit 1000 --max-seconds 3600 --progress-interval 30
```

Do not execute it merely because this plan exists. Run one worker at a time; inspect live process/session state as well as SQLite. Budget checks occur between jobs, so an in-flight request may finish after an hour. Repeating a compatible command resumes pending work. Saved cleanup results update SQLite, not published exports; after the worker is terminal, `make run-static` explicitly refreshes exports. Omitted request limits can drain a pending snapshot: keep limits in agent POCs.

Static Make targets require the prepared ignored `artifacts/static-audit-20261011/supplemented-lexicon.txt`. On a fresh macOS checkout with the dictionaries available, reconstruction is:

```bash
mkdir -p artifacts/static-audit-20261011
{
  printf '\n'
  cat /usr/share/dict/words /usr/share/dict/web2a /usr/share/dict/propernames resources/static-lexicon-supplement.txt
} | LC_ALL=C sort -u > artifacts/static-audit-20261011/supplemented-lexicon.txt
```

Do not rebuild resources during an active run. Dictionary changes alter fingerprints; use a new compatible run plan rather than silently overwriting results. Other systems must copy the recorded resource or document its substitute and new fingerprints. Preserve existing verified artifacts before intentionally refreshing them.

## Restore pinned Internet Archive sources

From the repository root use `uv run globe sources download`, then `uv run globe sources verify`. Both accept `--directory` (default `downloads`). Existing source files are never silently replaced. Missing files require network access; changed remote bytes fail the pinned size/SHA-256 checks. Inspect and move aside a failed `.partial` transfer before explicitly retrying. The manifest and downloader are tracked; the fifteen large files are ignored. Normal source commands resolve repository-root inputs into `downloads/`; explicit source roots remain supported.
