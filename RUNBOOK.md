# Congressional Globe RAG Corpus Runbook

Last updated: 2026-10-11

## Purpose

This folder is being prepared as a provenance-first corpus for retrieval-augmented generation (RAG). The desired end state is searchable, cleaned text with reliable citations back to the Internet Archive scan leaf, printed page, hOCR element, and (where useful) bounding box.

Do **not** replace or discard the raw OCR sources. All cleanup must be reversible and traceable to those sources.

## Scope of the current corpus

The target set is **The Congressional Globe, 39th Congress, 1st Session, Parts 1–5**. Each part is an independent Internet Archive item and must remain independently identifiable.

| Part | Internet Archive identifier | Status in this folder |
| --- | --- | --- |
| 1 | `congressionalg7391unit` | hOCR, DjVu XML, and page-number map complete |
| 2 | `congressionalglo7392unit` | hOCR, DjVu XML, and page-number map complete |
| 3 | `congressionalglo7393unit` | hOCR, DjVu XML, and page-number map complete |
| 4 | `congressionalglo00unit` | hOCR, DjVu XML, and page-number map complete |
| 5 | `congressionalglo7395unit` | Present before this runbook was created |

Part 5 is not the whole serial or even the whole congressional session. Its main proceedings span printed pages 3841–4310; that proves it is the final part of the five-part session set. It also contains a separately paginated Appendix.

## Files and roles

For each item, retain these three source derivatives:

- `<identifier>_hocr.html` — primary OCR/layout source: page, block, paragraph, line, word IDs, coordinates, and word confidence.
- `<identifier>_djvu.xml` — alternate OCR/layout source, useful for validation and source provenance.
- `<identifier>_page_numbers.json` — Internet Archive printed-page mapping.

The raw files for Part 5 were the initial inventory:

- `congressionalglo7395unit_hocr.html` (310 MB)
- `congressionalglo7395unit_djvu.xml` (161 MB)
- `congressionalglo7395unit_page_numbers.json` (179 KB)

Observed Part 5 structure: 2,148,356 hOCR words, 295,886 lines, and 66,146 paragraphs. hOCR exposes 1,090 page nodes; the page-number map has 1,082 records. Treat these as different source measurements, not an error to erase.

## Internet Archive metadata handling

Preserve the Internet Archive record verbatim in a future `metadata_raw` object. Do not flatten it into derived bibliographic fields.

Important example: the item catalog's `date: 1833` is a serial-level catalog value. The Part 5 title-page OCR states 1866. Store both distinctly:

```json
{
  "serial_start_year": { "value": 1833, "source": "catalog.date" },
  "edition_publication_year": {
    "value": 1866,
    "source": "title_page_ocr",
    "evidence": "page_000007"
  }
}
```

Relevant raw catalog fields include identifier, ARK, OCLC/LCCN, volume statement, contributors and associated names, collections, scan date, scanner/scanning center, PPI, OCR engine/converter/module versions, page progression, and all catalog notes.

## Download history and recovery

Completed downloads use Internet Archive's normal derivative names. A generic Archive redirect stalled intermittently, so the Part 3 recovery used its assigned mirror:

```text
https://ia601601.us.archive.org/17/items/congressionalglo7393unit/
```

The Part 3 transfer was started with resumable curl commands. It writes a `.partial` file and renames it only on success:

```bash
curl --http1.1 --fail --retry 8 --retry-all-errors --connect-timeout 30 \
  --continue-at - \
  --output congressionalglo7393unit_hocr.html.partial \
  https://ia601601.us.archive.org/17/items/congressionalglo7393unit/congressionalglo7393unit_hocr.html \
  && mv congressionalglo7393unit_hocr.html.partial congressionalglo7393unit_hocr.html
```

All three Part 3 derivatives completed successfully. If a future transfer ends early, re-run the same command; `--continue-at -` will resume where the server permits it.

`congressionalg7391unit_hocr.html.interrupted` is a 13 MB artifact from an aborted duplicate transfer. It is not a source file and is not used by the pipeline. Retain it until Part 1 has been independently verified, then remove it deliberately.

## Implemented corpus factory

The local `globe` command now implements the initial production path. It writes streaming JSONL for canonical pages and paragraphs, page-bounded RAG chunks, a run manifest, and—when requested—a single `corpus.json` containing the complete canonical page layer.

```bash
uv run globe inventory --hashes
uv run globe build-rag --run-id 2026-10-11-baseline --single-json
uv run globe prepare-ai \
  --paragraphs artifacts/2026-10-11-baseline/pages/congressionalg7391unit_paragraphs.jsonl \
  --output artifacts/ai-runs/part-1-requests.jsonl --model YOUR_MODEL
# Explicitly opt in only after reviewing the request file:
uv run globe submit-batch --requests artifacts/ai-runs/part-1-requests.jsonl --confirm-submit
# After downloading the completed Batch output JSONL:
uv run globe reconcile-ai --batch-output batch-output.jsonl \
  --paragraphs artifacts/2026-10-11-baseline/pages/congressionalg7391unit_paragraphs.jsonl \
  --output artifacts/ai-runs/part-1-normalized.jsonl \
  --review-output artifacts/ai-runs/part-1-review.jsonl
```

`reconcile-ai` accepts only Responses API `output_text` records that validate against the strict cleanup schema and whose patches match the exact raw substring. It writes failures to the review file; it does not change raw files or canonical extraction.

## Resumable cleanup runner and Ollama pilot

The interactive cleanup runner is deliberately separate from raw extraction. It stores one stable job per paragraph in `artifacts/runs/<run-id>/jobs.sqlite`, records provider events in `events.jsonl`, saves successful raw model outputs under `responses/`, and exports validated normalized records as JSONL. Reusing a run ID resumes its pending work; a newly started runner returns abandoned `claimed` jobs to `pending`.

An Ollama connection loss leaves the active job `pending` and stops the run rather than treating it as a text-quality failure. Schema/patch failures remain in `review`; explicitly requeue those only after inspection with `globe cleanup retry`.

Useful commands:

```bash
# Create a bounded queue from extracted paragraph JSONL.
uv run globe cleanup init --run-directory artifacts/runs/NAME --run-id NAME \
  --paragraphs artifacts/EXTRACTION/ITEM_paragraphs.jsonl --scan-leaf 120

# One sequential request at a time against the local OpenAI-compatible Ollama server.
uv run globe cleanup run --run-directory artifacts/runs/NAME --run-id NAME \
  --backend ollama --model qwen3.8:27b-mlx --limit 10

# Inspect progress, then materialize only completed validated records.
uv run globe cleanup status --run-directory artifacts/runs/NAME --run-id NAME
uv run globe cleanup retry --run-directory artifacts/runs/NAME --run-id NAME
uv run globe cleanup export --run-directory artifacts/runs/NAME --run-id NAME \
  --output artifacts/runs/NAME/normalized.jsonl
```

`--backend openai` uses the same queue and can continue a local run with foreground Responses API requests when `OPENAI_API_KEY` is set. The older `prepare-ai` / `submit-batch` / `reconcile-ai` commands remain a separate Batch workflow; Batch is **not yet** integrated with the SQLite queue. There is also no dashboard beyond CLI status and the JSONL event log.

The Ollama adapter uses OpenAI-compatible Chat Completions with `reasoning_effort="none"` and JSON mode (`response_format={"type":"json_object"}`). Empty model content is rejected and the finish reason is recorded in the review event; it is never accepted as a cleanup result.

`cleanup run` prints JSONL progress to the terminal: `job_claimed` immediately, `job_heartbeat` at the selected `--progress-interval` while a request is active, then a terminal outcome event. The same events are appended to the run's durable `events.jsonl`; the heartbeat thread sends no model requests, so local inference remains strictly sequential.

`cleanup status` is read-only and reports completed, pending, claimed, review, remaining, percentage, average completed-job time, and an ETA derived from completed jobs. It can run in a second terminal while a worker is active.

## Cloud cost planning (estimate only)

The current five-part corpus has 296,995 paragraphs and roughly 11.14 million OCR words. For a GPT-5-nano-class strict-JSON cleanup pass, budget 550–720 input tokens per paragraph (OCR plus repeated prompt/schema) and 30–100 output tokens (a no-op or small patch list). At GPT-5 nano's published $0.05/M input and $0.40/M output rates, this is approximately $12–23 for the full corpus, with a central estimate around $15. Batch API normally halves that to about $6–12, with a 24-hour completion window. Part 5 alone is roughly 22% of the full estimate. These are planning numbers, not a quote: record actual API usage from a representative cloud sample before a full submission. GPT-5 nano is marked deprecated in current model docs; select an available successor before submitting.

### 2026-10-11 local pilot result

Part 5 was extracted to `artifacts/pilot-extraction/`, then two trivial records from scan leaf 120 (printed page 3848) completed locally with `qwen3.8:27b-mlx`: the page number took 19.3 s and the running header took 7.5 s. Both produced valid no-change cleanup output. Attempts on substantive paragraphs did not return before the agent command window's 30-second limit, leaving recoverable claimed jobs in `artifacts/runs/ollama-pilot*/jobs.sqlite`.

This establishes queue/provenance behavior, not substantive correction quality. Do not scale that model paragraph-by-paragraph without a normal-terminal benchmark on representative content. The two trivial calls averaged about 13 seconds each, which alone extrapolates to roughly 46 days for 296,995 paragraphs; substantive paragraphs will be slower and may make the real duration far larger. Inspect and resume these pilot runs rather than recreating them.

After enabling OpenAI-compatible JSON mode and `reasoning_effort="none"`, the same substantive paragraph completed in 1.1 s with a valid no-op result. This fixed the empty-response failure but did **not** correct obvious line-break artifacts (`him- self`, `under- stand`, and `explana- tion`). Treat `qwen3.8:27b-mlx` with the current prompt as transport-validated but **not quality-approved** for full cleanup. The shared prompt was then revised to explicitly authorize high-confidence alphabetic line-wrap repairs with those examples. Evaluate the revised prompt against records with known expected edits before scaling; deterministic, geometry-aware dehyphenation remains a future optimization.

The first prompt revision elicited edits but the model supplied an `expected` substring that did matched the intended source but not its stated offsets; validation rejected it. The runner now uses an exact `expected` substring as a deterministic anchor only when it occurs exactly once, then records the resolved edit positions separately from the model proposal. Missing or ambiguous anchors still fail closed to review. Raw model JSON is saved before patch application, including when validation sends a job to review.

The final `ollama-pilot-3` retry completed successfully in 10.7 s. Its three proposed anchors were all unique and resolved to source-verified spans, yielding `himself`, `understand`, and `explanation` in `text_normalized`. This validates the local path for this repair class, but it is not a corpus-wide quality approval: run a stratified evaluation sample before scale.

### 2026-10-11 OpenAI provider benchmark

The cloud Responses path was validated against a 12-paragraph stratified Part 5 sample (10 paragraphs with line-wrap artifacts plus 2 clean controls), one request per paragraph. The first live call failed with HTTP 400 because OpenAI strict structured outputs require every property in `required`, while Pydantic omits fields that carry defaults (`review_reason`). The provider, batch request builder, and prompt now share a `strict_json_schema` helper that promotes all properties for transport only.

Before the prompt revision, `gpt-5.4-nano` sent 8 of 12 jobs to review: it invented no-op placeholder edits, anchored edits on a truncated fragment (`expected='meas-'` with `replacement='measure'`), and repeated the same span twice. The shared prompt now states that `expected` is the complete replaced span, forbids no-op and duplicate edits, and asks for the full set of joins. `resolve_edits` also deterministically de-duplicates and sorts resolved spans, which removes the duplicate/overlap review class. `OpenAIResponsesProvider` pins `temperature=0` so review behavior is reproducible run to run.

After the revision, `gpt-5.4-mini` completed 6/6 and then 5/6 of the same sample, fixing 37/38 and 22/38 wrap artifacts with valid, source-anchored joins. `gpt-5.4-nano` normalized every paragraph but consistently returned a single edit and left all 38 wraps unchanged, so it is not viable for this repair class. Remaining review cases are non-unique anchors, which still fail closed as intended. Treat `gpt-5.4-mini` as the current cloud default and re-run this sample before any large submission; geometry-aware deterministic dehyphenation remains the preferred fix for the roughly 30% of Part 5 paragraphs that contain line-wrap artifacts.

### 2026-10-11 static-cleanup investigation (findings only, not yet implemented)

Goal: move the mechanically decidable cleanup out of the LLM path and leave only genuinely contextual work for a model. Measurements below are over all 66,146 Part 5 paragraphs or a sample of 100–150 hOCR pages.

- hOCR exposes per-word `bbox`, `x_wconf` confidence, and `x_fsize`, but `extraction.py` `_text` flattens each paragraph to plain text and discards that geometry. Any deterministic word-level cleanup needs the extractor to retain line and word spans.
- Dehyphenation is the dominant task: about 10% of hOCR lines end in a hyphen, and 46,904 `word- word` joins appear across 19,899 paragraphs (30.1%).
- A geometry-free rule — join `X- y` when `Xy` is a lexicon word (with light morphology), keep the hyphen when `X` and `y` are both words, otherwise flag — resolves 44,163 of 46,904 joins (94.2%) with no model call. The 2,741 residuals (5.8%) are mostly proper nouns (`Ten- nessee`, `Wis- consin`, `John- son`).
- A base lexicon alone is insufficient: `/usr/share/dict/words` (236k entries, from `web2`) omits inflections (`experiments`, `officers`), so suffix stripping is required. Merging `web2a` and `propernames` helps but does not cover every proper noun.
- The DjVu XML OCR spells the joined form correctly for roughly 25% of the residual distinct forms, but presence alone is noisy (`Temiessee`, `governmentof`), so it is a hint, not a verdict.
- Missing spaces are not a reconstruction bug: a 100-page scan found zero source-level word merges, so `suppresseshostilities` is a genuine single-word OCR error. Lexicon splitting of long out-of-vocabulary tokens flags 5,471 candidates but is almost entirely false positives (`department`, `Springfield`), so this class still needs the model.
- Running heads, page numbers, and dates are statically detectable by repetition and page position (`THE CONGRESSIONAL GLOBE.`, `INDEX TO`, all-digit lines).
- 3,865 paragraphs (5.8%) contain junk characters (`^c`, `\`, `€ • » ■`); the rest is mostly legitimate (`—`, `£`, `§`, `°`). 42,382 paragraphs (64%) contain neither a line-wrap hyphen nor junk characters and need no deterministic edit at all.

Proposed static-first path (not built yet): retain line/word spans in extraction; run a deterministic normalizer (lexicon/morphology dehyphenation, header/footer/page-number marking, ligature and character fixes, whitespace/punctuation) before any AI; queue only residuals for the LLM with `x_wconf` and any DjVu alternate spelling attached as hints; reserve image review for low-confidence and still-unresolved cases. The local Ollama server currently serves `qwen3.8:27b-mlx`, `gemma4:31b-mlx`, and `muse-glimmer:30b-mlx` for residual experiments.

## Canonical corpus design

Create a canonical, hierarchical JSON representation plus a RAG-specific JSONL derivative.

### Canonical document/page model

Each page must retain:

- `item_identifier`, `part_number`, `scan_leaf`, hOCR page ID, DjVu page reference.
- Printed page number with `value`, `kind`, `source`, and confidence; preserve `detected` separately from any inferred number.
- Page dimensions and DPI.
- `text_ocr` exactly as extracted and `text_normalized` as conservative cleanup.
- Paragraph/line IDs, reading order, and bounding boxes.
- Date, chamber, and other contextual metadata with an explicit source such as `direct_header`, `propagated`, or `manual_review`.

The principal RAG citation should be able to render as:

```text
The Congressional Globe, 39th Cong., 1st Sess., pt. N,
printed p. X, scan leaf Y, hOCR page_Z, paragraph par_…
```

### RAG chunks

Derive page-bounded chunks after canonical extraction/cleanup. Each chunk should contain normalized text and metadata including part, date, chamber, section, printed page(s), scan leaf/leaves, paragraph IDs, source hOCR page, and a display-ready citation. Do not embed recurring page headers/footers as substantive text.

## Cleanup rules

1. Parse and reconstruct multi-column reading order deterministically from geometry before AI processing.
2. Keep raw OCR immutable.
3. Use AI only for conservative, structured transformations: OCR correction suggestions, headers/dates/chambers, speaker segmentation, document type, bill/resolution references, and entity enrichment.
4. Record each AI edit with original text, replacement, reason, confidence, model/pipeline version, and source IDs.
5. Use page-image review for uncertain names, dates, bill numbers, votes, or low-confidence passages. Text-only cleanup must not silently invent corrections.
6. Keep enrichment distinct from primary text and mark its evidentiary source/confidence.

## API processing approach

Use strict JSON-schema output for AI cleanup/enrichment and process deterministic page/paragraph jobs by stable ID. For volume-scale work, use batch processing and carry the stable corpus ID in each request's `custom_id`; batch result ordering is not reliable. Keep the batch input/output and run manifest for every transformation.

Before full processing, create a human-reviewed evaluation sample covering indexes, dense two-column proceedings, Appendix material, date/chamber changes, and low-confidence OCR.

## Immediate next steps

1. Implement the static-first path: retain line/word spans in extraction, add lexicon/morphology dehyphenation and header/footer/page-number marking, and measure before/after on a sample.
2. Build a compact quality-review sample before scaling any model (index, dense two-column proceedings, Appendix, date/chamber changes, and low-confidence OCR).
3. Queue only residuals for the LLM (`gpt-5.4-mini` or local), carrying `x_wconf` and any DjVu alternate spelling as hints.
4. If Batch is needed, integrate it with the SQLite job state rather than creating a second source of truth.
5. Add a lightweight progress report only if CLI status and `events.jsonl` prove insufficient.
