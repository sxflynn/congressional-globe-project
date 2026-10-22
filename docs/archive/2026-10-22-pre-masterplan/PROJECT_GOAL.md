# Project goal and architectural direction

Updated: 2026-10-11. This is the long-term architectural brief. `AGENTS.md` summarizes the operating rules; `PROGRESS.md` records what is implemented and what should happen next. Proposed models and stages below are design requirements, not claims that they already exist.

## Desired end state

Produce a high-quality, portable, structured historical corpus of all five locally collected parts of the 39th Congress, 1st Session of _The Congressional Globe_. It should support historical research, conventional keyword/full-text and structured database queries, semantic/vector search, and retrieval-augmented generation, independently of any embedding model, vector database, or search framework.

Canonical JSON/JSONL is authoritative for original OCR, accepted cleaned transcription, immutable-source references, and correction provenance. Separate authority and enrichment layers provide richer metadata without silently changing canonical text or presenting model inference as verified fact. Embeddings and indexes are disposable, reproducible derivatives. Any retrieved passage or generated answer must retain precise citations back to the canonical paragraphs, printed pages, Internet Archive items, scan leaves, and original OCR/correction history.

**Codex builds the workflow.** Substantive historical enrichment should eventually be performed by reproducible, explicitly authorized LLM calls and deterministic or authority-backed stages, rather than manually assigning the whole corpus in a coding session. Build schemas, prompts, orchestration, validation, retry and batching policies, caching, provenance, review, and export mechanisms. Keep priority on a reliable corpus first. This brief does not authorize immediate implementation of every enrichment, full-corpus model calls, re-OCR, or visual validation of original scans.

### Research questions the architecture must support

- What did Republican senators from Ohio say about Reconstruction during March 1866?
- What arguments did Thaddeus Stevens make about civil rights?
- What was said about a particular bill, distinguishing debate on it from passing mentions?
- How did Democrats and Republicans differ in their arguments about suffrage?

These require passage-level evidence and historically dated affiliations; neither a page nor today's retrieval chunk is necessarily one speech or one historical entity.

## Layered data products

| Layer | Authority and content | Relationship to other layers |
| --- | --- | --- |
| Immutable source inventory | Raw hOCR, DjVu, available IA metadata, page maps, hashes, source locations | Never rewritten by cleanup or enrichment; missing metadata remains explicit |
| Canonical transcription releases | Pages and paragraphs, original/accepted normalized text, layout, source identity, correction ledgers | Authoritative transcription; versioned releases preserve earlier corrections and references |
| Authority datasets | People, congressional service and affiliations, subjects, legislation, committees, organizations, places | Stable internal IDs, cited external records, versioned assertions and uncertainty |
| Enrichment datasets | Speaker/date/boundary proposals, entity links, subject assignments, legislative relationships | Link to canonical release and evidence spans; independently versioned and rerunnable |
| Search exports | Derived passages/chunks, linked metadata, citations, boundary/aggregation provenance | Deterministic products of selected canonical and enrichment releases; retain underlying paragraph/page links |
| Indexes and embeddings | Full-text indexes, structured-query adapters, vectors, vector indexes | Rebuildable products with export/model/config fingerprints; never historical authority |
| Audit and review datasets | Stage runs, LLM calls, attempts, validation, acceptance, review decisions | Explain every transformation and assignment; preserve failed and superseded outputs |

JSON/JSONL plus documented schemas, foreign keys, and manifests should allow consumers to build their own database/search systems. A local full-text or structured adapter may demonstrate usage, but portable exports must not require it or an LLM.

## Existing support and gaps

This mapping is based on the current Python contracts and workflow, not planned capabilities.

| Requirement | Present support | Additional design needed |
| --- | --- | --- |
| Canonical transcription and provenance | `PageRecord`, `ParagraphRecord`, `TextEdit`; raw/normalized text, static/AI ledgers, input hashes, geometry, hOCR IDs | Explicit canonical release/schema identifiers and offset-coordinate contracts; preserve historical releases |
| Stable source identity | Item, part, leaf, local paragraph ID; composite identity used in queues/merge | Portable namespaced paragraph/page identifiers and migration aliases; local paragraph ID alone is not globally unique |
| Congress/session context | Fixed corpus scope and human-readable citations | Typed collection/Congress/session metadata carried through exported records |
| Date and chamber | Sourced string values in paragraph `context`; conservative heading/order checks; chunks aggregate only consistent evidenced facts | Typed observed/inferred assertions, date ranges/precision, evidence, status and uncertainty; no unsupported propagation |
| People and affiliations | Source text and span/layout anchors available | Person authorities, temporal service/party/state assertions, speaker attribution and mention separation |
| Subjects and legislation | Draft subject vocabulary, evidence/proposal contracts, source-anchored cue matching and blinded offline review sampling | Human-adjudicated subject quality, model-stage orchestration, curated authorities and legislation identities/relationships |
| Retrieval | Page-bounded `RAGChunk`, citations and `RAGParagraphSource` records | Speaker-turn/boundary-aware passages; typed mixed metadata and aggregation policies |
| LLM orchestration | Strict cleanup output schema, SQLite queue, raw responses/usage/errors, attempts/events, explicit provider choice, resume, local request lock | General stage/call/attempt audit, prompt/schema versions, dependency-aware caches, retry/batch lineage and review policies |
| Validation and reproducibility | Source/artifact fingerprints, ledger replay, queue matching, coverage checks, staged exports and independent verifier | Foreign-key/evidence validation, authority temporal checks, enrichment evaluation fixtures and release selection policies |

Existing `context: dict[str, str]` and flexible `ai_provenance` fields are useful compatibility bridges, not the future typed authority/enrichment model. Existing job state is not a complete append-only audit of every attempt. Do not claim this brief's mechanisms already exist.

## Proposed metadata contracts

All new external boundaries should have versioned Pydantic v2 contracts and portable JSON Schema. Use explicit nullable/unknown values rather than inferred completeness. Confidence measures uncertainty within a method; it is not proof of correctness or a universal calibrated probability.

### Identity and evidence

Keep stable source-based IDs separate from text/config hashes. Corrections should create a new text/release version, not erase a paragraph's identity. Evidence references include namespaced paragraph ID, canonical release and text hash, text layer (`original_ocr` or a named normalized revision), character start/end with a documented half-open Unicode coordinate convention, and exact quoted span. Validate offsets and quotes against the referenced text. Preserve page/leaf/item, printed-page source, hOCR/geometry anchors and source-file hashes. Multi-paragraph or cross-page assertions require an ordered list of evidence references. If extraction segmentation changes, provide explicit identity mappings rather than pretending boundaries were unchanged.

### Shared assertion envelope

An enrichment assertion should identify its stage/run, target paragraph/span/turn and authority IDs; proposed value and alternatives; evidence references; concise evidence basis (not hidden chain-of-thought); method (`rule`, `authority`, `model`, `human`, or a documented combination); confidence/uncertainty; validation result; review status; timestamps; model/call reference where applicable; and supersedes/rejection relationships. Keep lifecycle states such as proposed, accepted by policy, reviewed, rejected, superseded and unknown distinct from factual verification. An automatically accepted model result remains a model result. Never overwrite competing proposals simply because a newer run finished.

### People, service, and speakers

Separate `PersonAuthority` (stable ID, canonical name, name/title variants, sourced external IDs) from service and affiliation assertions (person, chamber, state, party, applicable date interval/precision, evidence/source, status). Party and state are historically dated claims rather than timeless person attributes. A service interval alone must not invent an unsupported party affiliation.

`SpeakerAssignment` links a passage/span or turn to a person candidate and includes supporting printed designation or explicit continuation evidence, alternatives, method, configuration and review state. `EntityMention` records people merely mentioned; mention extraction must not silently become speaker attribution. `SpeakerTurn` is an ordered set of canonical spans and continuation/boundary relationships that can cross paragraphs and pages. Preserve quotations, procedural interruptions, uncertain attribution and multiple speakers within a paragraph. Boundary changes produce new derived turn versions with links to the same canonical material.

### Subjects and entities

`SubjectAuthority` contains stable topic ID, preferred modern label, historically appropriate aliases, broader/narrower relationships, vocabulary version, and sourced external authority links when verified. Historical phrases such as “elective franchise” and “right of suffrage” can map to “voting rights” without rewriting historical wording. Support Reconstruction, citizenship, suffrage, constitutional amendments, federalism, civil rights, military affairs, taxation and procedure, with vocabulary expansion controlled and versioned. `SubjectAssignment` is many-to-many, may be empty or unknown, and retains evidence, method and review status. An evaluated “no subject assigned” is distinct from an unprocessed passage.

`LegislationAuthority` scopes numbers and identities by Congress/chamber/instrument type as needed and retains formal/informal title variants, bills, resolutions and constitutional amendments, dates and cited sources. `LegislationRelation` distinguishes under consideration, quoted, referred to, or merely mentioned; do not resolve solely by an ambiguous number/title. Parallel entity authority/mention/link models support committees, organizations and places. Keep LLM candidate links distinguishable from verified authority matches.

### Dates

Use explicit date assertions with point/range, precision, proposed event meaning, method, evidence, alternatives and status. Distinguish catalog/edition dates from a proceeding or speech date. Rules or LLMs may propose continuation/date intervals only with supporting evidence and declared boundaries. Unknowns stay unknown; plausible guesses do not become definitive filter metadata. Do not propagate dates merely to increase coverage. Conflicts remain inspectable, and adjudication selects a versioned policy outcome without deleting alternatives.

## Controlled processing stages

Each stage must declare input/output schemas, dependencies, evidence windows, configuration, validation and acceptance policy, plus cost/time estimates where relevant. Prefer static rules and authority lookup where they are defensible; use model calls for contextual work. Enrichment stages can be rerun independently without repeating OCR cleanup.

| Stage | Typical input and output | Important controls |
| --- | --- | --- |
| Extraction/static cleanup | Immutable sources → canonical pages/paragraphs and edit ledgers | Streaming, source order, geometry, coverage, hashes and reversible corrections |
| Optional OCR model correction | Residual text/evidence → patch proposals | Validate spans/input hashes; preserve numerical/punctuation ambiguity; ledger and review |
| Boundary detection | Ordered canonical windows → turn/proceeding/quotation/continuation proposals | Explicit start/end evidence, overlap/coverage rules, cross-page context and uncertainty |
| Speaker attribution | Spans/turns, designation text, authority candidates → assignments | Speaking vs mentioned, continuation evidence, temporal plausibility, candidate alternatives |
| Entity/legislation resolution | Mentions/context and cited authority candidates → links/relations | Stable scoped identities, under-consideration vs mentioned, evidence-backed disambiguation |
| Subject classification | Canonical spans and selected vocabulary version → assignments | Valid topic IDs, many/none/unknown states, evidence, vocabulary hierarchy and review |
| Date/context inference | Ordered context and known assertions → date/chamber proposals | No fabricated values or unsupported boundary crossing; conflict/precision validation |
| Adjudication/export | Selected assertion/authority releases → research/search exports | Explicit acceptance policy, unknown/mixed handling, linkage checks and reproducible manifests |

Dependency planning should support iterative boundary/speaker/date proposals without overwriting earlier runs or creating hidden cycles. Freeze the selected dependency versions for each run; ambiguous continuation is reviewable rather than automatically inherited.

### LLM call and orchestration contract

Persist a `StageRun`, `LLMCall` and append-only `Attempt` history covering input IDs and hashes, evidence-window IDs, canonical/authority/vocabulary releases, schema version/hash, prompt/template version/hash and rendered request reference, provider/model identity and available revision, parameters, timestamps, raw output, parsed output, usage/cost, duration, validation errors, retries, finish reasons, acceptance/review status and batch correlation IDs. Keep secrets outside artifacts. The same record discipline applies to rule and authority-backed stages with method/configuration/source versions instead of model metadata.

Cache keys must include stage code, all relevant inputs and context, prompt, model, parameters, schema, authority/vocabulary and policy versions. Reuse only compatible validated results, distinguish cached from new calls, and preserve their lineage. Changed dependencies trigger deliberate reprocessing rather than silent substitution. Archive earlier outputs and select an explicit active release.

Define bounded retries/backoff for transient failures/rate limits, preserve every attempt, and route malformed or evidence-invalid results to review rather than treating an HTTP success as accepted data. Persist partial progress and costs. Batch execution must correlate stable job IDs independently of result ordering and reconcile into one authoritative job store. Review thresholds are stage-specific and evaluated on labeled samples; model confidence alone must not authorize facts. Ollama remains strictly one request at a time. Static processing may use verified process-worker paths without changing these contracts.

## Retrieval and query semantics

A search passage is a derived object with stable derivation identity, canonical span links, citation anchors, selected enrichment-release IDs, text/context, and a documented boundary policy. Preserve speaker turns or split at meaningful boundaries when useful; overlapping context must be explicitly labeled so evidence is not assigned to the wrong speaker. A single page/chunk may contain multiple speakers, parties, states, topics, bills or dates. Carry span-level assignments or typed sets/mixed indicators; only expose a scalar when every relevant constituent agrees under the documented policy. The current conservative date/chamber aggregation should remain the minimum standard.

Resolve party/state through time-valid authority assertions associated with the attributed speech date. Uncertain dates/affiliations must not falsely satisfy exact historical filters. Query interfaces must distinguish confirmed matches, confirmed nonmatches, unknown/unprocessed metadata and conflicting proposals, and let users choose whether to include uncertain results. Topic/bill filtering must also declare whether it includes only accepted/reviewed assignments or proposed ones.

Conventional keyword/full-text and structured queries must work without an LLM. Hybrid retrieval combines those filters with a replaceable semantic adapter. Embedding manifests identify passage export/release, text hash, model/configuration, dimensions and preprocessing; rebuilding vectors must leave historical records untouched. Any optional answer-generation stage cites retrieved evidence spans and cannot treat inference as an uncited fact.

## Immediate architectural guardrails and phased roadmap

1. Finish and maintain the reliable canonical corpus and reproducible cleanup/export workflow. Preserve source identity, evidence geometry, ledgers, source versions and uncertainty now; do not invent historical metadata to fill gaps.
2. Document typed release/identity/evidence/assertion/call-audit contracts and a representative research-query fixture set before implementing enrichment. Keep migrations compatible with existing anchors and already verified output.
3. Develop small authority datasets and schema fixtures, including temporal party/state affiliations, subject hierarchy, and scoped legislation IDs. Every real assertion needs sourced evidence; fixtures must be labeled synthetic when applicable.
4. Build independently rerunnable, explicitly opt-in enrichment components with structured prompts, validation, incremental caches, retries, batch reconciliation and review. Evaluate bounded samples before scaling.
5. Export turn-aware research passages and demonstrate ordinary full-text/structured filtering, preserving unknown/mixed values. Add optional vector/RAG adapters against portable exports.

This is architectural direction, not an instruction to perform the entire historical enrichment now. New code should avoid locking canonical data to embeddings, assuming one speaker per page, attaching timeless party/state attributes, replacing unknown dates with guesses, or mixing generated tags with transcription. Human review mechanisms belong in the design; re-OCR and original-image visual validation are outside this immediate scope.
