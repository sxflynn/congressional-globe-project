# Congressional Globe RAG Corpus Runbook

Last updated: 2026-10-11

Active exploration: [V2_PIVOT.md](V2_PIVOT.md) compares organizing and enriching unchanged OCR against the existing cleaned-text path. Preserve both; do not resume cleanup model jobs as part of that experiment. `PROGRESS.md` records its sample preparation, commands and limitations.

For continuation in another AI harness, follow [V2_HANDOFF.md](V2_HANDOFF.md). It records the preserved corpus, authorization, installed embedding models, exact POC commands, stopped trial, outstanding checks and resume order.

## Purpose

Build a portable historical research corpus with authoritative canonical transcription, separately versioned authorities and evidence-backed enrichments, and derived full-text, structured, semantic and RAG retrieval exports. Preserve precise links to Internet Archive items/scan leaves, printed pages, canonical spans, hOCR elements and geometry. `PROJECT_GOAL.md` defines the updated goal, existing-schema support, future workflow stages and guardrails. Codex builds the reproducible workflow; future explicitly authorized stages perform enrichment. The current priority remains reliable corpus processing, without re-OCR or expanding into original-image visual validation.

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

## Cloud cost planning (historical nano estimate)

The historical nano estimate below does not apply to the current `gpt-5.4-mini` path. Use the measured time/cost projections below with current provider prices.

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

### 2026-10-11 static-first cleanup

Goal: move the mechanically decidable cleanup out of the LLM path and leave only genuinely contextual work for a model. Measurements below are over all 66,146 Part 5 paragraphs or a sample of 100–150 hOCR pages.

- hOCR exposes per-word `bbox`, `x_wconf` confidence, and `x_fsize`, but `extraction.py` `_text` flattens each paragraph to plain text and discards that geometry. Any deterministic word-level cleanup needs the extractor to retain line and word spans.
- Dehyphenation is the dominant task: about 10% of hOCR lines end in a hyphen, and 46,904 `word- word` joins appear across 19,899 paragraphs (30.1%).
- A geometry-free rule — join `X- y` when `Xy` is a lexicon word (with light morphology), keep the hyphen when `X` and `y` are both words, otherwise flag — resolves 44,163 of 46,904 joins (94.2%) with no model call. The 2,741 residuals (5.8%) are mostly proper nouns (`Ten- nessee`, `Wis- consin`, `John- son`).
- A base lexicon alone is insufficient: `/usr/share/dict/words` (236k entries, from `web2`) omits inflections (`experiments`, `officers`), so suffix stripping is required. Merging `web2a` and `propernames` helps but does not cover every proper noun.
- The DjVu XML OCR spells the joined form correctly for roughly 25% of the residual distinct forms, but presence alone is noisy (`Temiessee`, `governmentof`), so it is a hint, not a verdict.
- Missing spaces are not a reconstruction bug: a 100-page scan found zero source-level word merges, so `suppresseshostilities` is a genuine single-word OCR error. Lexicon splitting of long out-of-vocabulary tokens flags 5,471 candidates but is almost entirely false positives (`department`, `Springfield`), so this class still needs the model.
- Running heads, page numbers, and dates are statically detectable by repetition and page position (`THE CONGRESSIONAL GLOBE.`, `INDEX TO`, all-digit lines).
- 3,865 paragraphs (5.8%) contain junk characters (`^c`, `\`, `€ • » ■`); the rest is mostly legitimate (`—`, `£`, `§`, `°`). 42,382 paragraphs (64%) contain neither a line-wrap hyphen nor junk characters and need no deterministic edit at all.

Implemented first slice: extraction now retains each hOCR line and word, including word ID, bounding box, `x_wconf`, and `x_fsize`. `globe static-cleanup` reads extracted paragraph JSONL and an explicitly supplied newline-delimited lexicon, joins alphabetic line-wraps only when the joined form is present in the lexicon (or is a supported simple inflection), and writes derived JSONL with source-anchored `static_edits`. OCR source fields remain unchanged. Example:

```bash
uv run globe static-cleanup \
  --paragraphs artifacts/extraction/IDENTIFIER_paragraphs.jsonl \
  --lexicon path/to/wordlist.txt \
  --output artifacts/static-cleanup/IDENTIFIER_paragraphs.jsonl
```

The lexicon is an input rather than a bundled platform dictionary, so runs can record and reuse the exact word list. This pass intentionally leaves uncertain joins untouched for later model or image review. Later work below implements conservative running-header/page-number marking, source-backed same-page date/chamber context, residual routing, and explicit review exports. General ligature/character rewriting and DjVu alternate-spelling correction remain deferred. The local Ollama server currently serves `qwen3.8:27b-mlx`, `gemma4:31b-mlx`, and `muse-glimmer:30b-mlx` for residual experiments.

### 2026-10-11 static cleanup and export POC

The static pass now checks actual hOCR line boundaries and resolves their source positions sequentially, including repeated line text. Inline hyphenated phrases are preserved. Input/output aliases (including hard links and the lexicon) are rejected. Derived rows retain pipeline, lexicon, and input SHA-256 fingerprints, source-anchored edits, and unresolved wrap hints. This establishes line-boundary evidence; it does not use bounding-box thresholds to infer ambiguous layouts.

A bounded POC used Part 5 scan leaves 17 and 120. Across their 201 paragraphs, the static pass applied 71 validated edits and left five unresolved wrap hints in five paragraphs. Two selected paragraphs contained five known wrap repairs; the static pass made all five. This is a targeted transport and integration sample, not a stratified corpus accuracy estimate.

The provider comparison used those two original paragraphs plus their two cleaned controls. Both `gpt-5.4-mini` and `qwen3.8:27b-mlx` matched all four expected outputs and preserved both clean controls. OpenAI consumed 2,586 input / 343 output tokens in 6.3 seconds; local Qwen consumed 2,814 input / 483 output tokens in 37.4 seconds. These are observed request totals, not cost estimates. Static repair of the five selected wraps used no model calls. The sample did not measure contextual residual errors, so it cannot select a residual provider yet.

POC evidence lives under `artifacts/benchmarks/static-first-poc-20261011/`, `static-first-openai-mini-20261011/`, and `static-first-ollama-qwen-20261011/`. The two full pages were merged with their derived paragraphs and exported as canonical JSONL plus seven page-bounded RAG chunks. The merge uses a temporary SQLite index, verifies raw-text equality and complete paragraph coverage, validates static edit ledgers, retains provenance, and replaces the final canonical file only after validation succeeds. Chunk citations now include hOCR page and paragraph IDs; normalized empty strings are preserved.

```bash
# Opt-in, bounded provider evaluation against expected-text JSONL cases.
uv run globe benchmark --cases artifacts/benchmarks/static-first-poc-20261011/cases.jsonl \
  --backend ollama --model qwen3.8:27b-mlx --run-id NEW-BENCHMARK-ID --limit 4

# Export supplied canonical pages and a complete derived paragraph file.
uv run globe export-rag --pages artifacts/benchmarks/static-first-poc-20261011/pages.jsonl \
  --paragraphs artifacts/benchmarks/static-first-poc-20261011/full-page-static.jsonl \
  --output artifacts/export-poc
```

The later `static-first` workflow composes the static and model ledgers in one resumable queue, exports sourced structure/context, and stages final artifacts behind a validation gate. The initial two-page sample alone was insufficient for model selection; see the full static audit and contextual POC below.

### Time and cost projections

Time and API cost are primary decision criteria alongside correction quality. `globe estimate` makes no model requests: it reads saved benchmark evidence and projects an explicitly supplied number of model jobs. Use the residual workload after static cleanup, rather than assuming every paragraph needs a request. The current estimate models one sequential request per job, with a separately supplied retry allowance.

At the standard `gpt-5.4-mini` prices verified on 2026-10-11 ($0.75 per million input tokens and $4.50 per million output tokens), the four-case OpenAI POC cost approximately $0.00348. Source: [official model pricing](https://developers.openai.com/api/docs/models/gpt-5.4-mini). The measured averages were 646.5 input and 85.75 output tokens per request. Pricing is supplied explicitly to the planner so it cannot silently rely on stale rates.

| Model requests | Local Qwen elapsed | OpenAI mini elapsed | OpenAI API dollars |
| --- | --- | --- | --- |
| 1,000 | 2.6 hours | 26 minutes | $0.87 |
| 10,000 | 26 hours | 4.4 hours | $8.71 |
| 296,995 (every paragraph) | 32.2 days | 5.4 days | $258.61 |

These are provisional scenarios extrapolated from four small cases, not corpus-wide forecasts or confidence intervals. Hard residual paragraphs may take more time and tokens. Static extraction/export overhead, image review, embeddings, electricity, hardware costs, retries, downtime, and cloud rate limits are excluded unless separately measured or supplied. Ollama API charges are zero; machine runtime remains a real constraint. Cloud concurrency and Batch scheduling are not assumed by this sequential calculation. The residual fraction observed on two pages is not representative enough to project across all five parts.

```bash
uv run globe estimate \
  --summary artifacts/benchmarks/static-first-ollama-qwen-20261011/summary.json \
  --jobs 10000

uv run globe estimate \
  --summary artifacts/benchmarks/static-first-openai-mini-20261011/summary.json \
  --jobs 10000 --input-rate 0.75 --output-rate 4.50 --retry-fraction 0.10
```

The final single-command workflow must include a planning report with measured static time, residual counts, projected model time/cost, and sample limitations before its full-run invocation. Representative residual POCs are still required to finalize those estimates and provider selection.

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

Before scaling model processing, define a reviewed evaluation sample covering indexes, dense proceedings, Appendix material, date/chamber changes, and low-confidence OCR. Original-image visual validation is outside the current scope; text-context labels must not be described as image-verified gold.

## Current progress and next steps

See `PROGRESS.md` for the authoritative checklist and exact resume commands. The static-first path, residual queue, small provider comparisons, and bounded canonical/RAG export verification are implemented. Remaining work is quality calibration and image-supported review before any full-corpus model run. Batch integration and a dashboard remain optional future work.

### 2026-10-11 full five-part static audit

The full static pass now runs with an explicit command and no provider requests:

```bash
uv run globe static-first \
  --root . \
  --run-id static-full-audit-20261011 \
  --lexicon artifacts/benchmarks/static-first-poc-20261011/lexicon.txt \
  --plan-only
```

`--plan-only` writes extracted pages, paragraphs, static patches, residual paragraphs, and a manifest. It does not start a cleanup worker. The default backend is `none`; omitting `--plan-only` also prepares a resumable residual queue and exports static canonical pages and RAG records. A provider requires an explicit backend and model. Reuse the same run ID and inputs to resume its queue; use a different run ID for a changed lexicon. Raw source material remains unchanged.

Measured full scope: 15 source derivative files across all five parts (five hOCR, five DjVu XML, five page maps), **5,412 scan pages and 296,995 paragraphs**. The static audit reads hOCR and page maps; DjVu is inventoried, not used as correction authority. There are 5,369 pages with at least one extracted paragraph; the remaining 43 pages are still represented in page JSONL. Locally saved IA item metadata is absent and recorded as unavailable rather than reconstructed.

The baseline run took **260.849 seconds (4 minutes 21 seconds)** on this machine: extraction 148.469 s, static cleanup 46.282 s, residual routing 34.340 s, and other hashing/review-count work. It made 202,064 validated line-wrap patches across 93,969 paragraphs and left 29,525 unresolved wrap hints. The narrow router flagged 28,054 paragraphs: 23,694 with unresolved wraps and 4,360 with suspicious glyphs only. These are candidate requests, not confirmed OCR errors or the complete contextual workload.

#### Reproducible quality sample

Evidence lives under `artifacts/static-audit-20261011/`; large derived files and scratch files are ignored by Git. The audit script and supplemental evaluation script are saved with the evidence, along with source fingerprints and anchored review verdicts. Seed **3911866**, Algorithm R reservoir sampling, independently stratified by part and sampling unit:

- 60 individual baseline patches per part: **300 patches** total.
- 30 flagged paragraphs per part: **150 paragraphs** total.
- 20 unflagged paragraphs per part: **100 paragraphs** total.
- A separate sample of 20 newly added supplemental patches per part: **100 additional patches**.

Every paragraph's static edit ledger was replayed and checked against its normalized text, including after the supplemental pass. Raw text and composite source identities were compared between baseline and supplemental output. hOCR and page-map fingerprints were rechecked afterward: all ten source files were unchanged.

Codex text-context review, including delegated GPT-6 Luna reviews, judged 297/300 baseline patches plausible correct joins, with three ambiguous historical compound spellings (`rail-road` twice and `slave-holders` once), and no clearly damaging joins. All 100 sampled supplemental joins looked correct in their supplied context. These are model-assisted text reviews, **not human gold labels or scan-image verification**; they do not establish a population error rate. Source anchors and individual uncertain verdicts remain available for image review.

The 150 baseline flagged paragraph samples included 50 candidates for further static word-list work, 95 needing contextual or image review, and five legitimate or ambiguous compounds. Among the 100 unflagged paragraph samples, 63 had no obvious issue, 25 needed contextual/image review, and 12 remained ambiguous. Examples of misses include fused words and character substitutions. Because sampling was stratified equally by part and verdicts are not image-verified, these raw counts are not a corpus error-rate estimate. **Do not call the unflagged corpus clean.**

The confidence rule also marks **150,424 paragraphs** for possible review, including 25,572 already in the baseline model-candidate set. That broad signal is too large to use directly as an automatic model queue. Calibrate it against reviewed examples and preserve its reasons separately.

#### Measured word-list improvement

The explicit 44-form list in `resources/static-lexicon-supplement.txt` addresses familiar inflections, irregular forms, and names missing from the platform dictionary, such as `gentlemen`, `submitted`, `having`, `territories`, `Wisconsin`, and `Tennessee`. Each form has hundreds or thousands of intact occurrences elsewhere in the raw corpus. This finite, reviewed list was used instead of broadening suffix rules or automatically accepting every frequent OCR spelling. Conventional hyphenated numbers such as `twenty-five` were excluded.

Combine that list with the baseline dictionary, then reuse the extracted paragraphs for a new static pass:

```bash
uv run globe static-cleanup \
  --paragraphs artifacts/runs/static-full-audit-20261011/paragraphs.jsonl \
  --lexicon artifacts/static-audit-20261011/supplemented-lexicon.txt \
  --output artifacts/static-audit-20261011/supplemented-static.jsonl
```

The saved supplemental lexicon is the sorted union of the baseline lexicon and the tracked 44-form list; its fingerprint is recorded in every derived row.

| Measure                             | Baseline | With 44-form supplement |
| ----------------------------------- | -------: | ----------------------: |
| Static patches                      |  202,064 |                 209,609 |
| Paragraphs receiving static patches |   93,969 |                  96,093 |
| Unresolved wrap hints               |   29,525 |                  21,980 |
| Narrow model-candidate paragraphs   |   28,054 |                  22,479 |

This gains **7,545 additional static patches** and removes **5,575 candidate requests (19.9%)**, without introducing a new candidate request. `supplemented-residuals.jsonl` contains the remaining flagged paragraphs with anchors, geometry, text, patches, and unresolved reasons. It is an auditable candidate set, not authorization to submit the full corpus.

#### Provisional time and cost

Using the earlier five-case residual benchmark unchanged, 22,479 sequential candidate calls project to about **10.7 hours / $19.3** for OpenAI mini, **46.0 hours / $0 API charge** for local Qwen, or **43.9 hours / $0 API charge** for local Gemma. The mini calculation uses the explicitly checked $0.75/M input and $4.50/M output rates. Local electricity/hardware costs are not estimated. These timings and costs extrapolate a tiny sample with repeated index material, not the random residual sample or the full paragraph-length distribution; retry, review, and export costs are excluded. The actual contextual workload can be larger because the narrow router misses other errors. Benchmark a stratified, reviewed residual sample before committing to a full provider run.

Next static work should prioritize the reviewed residual candidates, retain compound-hyphen ambiguity, measure precision of confidence and glyph signals, and evaluate source-supported fixes for recurring OCR substitutions. Each expansion needs a new anchored sample and a measured queue reduction; recurrence alone must not authorize a correction.

### Contextual POC and export verification (2026-10-11)

The one-command workflow now verifies fingerprints when resuming, preserves hOCR block order, attaches date/chamber facts only at or after their source heading, and exports paragraph geometry, anchors, context, status, and both correction ledgers inside RAG records. Conflicting or corrupt heading dates remain unknown. Materialization is atomic under the run lock; unsafe legacy patches become review records. Ollama requests use a shared OS lock across workers and benchmarks. Standalone punctuation rewrites and numeric-value changes are withheld for review. These guards validate proposed changes; they cannot establish that a model caught every OCR error.

The contextual benchmark uses five problem paragraphs (one per part) selected from the random static audit and three unchanged controls. Its expected texts are provisional text-context judgments, not scan-image gold. Evidence: `artifacts/benchmarks/context-audit-20261011/`.

| Provider | Eight-case duration | Accepted agreement with expected text | Control changes | API charge |
| --- | --: | --: | --: | --: |
| OpenAI gpt-5.4-mini | 11.51 s | 6/8 | 0/3 | $0.00657 |
| Ollama qwen3.8:27b-mlx | 51.97 s | 8/8 | 0/3 | $0 |
| Ollama gemma4:31b-mlx | 42.31 s | 7/8 | 0/3 | $0 |

Mini proposed a punctuation rewrite in an inverted index and separately requested image review; both were withheld. After tightening the punctuation-preservation prompt, a one-case mini retest corrected `ihc` to `the` while preserving the comma (1.37 s, about $0.00080). Gemma missed that glyph error entirely. Qwen's eight accepted results agreed with the provisional expectations, but this tiny selection is insufficient to authorize automatic corpus-wide cleanup.

The stricter mixed-letter/digit router now finds **22,547 candidates** when rerun over the full supplemental static output, 68 more than the earlier router. Scaling the eight-case sample means gives **9.0 hours / $18.53** for mini, **40.7 hours / $0 API charge** for Qwen, and **33.1 hours / $0 API charge** for Gemma. Mini pricing is $0.75/M input and $4.50/M output ([official model pricing](https://developers.openai.com/api/docs/models/gpt-5.4-mini)). These estimates exclude retries, image review, static/export overhead, and local hardware/electricity costs. The sample is purposive and small; no confidence interval or quality guarantee is implied.

A separate runtime verification used leaves 114–117 in each part: **20 pages, 1,035 paragraphs, 73 RAG chunks, 85 queued candidates**. Initial static/export execution took 10.88 s. Resuming the same queue for three Qwen requests took 50.44 s including export, then three mini requests took 7.99 s including export. Qwen's three jobs required review (one truncated JSON response and two image-review decisions). Mini completed one four-patch result and withheld two others; 79 jobs remain pending, five in review, none claimed. The completed paragraph still contains other visible OCR errors. These harder examples show why the eight-case timing projection can underestimate runtime and why pending/review flags must remain visible.

Independent verification replayed every static and AI ledger, checked source-text equality and paragraph coverage, validated all Pydantic records, checked heading order, anchors and geometry, and verified export hashes. Explicit headings produced sourced dates 1865-12-04 (Part 1 leaf 117) and 1866-07-16 (Part 5 leaf 114); 18 other pages retained unknown date/chamber facts. Evidence and provider reports: `artifacts/runs/e2e-final-20261011/`. No full-corpus model requests were made.

#### One command for static canonical and RAG outputs

```bash
uv run globe static-first --root . --run-id static-final-20261011 \
  --lexicon artifacts/static-audit-20261011/supplemented-lexicon.txt \
  --backend none --ai-limit 0
```

Outputs are `canonical_pages.jsonl`, `chunks.jsonl`, `manual_review.jsonl`, and `validation_report.json` under the run directory. A passing validation report establishes record/ledger consistency; `cleanup_complete: false` preserves unresolved work. Missing raw IA metadata is explicitly reported as unavailable. To opt into model processing later, inspect `cleanup status`, then repeat the same inputs/run ID with an explicit backend/model and matching `--benchmark-summary`; use `--ai-limit` to bound requests. Omitting that limit with a model processes the pending queue. Changing extraction code, source fingerprints, or lexicon requires a new run ID.

Full-scale export exposed a SQLite planner issue absent from the bounded sample: run-ID indexes caused per-paragraph queue scans. Composite indexes now cover `(run_id, identity, input_hash)` and legacy `(run_id, paragraph_id, identity)` lookups. The static-only run was interrupted and resumed with the same queue and cached preprocessing; see `PROGRESS.md` for its terminal verification state.

Performance follow-up: the user observed Python saturating one Mac CPU core at approximately 99%. Profile stage costs and evaluate multiprocessing for CPU-bound extraction/validation/serialization and threads for I/O; benchmark throughput and memory while retaining deterministic order, source anchors, ledger validation, and sequential Ollama requests. This investigation is pending in `PROGRESS.md`.

### Operator command: one-hour local Qwen session

From the project directory, inspect the existing queue first:

```bash
uv run globe cleanup status --run-directory artifacts/runs/static-final-20261011 \
  --run-id static-final-20261011
```

Then run up to one hour of sequential local cleanup (also capped at 1,000 requests):

```bash
uv run globe cleanup run --run-directory artifacts/runs/static-final-20261011 \
  --run-id static-final-20261011 --backend ollama --model qwen3.8:27b-mlx \
  --limit 1000 --max-seconds 3600 --progress-interval 30
```

The budget is checked between jobs. A request already in flight finishes before exit, so elapsed time can exceed one hour by that request. Successful patches and review decisions are saved in SQLite as each job finishes; rerun the same command to continue pending jobs. Local API cost is zero; hardware/electricity costs are excluded. Use `cleanup status` in another terminal to watch progress. This command updates the queue; it does not regenerate canonical/RAG exports. After the worker exits, repeat the documented static-first command with `--backend none --ai-limit 0` to materialize saved results and refresh validated exports.

Final static export completed: **5,412 pages, 296,995 paragraphs, 19,803 RAG chunks**, built-in validation passed; cached resume/export took **447.34 s**, excluding earlier extraction and the interrupted slow lookup attempt. There are 22,547 pending model jobs and 152,889 review records; dates remain unknown on 5,321 pages and chamber on 5,173. No full-corpus model requests were made. The separate full verifier completed before the wrap-up stop reached it: all 209,609 static patches replayed, source coverage/raw text and anchors matched, output hashes passed, and all 15 raw source fingerprints remained unchanged. Evidence: `artifacts/runs/static-final-20261011/independent_verification.json`.

### Reviewed external multiprocessing POC

OpenCode's `tmp/performance/PARALLELIZATION_PROPOSAL.md` reports full-corpus process-worker speedups of 6.4–10.2× per stage and a summed-stage projection of 563.5 → 78.5 seconds (7.18×), using 14 workers and ordered file/range partitions. Codex independently hashed its final parallel canonical pages and RAG chunks; both exactly match the published production hashes. Saved review/report/logs: `artifacts/performance-review-20261011/`. This establishes equivalence for those outputs and the benchmark inputs; production integration, failure handling, lock preservation, and completed/review/legacy queue cases remain pending. The full materialization benchmark uses a pending-only queue. No additional benchmark or model calls were made for this review. See `PROGRESS.md` for the integration checklist.

### Final operator workflow and additional small-model POC

`HAPPY_PATH.md` collects the recommended human-run commands and scope boundaries. An isolated eight-case Muse Glimmer benchmark took 71.273 s with five schema/JSON failures, one valid response that missed an expected correction, and two unchanged controls matching expectations. It is not recommended under the tested configuration. Qwen remains the preferred local POC candidate and Mini the faster paid candidate; sample labels/timings are provisional, and prompt versions differ between the earlier comparisons and Muse. Local inventory has no separately named Meta Llama model. Codex rechecked current source/output fingerprints and all required code gates (81 tests), without repeating the earlier provider POCs or starting production model processing. Production queue state has advanced outside these POCs; earlier static exports remain their original verified snapshot until the human explicitly refreshes them.

## Makefile shortcuts

The small root `Makefile` wraps existing CLI commands. `make gate` applies both formatters and runs every required check/test. `make run-workflow` aliases `make run-static`: prepare or refresh the static/canonical/RAG files without model calls. Then choose `make run-qwen`, `make run-gemma`, or `make run-openai` for an explicit one-hour/1,000-request worker on the same existing queue. Each worker target first reports queue status; `make status` is also available separately. Run `make run-static` after the worker exits to publish its accepted patches. Targets are serialized, have no configurable variable matrix, and use the current prepared local run/lexicon. OpenAI requires the saved key and incurs API charges. See README or HAPPY_PATH for the command table.

## Word-list setup on macOS

The simple Make targets require `artifacts/static-audit-20261011/supplemented-lexicon.txt`. The file is generated and ignored by Git. On the prepared machine it already exists; do not rebuild it while a run is active. For a fresh checkout on macOS with the standard dictionary files, create it once:

```bash
mkdir -p artifacts/static-audit-20261011
{
  printf '\n'
  cat /usr/share/dict/words /usr/share/dict/web2a /usr/share/dict/propernames resources/static-lexicon-supplement.txt
} | LC_ALL=C sort -u > artifacts/static-audit-20261011/supplemented-lexicon.txt
```

This combines the base dictionary, additional forms, proper names, and the tracked project supplement. The leading blank entry preserves the existing prepared file's exact format. Reconstruction from the current machine's dictionaries was compared in memory and matches the existing word list byte for byte. On machines without these dictionary files, obtain the prepared lexicon or an equivalent documented word list before running the Make workflow. Changed dictionary content changes the run fingerprint; an incompatible existing run requires a new run ID and corresponding Make command adjustment.

## Continuing bounded quality POCs

New cleanup workers emit source-linked `job_result` events alongside lifecycle events. Each shows `before_text`, `after_text`, accepted patches and outcome: accepted normalized text or unchanged retained input for review/retry. Raw responses remain separate from accepted patches. Events include citations, model, timing and available provider finish metadata; parse-error raw output/usage also persist in the review record. Completion/no-op/rejection/retry checks pass; `make gate` has 90 passing tests. The active hour-long worker retains its original loaded logging code.

The next benchmark design should compare candidates on a fixed, versioned task set, then use a different model to review a seeded sample of original inputs versus candidate outputs. Human review supplies the reference labels and adjudicates disagreements; model review alone cannot certify correctness. Keep before/after evidence, source anchors, model/prompt configuration, failures, time, tokens and costs, and report human-reviewed coverage. The implementation checklist and evaluation measures are in `PROGRESS.md` under “TODO: reproducible model benchmarks with independent review.” This workflow is planned, not implemented.

The user approved two hours of 15-minute scheduled local-only checks, with at most four additional isolated POCs of 15 minutes/60 requests each. Preserve the active one-hour Qwen worker and serialize all local requests. `PROGRESS.md` records the cumulative experiment count and exact process/run state. Stop early if quality plateaus or unsafe accepted edits appear; this permission does not authorize paid requests or draining the full queue.

The first live-worker snapshot sampled 40 cases across all five parts: 30 completed and ten review cases. Every completed sample replayed its ledger exactly. The cohort had 239 completed, 84 review and one claimed job, with 26.0% of resolved cases held for review. Early/index-heavy queue order limits generalization to debate text. Preserve unresolved artifacts and ambiguity; completed does not mean error-free. Evidence is under `artifacts/poc-quality-20261011/`.

The subsequent text-context review found 21 supported and three ambiguous accepted patches among 24 patches; 14 completed samples had no changes and may retain OCR artifacts. A human review packet/template is saved in the same evidence directory with every human verdict pending. No full-corpus quality rate follows from this stratified sample. Benchmark/provider instrumentation retains finish reason/status, raw output and usage for malformed, empty and truncated responses, and rejects explicitly incomplete outputs. This applies to new calls; the active worker retains its loaded code. Read-only safeguard analysis flags non-mechanical wrap changes, mixed numeric repairs and symbol removals for further evaluation; these categories include legitimate repairs and do not establish harm rates.

The hour worker is now terminal: 838 requests resolved, 653 completed and 185 held for review; no claimed jobs remain. Its saved report/log are under `artifacts/poc-quality-20261011/`. Summed request duration is 3,589.441 seconds; usage is partial (817/838). The current pending queue projects roughly 24.7 hours at that cohort's average request duration, excluding review/retries/export and assuming the same early/index-heavy workload. Local API charges are $0; hardware/electricity are excluded.

The subsequent fixed 12-case Qwen/Gemma challenges took 59.56/55.17 seconds wall respectively. Both matched only 6/12 provisional targets and preserved all three controls. Offset-group agreement was 0/6 for Qwen and 1/6 for Gemma, below the required 5/6. Exact-source validation held invalid proposals; Gemma also accepted a capitalization change with a residual slash. Further model calls under this schedule are stopped at two POCs; use remaining checks for offline deterministic fixes and source-span validation. Do not infer production readiness or loosen validation from these results. Per-case reviews and paired scorecard are under `artifacts/poc-quality-20261011/challenge-preparation/`. Canonical/RAG exports have not been refreshed from the live queue.

A provider-free six-record pilot with cloned lexicon entries `alexandria` and `leavenworth` produced four geometry-anchored wrap repairs across three records and preserved the unsupported trailing `rail-`. Evidence: `artifacts/poc-quality-20261011/static-wrap-poc/challenge-six-report.json`. These are candidate static improvements, not adopted production lexicon changes or historical gold. Review spelling/negative controls and sample affected repairs before changing fingerprints or rebuilding the queue. Exact challenge prompt/schema/configuration is preserved in `challenge-preparation/configuration-note.json`.

The subsequent streaming coverage audit found 110 candidate wrap repairs in 98 paragraphs across all five parts; 79 would cease routing to a model, while 19 retain other signals. All 34 sampled patches in 30 seeded paragraphs preserve raw letters/case and have adjacent-line hOCR evidence; ledgers replay exactly. Five negative fixtures stay unchanged. Evidence: `artifacts/poc-quality-20261011/static-lexicon-coverage/`. The two forms remain proposals; production lexicon/queue/exports are untouched and unsampled cases are not certified.

`make status` now estimates pending plus claimed model jobs from timed completed **and review** outcomes, ignoring missing/negative durations. `estimated_pending_hours` is the explicit field; `estimated_remaining_hours` remains its compatibility alias. `average_resolved_seconds` and `timed_resolved_jobs` show the timing basis. Review backlog still contributes to the `remaining` count, but its future human review time is excluded from model hours. The current all-history estimate is 23.51 hours, versus the separate hour-cohort projection of 24.7 hours; workload/provider mix, retries, export and hardware can change actual time. Required gates passed with 93 tests; no model requests for this change.

The next offline inventory found 21,980 residual line-end wrap hints in 17,902 paragraphs. Twenty ranked candidate forms are absent from the prepared lexicon; two anchored examples per form all repair under temporary entries using the existing normalizer. Start further review with ordinary words such as conferred, postponed and supplies, while preserving compound and historical spelling uncertainty. These are sampled opportunities, not adopted additions or measured request savings. Evidence: `static-lexicon-coverage/candidate-inventory.json`.

Changed lexicons require new run IDs; the current workflow has no cross-run result migration command. An audited exact-input reuse mechanism must be designed and checked before adopting changes while retaining prior work. `static-lexicon-coverage/rollout-plan.json` records this gap and unexecuted candidate commands. Separately, `span-contract-proposal.json` proposes host-defined source-span IDs and constrained decisions to avoid unreliable model offsets; it is not implemented or provider-tested. Model calls remain stopped at two additional POCs, and production queue/lexicon/exports remain unchanged.
