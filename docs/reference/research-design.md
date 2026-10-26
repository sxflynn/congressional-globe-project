# Research design and data contracts

Read this only when your task needs it. [MASTER_PLAN.md](../../MASTER_PLAN.md) owns current tasks, ownership, progress and next actions; this file owns detailed reference material.

The master’s [stage sequence](../../MASTER_PLAN.md#milestone-progress), [acceptance checks](../../MASTER_PLAN.md#what-accepted-pilot-means) and [parent/subtask map](../../MASTER_PLAN.md#work-package-progress-inside-the-stages) connect these detailed requirements to executable work. This reference is not another task queue. Quality thresholds and scope limitations must be explicitly agreed through the existing human checkpoints; the roadmap does not invent them.

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
| Clean reading and audio access | Maintain a separately versioned, source-grounded clean reading transcription suitable for ordinary reading, copying/quotation and text-to-speech; show raw OCR and page image whenever a reading is uncertain or disputed |
| Future AI tools | Let a bot issue multiple filtered keyword/vector searches, inspect context and compose cited answers from returned evidence |
| Portable handoff | Documented data releases, schemas, indexes and query/tool contracts that another project can use to build the application |

Representative queries include Freedmen's Bureau debates; military affairs; Andrew Johnson's conflicts with Congress; a particular bill; speeches by a named member; and date-bounded research. More demanding examples include Republican senators from Ohio discussing Reconstruction in March 1866, Stevens's civil-rights arguments, and party differences over suffrage. These are acceptance scenarios, not claims that every required filter works today.

### Scope boundary

- **Deliver now through this plan:** source/data preparation, identity/provenance, search representations, token accounting, chunking, evidence-backed enrichment, embeddings/indexing, resumable processing, evaluations, and a documented backend/data handoff.
- **Defer:** polished web interface, production chat inference/application, and deployment/hosting product. A thin query API or tool adapter may demonstrate the handoff. MCP is an option, not a required dependency or a reason to build a UI now.
- **Current corpus:** one congressional session in five parts, not the entire historical Globe or a multi-decade collection. Design for extension without claiming that broader coverage exists.
- **Immediate human priority, revised 2026-10-24:** investigate whether a holistic, image-grounded cleanup workflow can produce a trustworthy clean reading layer for people, text-to-speech, search, RAG and evidence-backed tagging. The workflow will repeatedly process bounded inputs with a deliberately selected provider (local Qwen/Gemma/Muse or OpenAI API), preserving every input/output/scan anchor and measuring quality, throughput, cost and review burden. This is a higher-priority research question than finding supposedly unreadable scans. It does not yet authorize a corpus-wide run, a model download, or silent canonical-text replacement.
- **Do not expand into:** re-OCR or systematic visual verification of original images. Human access and accurate image links are required; an image-verification project is not.
- **OCR decision:** preserve the completed cleanup path and all outputs. The active hypothesis is no longer limited to whether raw OCR is adequate for search: a high-quality clean reading layer could independently serve human reading, copy/quotation, accessibility and text-to-speech, while also improving RAG and annotation. Investigate the value and full cost of broad cleanup fairly against raw/search-normalized alternatives. Neither “perfect cleanup first,” “raw OCR is enough,” nor “AI inference makes transcription quality irrelevant” is an established conclusion.

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
| Canonical releases | Source-based pages/paragraphs, immutable original OCR, separately versioned clean reading text, source anchors, correction history, schema/release identity |
| Authorities | Stable people, temporal service/affiliations, subjects, places, legislation, committees and organizations; cited external records where verified |
| Enrichments | Independently versioned speaker/date/boundary/entity/subject proposals, supporting evidence, method, uncertainty and review decisions |
| Search exports | Derived retrieval passages linked to ordered canonical spans, selected metadata releases, context relationships and source citations |
| Search indexes | Lexical representations, vectors and index structures; disposable products identified by their input/configuration manifests |
| Audits/reviews | Stage runs, attempts, raw replies, failures, validation, acceptance policies, human labels and supersession history |

Canonical and enrichment JSON/JSONL plus documented schemas remain usable without a particular embedding model, vector database, search framework or LLM. Provide ordinary database/full-text access as well as semantic adapters. Do not mix vectors from different embedding spaces in one index.

### Required metadata semantics

- **Dated roster lookup requirement (human clarification, 2026-10-22):** build evidence-backed seat occupancy/service intervals across the 39th Congress, including replacements and vacancies, to answer seat/date lookups such as Iowa district 2 or California senators. Current Wikipedia candidates do not yet supply verified intervals. Once established, roster lookup and linked authority fields are deterministic. OCR-to-person matching must use the roster/aliases and reliable context, retain ambiguous candidates or unknowns, and never create an identity from garbled OCR or guarantee a match from roster inclusion alone.
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

### Applied human calibration: HR-008-v1 (SF, 10/22/26)

Original questions, sources and exact answers are preserved in [the immutable answered packet](../../docs/archive/human-review/HR-008-v1/original.md); its hash and processing scope are in [the receipt](../../docs/archive/human-review/HR-008-v1/receipt.json). Human confirmed completion in chat. These are output-informed diagnostic judgments, not blind gold or a general accuracy estimate. No validated machine-label import or corpus retagging occurred in this documentation unit.

- **S1:** voting rights is an acceptable substantive tag (human grade B+). The human wants useful finer topics considered, including republican government, and tagging at an appropriate passage/speech scope. Explore scope notes and broader/narrower terms on a tiny sample; this does not automatically add a controlled term or assert a new verified tag.
- **S2:** Mini's military-affairs assignment is incorrect; Qwen's caution is preferred. Do not infer military meaning from “protection” and postwar context when the object is missing. The human reports the original reads “660 citizens … protection to American labor”; keep that human-reported reading separate from immutable OCR and any independently validated correction. Preserve petition identification for discovery, including testing OCR-damaged cue variants; the word petition alone does not establish the requested subject, author, or congressional endorsement. Targeted scan access is a technical exploration below.
- **S3:** public employee compensation is acceptable/substantive; congressional procedure is a passing mention **in this salary passage**. Routine procedural language is insufficient by itself for a substantive procedure tag. Preserve genuinely substantive procedural debates as a separate possibility; do not turn this sample into a blanket rule excluding procedure.
- **Cross-page speech context:** the human reports S3 starts mid-speech at a new page, with the speaker introduced at the prior page's bottom right. Include ordered previous-page context and available column/geometry evidence when evaluating attribution. Do not reset attribution at a page break or blindly carry a speaker past an intervening turn, chamber/date/proceeding boundary. Keep unknown where continuity cannot be established. This is now an explicit M1 POC case and required boundary behavior, not a claim the implementation already works.
- **Scope:** all requested S1–S3 grades and overall guidance are answered; optional demo fields were left blank and are not outstanding requests. P0, human acceptance thresholds and independent representative labels remain open. Reopen only for new evidence or a new concrete policy question.

### Applied human calibration: HR-005-v1 (Stephen, 10/24/2026)

The human explicitly confirmed **“Yes, the AI was correct, it is Mr. Wade, yes.”** and limited the explanation to this instance. [The complete answered packet](../../docs/archive/human-review/HR-005-v1/original.md) preserves the exact wording, context and date; [the processing receipt](../../docs/archive/human-review/HR-005-v1/receipt.json) links the normalized judgment to the frozen packet hash and P15/P16 source paragraphs on part5 leaf404.

For this reviewed reply and its following paragraph, the contextual Wade attribution is supported. This resolves the prior conservative AI review flag and supplies one human-confirmed example of useful speaker attribution on unchanged damaged OCR. Do not record it as a known historical error or ask the same question again. Keep both models' raw outputs and all original validation records; overlay this human adjudication rather than rewriting frozen source expectations or comparison reports.

Scope remains narrow: no blanket automatic spelling/name-repair policy, no canonical text correction or corpus export change, no verified biographical/service authority ID, no representative accuracy claim and no P0 decision. P0 still needs matched raw-versus-cleaned evidence and agreed criteria. Protocol v2/unknown-case engineering can proceed offline using saved replies; a later materially different role/date or name-resolution question gets a new review packet/version.

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

### Small POC loop

1. Name the specific question and the next decision it will change. Check saved evidence; do not rerun a spent experiment merely because a new agent starts.
2. Freeze a small sample, whole evidence windows, input hashes, task/prompt/schema, vocabulary/model configuration, maximum calls/runtime and success/failure criteria before requests. Start with about five substantive cases when suitable; expand only for a stated gap.
3. Include positive, negative, truncated, unknown and mixed cases across the five parts and relevant document types. Known diagnostic retries are useful but are never fresh held-out quality evidence.
4. Use independent source expectations/review, with exact text evidence. Keep human labels distinct from AI-provisional assessments. Tag the human at H2 for the first usable new-family calibration sample, and at H1/H3 before adopting semantic standards. Humans set acceptance standards before examining held-out scores; do not invent thresholds or silently skip the human checkpoint.
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

To decide whether cleanup earns its cost, compare paired raw and existing static/cleaned views with identical boundaries/settings. Separately test source-preserving search normalization and controlled enrichment. Evaluate not only retrieval/tagging but also clean-reading fidelity, quotation/copy usefulness and text-to-speech suitability. Include actual cleanup-plus-tagging/retrieval/reading-layer costs under a declared acceptance policy. Equal target ranks or similar tag counts do not establish that OCR never matters, that a clean reading layer lacks value, or that model calls can safely be skipped.

### Release decision

A passing code gate is necessary for shipped implementation, not sufficient for a research release. A release must demonstrate source traceability, the stated query/filter scenarios, unknown/mixed behavior, reviewed quality standards and coverage, reproducible builds/resume, and portable consumption by a separate client. Human approval of a concrete, reviewable pilot and its cost/time estimate precedes any full model/indexing launch. Do not claim complete unless these deliverables are actually demonstrated.

### P0: is a clean reading layer worth broad OCR cleanup?

**Unresolved, reprioritized and not settled by choosing a raw-first pilot.** Preserve the existing cleanup implementation, queue, ledgers and static snapshot. Earlier raw/static experiments compare original OCR with deterministic static edits, not perfect transcription or a fully AI-cleaned corpus. The human has directed that the value of a broad clean reading layer—usable by people and text-to-speech as well as RAG and historical annotation—now be investigated directly.

| Open question | Current signal | Missing decision evidence |
| --- | --- | --- |
| Can researchers find passages without broad cleanup? | Similar target ranks in small raw/static vector diagnostics; useful source-preserving lexical joining | Fresh relevance labels, exact names/quotes/numbers, split-word/ambiguous-compound failures, negative controls and trustworthy filters |
| Does dirty OCR increase enrichment workload or errors? | Raw/static cue sets matched in one diagnostic; revised raw-topic proposals useful | Reviewed speaker/date/entity/bill/topic assignments and omissions; actual safe rule acceptance versus model/review routing, not cue counts |
| Can answers faithfully use returned raw text? | Some correct answers despite damage; also missing qualifications and incorrect abstentions | Human-supported claims/citations, unanswerable cases and consistent retrieved context in paired comparisons |
| Can a cleaned layer support reliable human reading and text-to-speech? | Existing deterministic patches replay, and tiny image cases show source print can resolve damaged OCR; neither establishes readability/TTS quality at corpus scale | A source-grounded rubric for names, numbers, wording, sentence flow, punctuation and uncertainty; representative human review and audio-oriented error analysis across document types |
| Which workflow is worth many hours? | Tiny time/cost samples; resumable cleanup worker preserved | Total search-view/cleanup/enrichment/embedding/review/retry costs under a declared quality policy and representative throughput |

Compare frozen matched units: **A**, raw OCR plus source-preserving search normalization and enrichment; **B**, existing static text plus the same enrichment/retrieval; **C**, a separately versioned, image-grounded clean reading layer generated by a bounded repeated-LLM workflow. Match context, boundaries, queries, reading/TTS checks, labels and configuration when attributing an effect to cleanup. Arm C is now a priority investigation, not an automatically authorized corpus-wide workload.

Every relevant POC must state its P0 hypothesis/arm, sample/configuration hashes, outcome, limits and next decision. M1 initially tests whether the revised role/date contract works over raw text; it does not by itself isolate OCR effects. A later paired comparison must separate OCR problems from prompt, authority and boundary failures. Reuse compatible saved inputs/results instead of paying to repeat completed work.

The final P0 deliverable is an evidence-backed policy: retain raw OCR only within a demonstrated scope, apply deterministic/targeted fixes to defined failure classes, or justify a broad clean reading layer where reading/TTS/RAG/annotation gains outweigh total costs. The answer can differ by task/document condition. Do not force a binary conclusion, hide the decision in an incidental backlog item, or start full cleanup merely to research it. Vector hits, useful tags and passing code gates cannot close P0.

#### Finite investigation and stopping rule

1. **Plan before more benchmark calls:** draft P0-A and the coverage/budget/sample design for P0-B. This is offline planning, not a request to rerun old experiments. Do not invent numerical historical-quality thresholds or silently treat unapproved criteria as agreed. Human approval is needed for those standards, not for every reversible preparation task.
2. **Run one frozen primary comparison**, reusing compatible saved outputs only where their inputs, labels and configurations qualify. Bound calls/runtime and publish the experiment manifest before launch. Evaluate a bounded broad-clean-reading arm C as a repeated LLM workflow, not merely a few targeted corrections; preserve raw/static controls and separate clean reading from authoritative raw OCR.
3. **Run one fresh confirmation batch** for the proposed policy. Extra experiments require a named unresolved failure or uncertainty that could change the decision, explicit bounds and a stopping condition. Repeating a known saturated sample is not a substitute for confirmation.
4. **Enough information:** P0-A–P0-G have supporting evidence, results meet the predeclared standards, observed cleanup benefits/costs are attributable enough to choose, and no unresolved material uncertainty could plausibly reverse that choice within the declared scope. Show counts and uncertainty, including slices where the conclusion is weak. If uncertainty is still material, name it and do the smallest discriminating follow-up; do not declare victory or start an open-ended benchmark program.
5. **Record the human decision:** mark P0 decided only after the human reviews the packet and selects the policy. Record the scope, evidence/criteria versions, exceptions, rationale and reopening conditions. Any omitted capability/slice needs an explicit human-approved scope limitation; do not silently waive a required readiness item. Narrow provisional recommendations remain provisional rather than closing the whole P0 question.

The result may be task-specific: raw text for broad discovery, source-preserving normalization for broken words, targeted repair for demonstrated name/number failures, or a broadly cleaned reading layer for accessibility and scholarly reading. **P0 readiness is separate from production readiness:** small evaluated prototypes can establish the cleanup policy before all M2–M6 production features ship. Conversely, a P0 decision never authorizes M7/full-corpus processing or certifies the historical metadata.

For each P0-related POC, its result must name which readiness item it advances, the evidence path and whether that item remains missing/partial or becomes ready. Add no alternative P0 checklist elsewhere. Before a new run, state which plausible outcome would change the policy; if neither outcome changes a decision or closes a necessary gap, do not run it.

#### Holistic cleanup investigation requirements (new highest-priority P0 planning unit)

Design the investigation around a repeated, resumable LLM workflow rather than an interactive Codex conversation. Each bounded work item must bind its raw OCR, whole enough text context, source/page identity, optional exact image crop, prompt/schema/model configuration and policy version. It must persist its raw provider reply, proposed clean reading text or abstention, validation/review outcome, usage/time/cost, and a resume-safe terminal state. A later full workflow may use a local vision-capable model, an OpenAI API model, or both in a declared comparison; provider choice follows measured quality, throughput, cost and failure behavior, not a model-name preference.

The first scorecard must define, before a provider request:

1. What is being measured: literal transcription fidelity against source images; preservation of names, numbers, historical wording and uncertainty; readability/copy/quotation; text-to-speech sentence flow and harmful spoken errors; retrieval/RAG; and speaker/date/topic/bill tagging effects.
2. Which representative strata are included: all five parts, proceedings and index-like material, clean controls, ordinary damaged OCR, names/numbers, line wraps, punctuation, long passages and cases where the image/context does not support a safe reading.
3. How image access is routed: source geometry/crops only where needed by the declared policy, never a bulk image archive or a substitute for source provenance; missing/irrelevant evidence must produce an explicit unknown/review state.
4. Which workflow designs/providers are comparable: identical frozen packet and limits, exact model/provider/runtime fingerprints, sequential local requests, no hidden retries, and separate cost accounting for local runtime, paid APIs, image retrieval and human review.
5. What durable engineering evidence is required: input/config/code hashes, item-level events and attempts, interruption/ambiguous-outcome handling, compatible cache reuse, validation errors, provider output limits, and measured throughput suitable for cautious full-run projection.
6. What does not follow from the POC: no automatic canonical rewrite, no claim of historical verification, no final provider winner from a tiny sample, and no authorization to start a corpus-wide job without a concrete H4/H6 review.
