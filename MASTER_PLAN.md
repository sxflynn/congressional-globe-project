# Congressional Globe master plan

Updated: 2026-10-22. **This is the single authoritative project plan and progress record.**

Every engineering agent must read this document before working, use its ordered milestones, and update its current status and next action before handing off. New instructions from the human take precedence. `AGENTS.md` is the entry point; `README.md` is a short operator tutorial. Neither maintains a competing roadmap. Earlier planning files now point here; their original contents are preserved in the [historical archive](docs/archive/2026-10-22-pre-masterplan/README.md).

Navigation: [Goal and scope](#1-goal-and-division-of-responsibility) · [Data/search architecture](#3-data-and-retrieval-architecture) · [Resumable workload](#4-long-running-workload-contract) · [Evaluation](#5-evaluation-and-decision-rules) · [Current progress](#6-current-progress-and-evidence) · [Ordered checklist and next POC](#7-ordered-master-execution-checklist) · [Operator commands](#8-operator-commands-and-current-limitations) · [Agent rules](#9-agent-working-rules-and-handoff-discipline).

## 1. Goal and division of responsibility

Build a trustworthy, portable historical research and search foundation from **all five locally collected parts of the 39th Congress, first session of The Congressional Globe**. A researcher or future AI assistant must be able to find relevant passages, apply historically meaningful filters, read surrounding context, and follow precise citations back to the primary documents.

**The engineering agent builds and proves the workflow. GPT Mini, local Qwen through Ollama, or another deliberately selected provider performs the eventual repeated workload. The human launches large runs.** A job taking many hours is acceptable; losing results, repeating paid compatible work, hiding failures, or inventing historical metadata is not.

Develop through tiny, bounded POCs, independent source-context review, and human spot-checks. Record actual time, tokens, costs, failures and uncertainties. Build only the machinery needed to advance the next research capability; passing schemas or accumulating more infrastructure is not a substitute for useful search and defensible metadata.

### What the finished foundation must support

| Capability | Required behavior |
| --- | --- |
| Exact and keyword search | Names, phrases, numbers, quotations and ordinary full-text queries without an LLM |
| OCR-tolerant lexical search | Find defensible spelling/line-break variants, including split words, through a derived matching view while preserving raw text and exact source mappings |
| Semantic/vector search | Find related arguments expressed differently; do not assume embeddings reliably repair every OCR error |
| Combined prefilters | Narrow searches by date/range, speaker/person, topic, legislation, and other supported historical attributes before ranking relevant candidates; combine filters deliberately |
| Human primary-source access | Return passages, surrounding context and citations/links to original OCR and page images, IA item/scan leaf and printed page |
| Future AI tools | Let a bot issue multiple filtered keyword/vector searches, inspect context and compose cited answers from returned evidence |
| Portable handoff | Documented data releases, schemas, indexes and query/tool contracts that another project can use to build the application |

Representative queries include Freedmen's Bureau debates; military affairs; Andrew Johnson's conflicts with Congress; a particular bill; speeches by a named member; and date-bounded research. More demanding examples include Republican senators from Ohio discussing Reconstruction in March 1866, Stevens's civil-rights arguments, and party differences over suffrage. These are acceptance scenarios, not claims that every required filter works today.

### Scope boundary

- **Deliver now through this plan:** source/data preparation, identity/provenance, search representations, token accounting, chunking, evidence-backed enrichment, embeddings/indexing, resumable processing, evaluations, and a documented backend/data handoff.
- **Defer:** polished web interface, production chat inference/application, and deployment/hosting product. A thin query API or tool adapter may demonstrate the handoff. MCP is an option, not a required dependency or a reason to build a UI now.
- **Current corpus:** one congressional session in five parts, not the entire historical Globe or a multi-decade collection. Design for extension without claiming that broader coverage exists.
- **Do not expand into:** re-OCR or systematic visual verification of original images. Human access and accurate image links are required; an image-verification project is not.
- **OCR decision:** preserve the completed cleanup path and all outputs. The active hypothesis is that raw OCR plus organization, search normalization and enrichment may be sufficient. Additional cleanup is optional and must earn its cost through demonstrated failures. Neither perfect cleanup first nor “OCR never matters” is an established conclusion.

## 2. Historical integrity and source identity

| Part | Internet Archive item identifier |
| ---- | -------------------------------- |
| 1    | `congressionalg7391unit`         |
| 2    | `congressionalglo7392unit`       |
| 3    | `congressionalglo7393unit`       |
| 4    | `congressionalglo00unit`         |
| 5    | `congressionalglo7395unit`       |

Retain each item's original `_hocr.html`, `_djvu.xml` and `_page_numbers.json`. Source OCR, geometry and available raw IA metadata remain immutable. Preserve original metadata objects, including catalog notes and identifiers; do not flatten away conflicting facts. Catalog-level serial dates, edition/title-page dates and dates of proceedings are separate assertions. Raw IA catalog metadata is currently recorded as unavailable locally for the five parts; do not imply it was downloaded.

Every passage and assertion must resolve to its source: item, part, scan leaf, printed-page value and its provenance, paragraph identity, hOCR page/line IDs, geometry where available, text layer and text hash. Local paragraph-ID strings repeat across parts; use composite source identity and eventually portable namespaced IDs. Preserve aliases/migrations when extraction boundaries or identifiers change.

Evidence spans use half-open Unicode character offsets into a specified text layer, exact quotes and input hashes. A matching ID or fluent explanation is insufficient: validate the actual span and source anchor. Multi-paragraph assertions retain ordered evidence. Search-view offsets must map back to canonical text; normalized text is not a replacement primary source.

Keep original OCR, accepted cleaned versions and correction ledgers accessible. OCR correction remains patch-based, validated and reversible. Never silently overwrite text, prior model proposals or historical disagreements.

## 3. Data and retrieval architecture

### Separate authoritative records from rebuildable products

| Layer | Contents and responsibilities |
| --- | --- |
| Immutable sources | Original derivatives, available IA metadata, file fingerprints and download/source references |
| Canonical releases | Source-based pages/paragraphs, original and accepted text, source anchors, correction history, schema/release identity |
| Authorities | Stable people, temporal service/affiliations, subjects, places, legislation, committees and organizations; cited external records where verified |
| Enrichments | Independently versioned speaker/date/boundary/entity/subject proposals, supporting evidence, method, uncertainty and review decisions |
| Search exports | Derived retrieval passages linked to ordered canonical spans, selected metadata releases, context relationships and source citations |
| Search indexes | Lexical representations, vectors and index structures; disposable products identified by their input/configuration manifests |
| Audits/reviews | Stage runs, attempts, raw replies, failures, validation, acceptance policies, human labels and supersession history |

Canonical and enrichment JSON/JSONL plus documented schemas remain usable without a particular embedding model, vector database, search framework or LLM. Provide ordinary database/full-text access as well as semantic adapters. Do not mix vectors from different embedding spaces in one index.

### Required metadata semantics

- **People and speakers:** separate a person mention, actual floor speaker, petition presenter, letter author, quoted speaker and unnamed chair/title. Resolve printed variants to stable person authorities only when supported. A person's state, party and chamber are time-scoped service assertions, not timeless attributes. Service alone must not invent party affiliation.
- **Boundaries:** identify turns, interruptions, quotations and continuations across paragraphs/pages. A paragraph can contain multiple speakers; a page can contain unrelated proceedings. Keep uncertain continuation links reviewable. Retrieval windows are not automatically speeches.
- **Dates:** retain point/range, precision, kind, evidence, method, alternatives and status. Do not copy dates across unsupported boundaries or infer a complete date from catalog context alone. Unknown stays unknown.
- **Controlled subjects:** stable IDs, preferred labels, historical aliases, scope notes and broader/narrower links. Support modern discovery terms without rewriting nineteenth-century wording. Freedmen's Bureau and Andrew Johnson research require useful entity/topic relationships; the ten-subject draft is not the final vocabulary.
- **Legislation:** scope bill/resolution/amendment numbers by Congress, chamber and type as necessary; retain title variants and cited authority sources. Distinguish under consideration, proposed, quoted, referred to and merely mentioned. An isolated number is not a resolved bill identity.
- **Places and other entities:** keep source mentions separate from resolved authority links. Disambiguation needs context and evidence, not a spelling match alone.
- **Loose discovery hints:** keep free-form model suggestions separate from controlled assignments. They may help discovery; they cannot satisfy trusted historical filters or masquerade as authority matches.
- **Unknown and review state:** distinguish unprocessed/unannotated, no supported assignment, unknown, mixed, conflicting, out of vocabulary, proposed, accepted by declared policy, human-reviewed, rejected and superseded. A model result accepted by software is still model-derived, not verified history.
- **Human decision already made:** an explicit petition request counts as a substantive topic even without a long debate. Keep petition author/presenter, alleged claims and congressional endorsement separate. A routine referral or a cue word alone does not establish substantive discussion.

All inferred assignments retain supporting spans, concise evidence basis, method, configuration/model/prompt versions, uncertainty and review status. Preserve competing proposals and select explicit versions for export. Human-review imports require explicit human-authored input; provider outputs must not claim human-review status.

### Chunking, tokenization and filtering

1. Preserve canonical paragraphs. Derive coherent retrieval units with meaningful turn/proceeding boundaries where defensible; link longer speeches to parent speech/context and neighboring passages.
2. Measure actual token lengths for the selected model/backend. Choose chunk size and overlap through POCs; do not hard-code an unmeasured universal 400–800-token policy. Record splitter/tokenizer/version, overlap, text layer and any contextual metadata added to embedding text.
3. Preserve exact and OCR-normalized lexical fields separately. Evaluate case/line-break/hyphen joining, phrase behavior and ambiguous historical compounds; avoid unrestricted joining that changes meaning.
4. Apply structured filters to the correctly attributed source spans or validated aggregation, then rank candidates. Multiple filters must refer to compatible evidence: a speaker in one paragraph and a bill in an unrelated paragraph cannot manufacture a speaker/bill relationship merely by sharing a page.
5. Return matching subspans/context and explicit mixed/unknown metadata. Define AND/OR, date-overlap and unknown-inclusion semantics; expose metadata coverage so missing values do not look like confirmed nonmatches.
6. Compare lexical, semantic and hybrid retrieval. Fusion/reranking is optional and must improve measured results, not merely be added because it is fashionable.
7. Record embedding model digest/revision, runtime, dimensions, quantization when available, query/document task instructions, truncation policy, normalization, input hashes and index configuration. Query/document conventions differ by model. Rebuild incompatible indexes deliberately.

## 4. Long-running workload contract

This contract applies to **every repeated stage**, not just the existing OCR cleanup worker. It is a requirement; it is not all implemented today.

| Requirement | Required operation and evidence |
| --- | --- |
| Explicit stage inputs/outputs | Versioned schemas, selected source/authority releases, declared dependencies and validation rules |
| Durable incremental work | Persist each finished result/checkpoint; publish validated exports safely; never depend on a live agent conversation |
| Pause/interruption/resume | Stop claiming work cleanly; retain in-flight attempt state; recover stale claims under a documented policy; resume pending work without losing valid results |
| Compatible reuse | Cache by input/context hashes, stage code, model/configuration, prompt/schema, vocabulary/authorities and acceptance policy; distinguish cache hits from new calls |
| Deliberate reprocessing | Changed dependencies create a new run/version; preserve prior outputs. No existing cross-run cleanup result migration command should be assumed |
| Independent stages | Retag or re-embed without repeating extraction/cleanup; freeze dependency releases to avoid hidden cycles |
| Provider choice | Same task contract for Mini and Ollama Qwen; record provider differences and validate compatibility, rather than assuming identical behavior |
| Audited attempts | Stage/run/call/task IDs; timestamps; raw request/response references; parameters; finish/truncation; usage/cost; errors; retries; validation and review decisions |
| Controlled failures | Bounded retries/backoff for transient failures; stop on permanent authentication/configuration failures; preserve malformed outputs and exhausted tasks for review |
| Idempotent recovery | Demonstrate no duplicate accepted work after interruption/resume; reconcile ambiguous network outcomes and partial batches without hiding unknown usage |
| Visible progress | Stream stage/total, completed/pending/review/failed/cached counts, elapsed time, throughput, tokens, cost and remaining-time estimate with its basis |
| Inspectable events | For cleanup show original and proposed/accepted text. For tagging show source excerpt, proposal and disposition. A progress event should help a human understand what happened |
| Cost discipline | Bound requests/runtime/output, record actual usage and estimated billing separately; unknown usage is not zero; include retries/review in projections and label tiny-sample estimates |
| Execution safety | Inspect live handles/processes and queue before another worker; Ollama calls sequential under the shared lock. Reuse compatible existing cleanup run IDs instead of rebuilding queues |
| Human operation | Small literal Make/CLI commands to prepare, inspect, run, stop and resume; full launch is an explicit human decision |

General stage/call audit and cache machinery must be justified with a small working enrichment slice; do not build a large generic framework without proving that slice. Before scaling, demonstrate forced interruption and recovery, retries/exhaustion, partial failure, invalid evidence, exact-input reuse and deliberate version invalidation. Test controlled worker failures, not only successful rows.

Use deterministic rules and authority lookup where defensible; models handle contextual tasks. Model-generated outputs are separate enrichment proposals. Workflow progress, historical correctness, retrieval relevance and answer support are four different things.

## 5. Evaluation and decision rules

### Small POC loop

1. Name the specific question and the next decision it will change. Check saved evidence; do not rerun a spent experiment merely because a new agent starts.
2. Freeze a small sample, whole evidence windows, input hashes, task/prompt/schema, vocabulary/model configuration, maximum calls/runtime and success/failure criteria before requests. Start with about five substantive cases when suitable; expand only for a stated gap.
3. Include positive, negative, truncated, unknown and mixed cases across the five parts and relevant document types. Known diagnostic retries are useful but are never fresh held-out quality evidence.
4. Use independent source expectations/review, with exact text evidence. Keep human labels distinct from AI-provisional assessments. Humans set semantic acceptance standards before examining held-out scores; do not invent historical-quality thresholds to obtain a pass.
5. Inspect every output in tiny batches, including unchanged, rejected, abstained and timed-out cases. Validate both evidence references and actual meaning. Record false assignments, omissions, role confusion, boundary leakage and answer qualifications.
6. Report per-case findings, time, tokens, cost, retries and failures. Choose the next action: adopt within a declared scope, revise one cause, route to review, or stop an unproductive approach. Do not repeat unchanged POCs or claim a quality winner from five examples.

### Separate evaluations

| Evaluation | What it proves and what it must not be confused with |
| --- | --- |
| Integrity | Exact sources, hashes, IDs, spans, manifests, ledger replay and coverage; does not prove historical truth |
| Tagging/attribution | Supported vs unsupported, missed, uncertain, incidental, OOV and role/date correctness; cue coverage is not safe auto-acceptance |
| Retrieval | Relevant passages at declared cutoffs, per-query misses/false positives, filter correctness and coverage; intended-target rank is not precision/recall when alternatives are unlabeled |
| Answers | Supported claims, correct attribution, preserved conditions/hedges/numbers, citations and appropriate abstention; fluent or schema-valid output is insufficient |
| Workflow | Resume/reuse/retry/version behavior and operator clarity; queue “completed” is not a clean-text or correct-history certificate |

For a fresh benchmark, freeze document splits, include indexes/Appendix/proceedings/date transitions, label relevant alternatives and negative controls, and establish disjointness from prior diagnostic/model inputs. Current exclusion inventory is incomplete: until complete enough to support the claim, call the sample diagnostic. Preserve reviewer disagreement and adjudication. Report precision/recall/MRR/coverage/abstention only with their proper denominators and limits.

To decide whether cleanup earns its cost, compare paired raw and existing static views with identical boundaries/settings. Separately test source-preserving search normalization and controlled enrichment. Include actual cleanup-plus-tagging/retrieval costs under a declared acceptance policy. Equal target ranks or similar tag counts do not establish that OCR never matters or that model calls can safely be skipped.

### Release decision

A passing code gate is necessary for shipped implementation, not sufficient for a research release. A release must demonstrate source traceability, the stated query/filter scenarios, unknown/mixed behavior, reviewed quality standards and coverage, reproducible builds/resume, and portable consumption by a separate client. Human approval of a concrete, reviewable pilot and its cost/time estimate precedes any full model/indexing launch. Do not claim complete unless these deliverables are actually demonstrated.

## 6. Current progress and evidence

### Current status — update this block in place

- **Active direction:** reviewed raw-text retrieval/enrichment pilot; retain optional cleanup for demonstrated failures.
- **Current milestone:** M1, bounded speaker/role/date evidence POC. Topic diagnostic complete; speaker/date retry not yet prepared or run.
- **Current code:** extraction, cleanup/export, embedding boundary, subject contracts/matcher/sampler and explicit human-label import are tracked. Production research search/enrichment workflow is not complete.
- **Latest project gate:** consolidation session 51262, terminal exit 0; 147 tests passed in 0.72 seconds; Ruff, ty, complexity ≤5 and Markdown formatting passed. Log `artifacts/document-consolidation-20261022/gate.log`. Last comparison commit before consolidation: `85c4cc6`.
- **Active processes:** last POC handles are terminal; no worker started by this documentation consolidation. Reinspect actual processes/queue before any new request. A saved lock/status file is not proof that a worker is live.
- **Queue last observed:** `static-final-20261011`, 1,339 completed / 423 review / 20,785 pending / 0 claimed. These are cleanup task states, not corpus accuracy.
- **Canonical snapshot:** 5,412 pages / 296,995 paragraphs / 19,803 page-bounded chunks. Its verified static export is older than subsequent SQLite AI results; do not describe it as refreshed from the live queue.
- **Human review:** ten raw windows / 92 paragraphs frozen, two windows per part, labels pending. Part-only sampling, length eligibility bias and incomplete historical exclusions mean diagnostic preparation, not established held-out gold.
- **Credentials:** Mini succeeded after the human replaced the expired `.env` key; no current credential blocker. Never copy the key into a document, log or chat.
- **Limits:** no full-corpus model enrichment or corpus-wide embedding job is authorized by this plan. The earlier specifically authorized one-hour cleanup worker completed; its authorization is not an instruction to drain the queue now. Historical two-hour scheduled POC permission does not authorize new recurring work.

### Verified foundation and known gaps

| Area | Implemented/evidenced now | Not yet established |
| --- | --- | --- |
| Sources/canonical | Five-part extraction; original/static text and ledgers; source hashes/geometry; independent full export verification | Portable release identities/migration packaging; raw IA catalog metadata acquisition |
| Cleanup execution | SQLite queue, bounded provider workers, locking, per-job results/events, validation, resume/export and basic Make targets | General enrichment-stage audit/cache; cross-run migration; full historical accuracy |
| Performance | External 14-process POC output hashes matched saved canonical/chunk outputs | Production multiprocessing integration, failure states and safe mixed queue rollout |
| Dates/chamber | Conservative source-heading context | Typed date assertions, reviewed propagation/boundaries, useful verified coverage |
| Subjects | Draft ten-subject resource; cue matcher with raw spans; proposals; offline review sample/import; five-case model diagnostics | Curated vocabulary/hierarchy, human quality labels, calibrated routing, installed production model tagger |
| People/places/bills | Source-linked candidate mentions and failed/partial role diagnostics | Resolved authorities, temporal affiliations, reliable speaker/date assignments and legislation relationships |
| Search | Tracked provider-neutral embedding boundary and local lexical/vector/fusion/filter prototypes | Shipped OCR-tolerant lexical index, trusted prefiltered hybrid retrieval, stable query interface and complete corpus index |
| Research handoff | Canonical JSONL, source-linked page chunks, local evidence/review packets | Turn-aware exports, durable full enrichment workflow, documented reproducible backend release usable from a clean consumer |

### Evidence ledger — completed diagnostics, not a restart list

Paths below are local, Git-ignored unless stated. Detailed original reports/commands are retained in the archive and artifacts. Preserve run IDs and raw responses; read results rather than repeating them.

| Evidence | Result | Limitation / next decision |
| --- | --- | --- |
| `artifacts/runs/static-final-20261011/independent_verification.json` | Full source/ledger/export verification;209,609 static patches replayed; 15 source fingerprints | Transcription correctness not certified; preserve baseline before refresh |
| `artifacts/performance-review-20261011/` | Parallel outputs matched; summed stages reported563.5 → 78.5 seconds with 14 workers | Summed-stage projection, not measured full workflow; integration pending |
| `artifacts/v2-pivot-20261011/tier2/` | 125 windows / 29 queries; BM25 raw 25/29, MRR .931; static 24/29, MRR .908 | Intended-target ranks; relevance alternatives/human labels missing |
| Same Tier-2 reports | Appended deterministic tags kept raw hit@1 but lowered MRR; one target fell 1 → 13 | This tests lexical tag appending, not value of trusted metadata; do not repeat as a general tagging strategy |
| Same Tier-2 semantic/hybrid reports | Native 4B 2,560 dimensions: raw/static 27/29; locally derived 1,024: each 28/29; RRF worse overall | Derived vector slice is not native 1,024 quality evaluation; no general model/dimension winner |
| `metadata-filters/span-selection/` under pivot artifacts | Old five-case Mini/Qwen role/date contract:each 1 valid / 4 held failures | Long IDs, unsupported roles, truncation/timeouts; use short aliases and smaller tasks next; verified speaker/date filter coverage remains zero |
| `raw-vs-static-transfer/` under pivot artifacts | 50 windows / 10 queries: both raw/static native 4B arms 10/10 targets first; 20 Mini answers and 10 Qwen answers reviewed provisionally | Saturated diagnostic; mixed answer omissions/abstentions; five pairs differ in retrieved contexts, so no causal OCR conclusion |
| `tag-cleanup-cost/` under pivot artifacts | 50 windows: boundary/hyphen-aware raw/static candidate sets identical, 78 assignments / 44 windows; 10 Mini calls ~$0.01967 | Candidate coverage≠precision or safe AI bypass; narrow initial vocabulary caused scope errors |
| `artifacts/v2-subject-review/` | Frozen 10 windows / 92 raw paragraphs, draft vocabulary and manifest; tracked sampler/import | Human labels pending; incomplete exclusions and part-only strata |
| `artifacts/v2-tagging-retry-20261022/` | Revised five-case raw-topic comparison;same inputs/prompt/schema/vocabulary; independent AI source review | Known cases, not fresh benchmark or quality percentages |

Latest paired topic execution:

| Provider/run | Timing and usage | Result |
| --- | --- | --- |
| Mini `topic-mini-20261022-02` | 13.690 seconds; 12,088 input / 1,095 output tokens; estimated $0.0139935 | 5 calls / 5 valid; unsupported military topic inferred from truncated “protection to American…” |
| Qwen `topic-qwen-20261022-01` plus `topic-qwen-warm-p1-20261022-01` | 173.246 seconds including failed first attempt; 13,368 recorded input / 2,006 output tokens; timeout usage unknown; $0 API | 6 calls / 5 usable outputs; extra salary/procedure scope uncertain |
| Historical Mini `topic-mini-20261022-01` | 5 HTTP 401 errors; no outputs/usage | Preserved failed expired-key run; blocker resolved; never count missing usage as zero billed work |

Both models found the main topics: voting/civil rights, explicit harbor/tax/restoration petitions, whisky taxation, bill procedure and Senate employee compensation. Qwen also surfaced useful separate discovery/OOV hints. Mini was more cautious about salary-related procedure but invented military subject matter from truncated evidence. Schema validity did not catch that semantic error. All assessments remain AI-provisional; the narrow sample does not establish model superiority or processing estimates for the corpus.

Full paired evidence: `mini-independent-review.json/.md`, `independent-review.json/.md`, `paired-comparison.json`, `mini-root-verification.json`, `root-verification.json`, source expectations and per-run frozen scripts/inputs/results. Do not rerun completed commands merely to inspect them.

### Model and fingerprint facts

- Machine: Mac mini M4 Pro, 64 GB unified memory. Local Qwen completion tag checked2026-10-22: `qwen3.8:27b-mlx`, digest `5642e97495e1a088883805981563dcdc4a040c2f53388b7a41d1f24d3622cf7e`. Recheck installed tags before future requests; do not assume resident/idle state.
- Embedding tags checked installed: `qwen3-embedding:4b` (2,560 dimensions) and `:8b` (4,096 dimensions). Native 4B 1,024-output compatibility was separately confirmed. The benchmark of locally sliced 1,024 vectors is distinct; do not silently relabel it. Smaller candidates remain future bounded comparisons, not downloads or current winners.
- Canonical snapshot SHA256: `4ab8ef6b325b650a0db002a94d690989f02d82333e977e5fed05c8f651772eeb`.
- Blind review packet SHA256: `138d7660e3dc2b342c8bc7518a6d3ee410f4126a62bb904cde508fca27207bba`; keep it blind while humans label.
- Draft vocabulary version `v2-subjects-draft-1`, content digest `3011bfe5d17e778ea29956fb356b477489277c55eb0a3754a80b63b1de158b57`. It is a draft, not a final authority release.
- Final local topic helper SHA256: `f5568a896d235a0ed7d6910bfcefb6deed442fb40546f09081b707bfa85cfc95`. It is an ignored prototype, not an installed production command. Per-run `script-used.py` is authoritative for earlier behavior.
- Existing static snapshot timing projection for 19,803 chunks was roughly 6.08–6.31 hours for embedding from a small throughput sample. It excludes new chunking, indexing/review and sustained-load differences; do not present it as a completion promise.

## 7. Ordered master execution checklist

These are the **only active roadmap and next-step list**. Update statuses here rather than adding another roadmap. A completed diagnostic does not complete the corresponding production milestone.

| ID | Status | Work and dependency | Completion evidence / exit condition |
| --- | --- | --- | --- |
| M0 | Foundation complete; preserve | Maintain immutable sources and verified canonical baseline; inspect old evidence | Saved hashes/ledgers and source coverage; known snapshot/queue distinction retained |
| M1 | **Next** | Tiny improved speaker-role/date POC using old failure lessons; source-linked short aliases; independent review | Per-case roles and scoped dates/unknowns, exact evidence, raw outputs/errors, time/cost; explain residual failures; diagnostic≠gold |
| M2 | Pending; offline work can overlap M1 | Prove a minimal durable enrichment slice through prepare→run→inspect→resume→review→export; generalize existing cleanup machinery only where needed | Forced interruption and partial failure recover; compatible results reused; version changes deliberate; auditable attempts/progress; no source mutation |
| M3 | Pending | Bounded people/place/legislation authority linking and topic hierarchy/coverage examples; use M1/M2 evidence | Real cited authority mini-datasets plus explicitly synthetic failure fixtures; roles/mentions/time-scoped identities and bill relations remain distinct |
| M4 | Pending | Build source-preserving lexical search view and boundary/token-aware retrieval export; prototype hybrid search with trusted metadata | Tests and source examples for split words, exact names/quotes/numbers, mixed turns, dates and combined filters; no silent truncation or cross-speaker false matches |
| M5 | Pending | Fresh reviewed end-to-end benchmark, selected vocabulary/authority releases and declared human acceptance standards | Correct evidence/metadata, relevant alternatives, negatives/abstentions, reviewer disagreements; separate raw/static, tags, lexical/vector/hybrid and answer findings |
| M6 | Pending | Package portable backend/data pilot and simple operator commands with realistic estimates | Another client can consume export/query contract; reproducible setup/build/resume; no local ignored dependency silently required; code gate and human review passed |
| M7 | Human decision; not authorized by plan | Human selects provider/configuration and explicitly launches full workload/indexing | Reviewable release plan, resource/cost/time estimates and resume controls; after run validate coverage, failures, release manifests and source citations |

Cross-cutting backlog: measured multiprocessing rollout after failure/equivalence checks; optional external metadata acquisition with preservation; model/dimension comparisons when a fresh evaluation can distinguish them. Do not let these replace the next research capability. Do not repeatedly tune on the five known topic cases and call it progress toward held-out quality.

### Next bounded experiment: M1

1. Read the existing `metadata-filters/span-selection/` frozen cases and reviews. Do not relaunch the failed long-ID configuration.
2. Prepare about five bounded source windows covering petition presentation, ordinary speech, a letter/quotation, an unnamed continuation and mixed turns. Explicit date evidence and date-negative cases must both appear. Reusing old cases is diagnostic; fresh cases need a declared split and exclusion check.
3. Use short request-local paragraph/cue aliases mapped by the host to immutable sources. Separate speaker-role and date tasks if one combined response is too dense. Require paragraph/span-local role evidence, date kind/scope and explicit unknowns; do not silently fix invented IDs.
4. Freeze source expectations before calls, label AI assessments honestly, validate offline failure fixtures, and record request/time/output limits before using installed Qwen and a matched small Mini sample. Existing bounded-testing authorization applies; this is not permission to drain any queue.
5. Independently review every response against full raw context, including false positives and omissions. Save a short source→proposal→review scorecard and actual time/cost. Human questions should concern concrete examples, not approval of unspecified future work.
6. Update M1/current status/evidence and select the next action from observed failures. If data or authority support is absent, retain unknown and report coverage; do not manufacture a passing result. Do not expand a plateauing POC into corpus work.

## 8. Operator commands and current limitations

Run commands from the repository root using `uv`. `UV_CACHE_DIR=/private/tmp/congressional-globe-uv-cache` is the known working local cache override when sandbox permissions require it. A clean clone does **not** contain ignored artifacts, source derivatives or local prototypes. Prepare/copy them deliberately before expecting old run IDs to work.

| Command | Current implemented behavior |
| --- | --- |
| `uv sync --all-groups` | Install project dependencies; use uv, not manually managed virtual environments |
| `make status` | Read the existing cleanup queue; this is not a research-enrichment status dashboard |
| `make run-static` / `make run-workflow` | Existing static-first cleanup/export path, no model requests; can refresh exports with saved accepted edits, so it is not a read-only inspection command |
| `make run-qwen` / `make run-gemma` / `make run-openai` | Existing cleanup worker only; up to 1 hour / 1,000 requests; explicit model operation, not a corpus tagging/search pipeline |
| `make v2-sample` | Offline subject exclusions/sample preparation; outputs already exist here, so **do not rerun** against those paths |
| `globe subject-review-template` / `globe subject-review-import` via `uv run` | Explicit offline human-label preparation/validation; exact sample/vocabulary binding, no provider requests |
| `make gate` | Formats and runs all required implementation checks/tests; can change formatting |

No installed one-command full enrichment/search pipeline exists yet. Do not present the cleanup Make targets as if they implement that deliverable.

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

### Current human-label work

Read `artifacts/v2-subject-review/review_packets.jsonl` alongside its frozen `vocabulary.json`; keep the packet unchanged. `artifacts/v2-subject-human-labels.jsonl` is already prepared and still pending. Do not regenerate it or fill it with AI labels called human judgments. Human fields need reviewer identity, timezone-bearing timestamp, decision/note and exact paragraph quotes/Unicode offsets. In-scope and OOV topics may coexist; no-subject/unknown decisions can retain evidenced incidental mentions. For completed human labels, create a new reviewed output:

```bash
uv run globe subject-review-import --sample artifacts/v2-subject-review \
  --reviews artifacts/v2-subject-human-labels.jsonl \
  --output artifacts/v2-subject-human-reviewed.jsonl
```

This is a future human action, not an instruction to import pending labels now. Import requires every window, verifies evidence/digests, refuses overwrite and keeps the original sample. It does not authenticate the author or establish historical truth. Older local HTML review packets can be inspected at `artifacts/v2-pivot-20261011/human-review/index.html`; their rendered UI was not independently verified. Current subject/model review JSON does not require a server or model calls.

## 9. Agent working rules and handoff discipline

1. Read this plan first. Check actual Git/files/run evidence; distinguish current status from historical snapshots. State which milestone and decision a proposed unit advances.
2. Use Luna delegates for bounded preparation, evaluation and documentation when available, as requested by the human. Delegate with clear file ownership; inspect their findings. Do not treat an AI reviewer as human gold. If a different harness cannot provide that model, disclose the limitation rather than silently inventing delegation.
3. Use uv, Pydantic v2 at external-data boundaries and streaming parsers for large OCR files. Keep cyclomatic complexity ≤5; refactor rather than add exceptions. Tests should cover core behavior/failure cases, not broad low-value suites.
4. Raw OCR/IA metadata immutable. Derived products belong under `artifacts/`; disposable scratch under `tmp/`, ignored except `.gitkeep`. Do not edit/clean/commit the separate agent's `tmp/performance/` work. Secrets remain in ignored environment configuration, never evidence or Git.
5. AI requests remain opt-in. The human authorized bounded Mini/Ollama POCs; a full-corpus model run, model download or recurring schedule is a separate action. Do not infer full-run approval from this plan or a continuation message.
6. Preserve source anchors and patch-based cleanup. Inspect existing SQLite/run state and live handles before workers. Keep Ollama sequential under the shared request lock; local API key placeholder is `ollama`. Do not restart solely because observation timed out; verify the same handle/process to terminal first.
7. For code changes run `make gate` before handoff. It applies Ruff and the required elevated `npx prettier@3.9.10 --prose-wrap never --write "**/*.md"`, then Ruff format/check, ty, `complexipy src tests --max-complexity-allowed 5`, and pytest. Markdown edits require that Prettier command with elevation for Codex; original archived snapshots are intentionally excluded from reformatting. Check `git diff --check` before commit.
8. After a unit, update **this document**: current status, milestone status, evidence/limits, exact run IDs/handles and next executable action. Record terminal state before reusing resources. Keep the current block current; do not append another conflicting “latest next steps” section. Add only a compact dated change entry.
9. Commit completed units with a single-line message and no agent attribution. Include authorized human changes deliberately; never sweep secrets or another agent's scratch files into Git.
10. A handoff reports what changed, evidence/checks, limits, active work and next action. Do not mark milestones complete on intentions, mock results, schema passes, credit exhaustion or a persuasive summary. The long-term goal remains incomplete until its stated release requirements are demonstrated.

## 10. Document consolidation and change log

This plan replaces the active planning/progress roles of `PROJECT_GOAL.md`, `PROGRESS.md`, `V2_PIVOT.md`, `V2_HANDOFF.md`, `RUNBOOK.md`, `HAPPY_PATH.md`, `V2_EMBEDDING_MODELS.md`, `V2_TAGGING_EVAL.md`, `V2_TAGGING_RETRY.md` and `TAG_ARM_PROMPT.md`. Those paths are compatibility pointers only. Do not add new work or contradictory instructions there.

Original documents, the prior README and prior agent instructions are preserved verbatim in `docs/archive/2026-10-22-pre-masterplan/`, with original-file hashes in `manifest.json`. Archived checklists, pending states and commands are historical evidence, not an active task queue. Relative links in snapshots reflect the former root locations. Important detailed reports/hashes live in the archive/artifacts; summaries here do not turn provisional evidence into verified history.

| Date | Change / evidence |
| --- | --- |
| 2026-10-22 | Consolidated the human's clarified backend/search/enrichment goals, long-running workflow requirements, current paired model findings and ordered M0–M7 execution plan. Preserved prior documents and made legacy paths pointers. No model requests or corpus processing in this consolidation unit. Two independent Luna audits found no material requirement/evidence omissions. All 12 original snapshots verified against recorded hashes; current Markdown file links/anchors checked; `make gate` passed 147 tests. Commit is recorded in Git; exact gate evidence is in the current status block. |
