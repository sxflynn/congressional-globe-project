# Congressional Globe master plan

Updated: 2026-10-23. **This is the single authoritative project plan and progress record.**

Every engineering agent must read this document before working, use its ordered milestones, and update its current status and next action before handing off. New instructions from the human take precedence. `AGENTS.md` is the entry point; `README.md` is a short operator tutorial; [HUMAN_REVIEW.md](HUMAN_REVIEW.md) is the human-facing request/response desk. The master owns goals/status/accepted policy; the review desk preserves original human answers and readable evidence. Neither companion maintains a competing roadmap. Earlier planning files now point here; their original contents are preserved in the [historical archive](docs/archive/2026-10-22-pre-masterplan/README.md).

Navigation: [Goal and scope](#1-goal-and-division-of-responsibility) · [Data/search architecture](#3-data-and-retrieval-architecture) · [Resumable workload](#4-long-running-workload-contract) · [Evaluation](#5-evaluation-and-decision-rules) · [Current progress](#6-current-progress-and-evidence) · [Ordered checklist and next POC](#7-ordered-master-execution-checklist) · [Operator commands](#8-operator-commands-and-current-limitations) · [Agent rules](#9-agent-working-rules-and-handoff-discipline).

**Stateless agents start with [the startup/recovery procedure](#stateless-startup-and-mid-flight-recovery), then [the live work record](#live-work-record--update-before-launch-and-at-each-checkpoint).** Codex, OpenCode and other harnesses share the same plan, work ownership and durable evidence; chat history, model memory and access to the original harness are not prerequisites. **P0, whether further OCR cleanup earns its cost, remains an open research decision.**

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

Original questions, sources and exact answers are preserved in [the immutable answered packet](docs/archive/human-review/HR-008-v1/original.md); its hash and processing scope are in [the receipt](docs/archive/human-review/HR-008-v1/receipt.json). Human confirmed completion in chat. These are output-informed diagnostic judgments, not blind gold or a general accuracy estimate. No validated machine-label import or corpus retagging occurred in this documentation unit.

- **S1:** voting rights is an acceptable substantive tag (human grade B+). The human wants useful finer topics considered, including republican government, and tagging at an appropriate passage/speech scope. Explore scope notes and broader/narrower terms on a tiny sample; this does not automatically add a controlled term or assert a new verified tag.
- **S2:** Mini's military-affairs assignment is incorrect; Qwen's caution is preferred. Do not infer military meaning from “protection” and postwar context when the object is missing. The human reports the original reads “660 citizens … protection to American labor”; keep that human-reported reading separate from immutable OCR and any independently validated correction. Preserve petition identification for discovery, including testing OCR-damaged cue variants; the word petition alone does not establish the requested subject, author, or congressional endorsement. Targeted scan access is a technical exploration below.
- **S3:** public employee compensation is acceptable/substantive; congressional procedure is a passing mention **in this salary passage**. Routine procedural language is insufficient by itself for a substantive procedure tag. Preserve genuinely substantive procedural debates as a separate possibility; do not turn this sample into a blanket rule excluding procedure.
- **Cross-page speech context:** the human reports S3 starts mid-speech at a new page, with the speaker introduced at the prior page's bottom right. Include ordered previous-page context and available column/geometry evidence when evaluating attribution. Do not reset attribution at a page break or blindly carry a speaker past an intervening turn, chamber/date/proceeding boundary. Keep unknown where continuity cannot be established. This is now an explicit M1 POC case and required boundary behavior, not a claim the implementation already works.
- **Scope:** all requested S1–S3 grades and overall guidance are answered; optional demo fields were left blank and are not outstanding requests. P0, human acceptance thresholds and independent representative labels remain open. Reopen only for new evidence or a new concrete policy question.

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

### Human checkpoints — when agents must involve the human

**Agents must explicitly tag/notify the human when a checkpoint below is reached.** Prepare the concrete evidence or grading packet first; a document saying “human review pending” is not itself a request. Human preferences, semantic standards, judgments and consequential launch decisions must not be silently supplied by an agent. Prior authorization and answered decisions persist within their recorded scope; do not ask again merely because a new harness starts.

| Gate | When the human is needed | What the agent brings / asks | What waits, and what may continue |
| --- | --- | --- | --- |
| H1 — Research standards | Before fresh benchmark scoring or declaring results acceptable; when a material scope/quality tradeoff changes | Proposed tasks/coverage, example correct and incorrect outcomes, acceptable misses/false assignments/unknown coverage, citation expectations, time/API/human-review tradeoffs and a recommendation. Ask for explicit agreement or corrections | Acceptance-based scoring/claims wait for agreed criteria. Offline fixtures, sample preparation and authorized diagnostic POCs may continue, clearly provisional |
| H2 — Human grading/calibration | First usable small sample for a new tag/role/date/filter/answer family; before treating labels as human gold; when a consequential disagreement is unresolved | A small readable source packet and rubric as below. Ask the human to label or grade concrete examples, including negatives and ambiguity; preserve their actual judgments | Human-quality calibration, gold labels and safe automatic-accept claims wait. Agents can inspect evidence, fix mechanical failures or prepare independent tasks; AI review stays provisional |
| H3 — Historical meaning and policy | A scope rule materially changes outcomes: subject meaning, petition vs debate, speaker/presenter/mentioned person, date precision/propagation, identity-link evidence, mixed/unknown/OOV handling | Two or three actual contrasting examples, proposed rule, alternatives and effect on filters/coverage. Ask which rule matches the research intent | Adoption as the trusted policy waits. Draft vocabularies, alternatives and experiments can continue with proposed status; do not request approval for each routine alias or label within an already agreed rule |
| H4 — Spending/resources/authorization | A proposed action exceeds existing bounded POC permission or approved cost/runtime/model scope; requires a model download; needs unavailable credentials/resources; or changes an approved full-run budget | Exact command/configuration, bounds, cost/time basis and uncertainty, resources, resume/stop plan and reason. For credentials request private setup, never a secret in chat | The dependent unauthorized/inaccessible action waits. Already authorized small Mini/Ollama calls do not need repeated approval; reversible preparation and unrelated authorized work continue |
| H5 — P0 decision | P0-A–P0-G produce a reviewable decision packet, or a previously accepted conclusion needs reopening | Matched evidence, costs/quality by task, uncertain slices, skip/selective/broad recommendation, exceptions and reopening conditions. Ask the human to choose policy/scope | Closing P0 or changing its accepted policy waits. Do not interpret that choice as permission for full processing |
| H6 — Pilot/release/full execution | Before adopting the pilot as an accepted handoff, choosing/launching M7 full processing, or accepting the resulting research release | Concrete pilot/demo, data/model/config versions, sample quality/coverage, known limits, operator commands, total estimate and recovery proof; after the run, coverage/failure/review/release report | Acceptance, full launch, material budget expansion and release designation wait for explicit human decision. Building/reviewing the concrete pilot or release candidate is authorized engineering work; do that before asking |

If a model returns a plausible but unsupported name/date/bill assignment, reject/hold it rather than ask the human to bless a guess. Escalate a representative cluster or policy ambiguity when it affects the research standard; do not make the human adjudicate every production row. Reuse approved guidance, sample periodically, and measure remaining review workload. If the human is unsure, retain uncertainty and seek additional evidence; a forced yes/no is not a historical fact.

#### How to ask for sample grades

1. Freeze IDs, raw text/context, citations, vocabulary/rubric and sample version. Start calibration with a few readable examples (typically 3–5 when suitable): a clear positive, a negative/incidental mention, an ambiguous/truncated/mixed case, and a model disagreement or failure. This calibrates expectations; it is not sufficient evidence of corpus accuracy. Fresh benchmark selection still needs the declared coverage/exclusions.
2. For **blind expectations**, let the human label the source before seeing model outputs, scores or which arm produced them. Ask what is relevant, who speaks versus is mentioned, what date/subject/bill is evidenced, or whether the question is answerable. Permit unknown, OOV, mixed and “need more context.” For **diagnostic output grading**, then show source → proposal → exact cited evidence and ask acceptable/incorrect/unclear, with the reason and severity. Do not call output-informed grades blind gold.
3. Ask a focused research question rather than requiring JSON editing: for example, “Is procedure a substantive subject here or just salary-debate context?” Provide source links/page references and enough surrounding text. Page-image access is available for the human, but this does not create a systematic visual re-OCR requirement. Bundle related decisions and estimate the review effort.
4. Preserve the human's actual answers, reviewer/time, packet/configuration versions and evidence IDs; link them in the register. A host may translate those answers to the existing validated import format, preserving the original response. Never fabricate a human identity, fill missing judgments with AI agreement, or convert an agent's source expectations into human labels.
5. Record disagreements and any adjudication. If only one human grader is available, state that limitation; a second AI reviewer is not a second human. Rule changes after seeing results require versioned criteria and fresh evaluation before claiming generalization.
6. Apply approved guidance to the next bounded sample and show whether it resolves the human's concerns. Ask again only for a genuinely new unresolved decision, changed scope/evidence, or the next scheduled calibration gate—not merely for another model call.

#### Human-facing review desk

**`HUMAN_REVIEW.md` is the single place for agents to present decisions, sample packets, demos and explicit response areas to the human.** This is an intentional companion to the master plan, not another project plan or status backlog. Use the same HR IDs/versions as the register below. The human writes plain-language responses there or in chat; agents preserve original answers, then update the master's accepted-policy/status summary and any validated review artifacts.

At the start of a session and before choosing the next work unit, read relevant review-desk responses and compare them with the HR register and last applied follow-up. New human answers may change what is blocked or which policy applies. On the same prepared machine, “continue working” includes checking this desk. On another machine, copy/commit the tracked desk as well as the master plan; ignored source evidence remains a separate dependency.

Agents must:

- Populate a concrete item before requesting a response: ID/version, plain-language question, source/context/citations, recommendation/options, review effort, what waits/continues and any spending/runtime limits. Demos must state read-only versus model-calling behavior and expected/observed results. Keep the active queue small and actionable.
- Leave **Your response** fields blank or clearly placeholder text. Never preselect an approval, write a human grade, or count the agent's recommendation/template as an answer. Do not ask the human to edit JSON. If the human answers in chat, copy the actual answer only with its origin/date and preserve unresolved items; do not invent timestamps or identity.
- Notify the human that the specific item is ready, then record delivery and `awaiting_human` in the master register. Merely drafting a future item is `not_requested`. Do not resend pending requests because the harness changed; use existing scope/authorization.
- Preserve human edits and prior answers. When the human confirms a review set is finished, archive its exact bytes under `docs/archive/human-review/<HR-ID-version>/original.md` before editing the desk; record its SHA-256, original path, packet IDs, supplied reviewer/date and processing scope in a receipt. Incorporate all answers/conditions/backlog into this plan, verify preservation, then replace the completed set on the desk with a concise linked receipt. Keep unanswered required items active; optional blank demo feedback does not block closure. Never replace original answers with a summary. Material question changes require a new version; if authorship/intent is ambiguous, clarify before the dependent action. Format and commit the processed unit.
- Apply answers narrowly: three sample grades do not approve a provider budget, a full run, P0 closure or corpus-wide quality. Record answered/applied status, exact scope, remaining uncertainty, evidence links and reopening conditions in the master plan. A partially answered packet stays partially unresolved. Sync the desk's follow-up and master register in the same unit; a stale summary must not override an actual human response.
- Freeze blind labels in a separate clearly identified source-only packet before showing the same cases' model outputs or scores. The current HR-008 desk examples are output-informed diagnostics, not the blind HR-004 sample. Do not expose held-out model outputs in a blind request or treat demo feedback as gold labels.

The request/answer record is part of every cross-harness handoff. Large machine evidence can stay in `artifacts/`; inline enough exact source context for the human to understand the ask without running a model or opening raw JSON. Completed interactions remain readable; the canonical request lifecycle and accepted project policy live in the master register.

#### Request/decision protocol shared by every harness

Every human request has an ID in the register below, a concrete section in `HUMAN_REVIEW.md`, and a linked work unit/readiness item. Before sending it, record the concrete packet, recommendation/options, impact, exact question, blocking dependent actions and independent work that can proceed. Then notify the human through the current chat/harness; do not contact other people or create a schedule without authorization.

Use states `not_requested` (still preparing), `awaiting_human` (actually sent), `answered`, `applied`, `deferred`, or `superseded`. Record the send time/channel/reference and the actual answer/evidence/version/scope/reopening condition when available. Silence, elapsed time, an unread request, a default option or AI consensus is not an answer. On handoff, pending requests stay pending; the replacement agent checks their status rather than sending duplicates. An answer in chat must be persisted into this plan and the evidence before applying it as a durable policy for future agents.

Pause only dependent decisions/actions. Continue useful independent work under existing authorization. Do not mark the whole project blocked while an offline safe action remains. A proposed rubric can support exploratory diagnostics if clearly unapproved; it cannot certify success or close a human gate.

### Human request and decision register — update in place

| ID / gate | State | Decision or packet / current action | Dependency and continuation |
| --- | --- | --- | --- |
| HR-001 / H3 | **Applied** | Human explicitly chose “Count explicit petition requests as substantive topics.” Recorded in the topic POC prompt/configuration and this plan's metadata rules | Scope: substantive topic, not endorsement, attribution or factual verification. Reuse this decision; reopen only if a new substantive boundary issue arises |
| HR-002 / H4 | **Applied (access resolved)** | Human privately replaced the expired Mini key; `topic-mini-20261022-02` succeeded. Historical failures remain recorded; no secret stored here | No current credential request. Reask only if actual access fails; do not repeatedly request authorization for the already approved small Mini/Ollama sampling scope |
| HR-003 / H1,H3; P0-A | **Not requested** | Agent must prepare a concrete acceptance/coverage/cost scorecard with contrasting examples, then ask for agreement. Criteria are not yet human-approved | Needed before fresh acceptance-based benchmark claims; M1 offline preparation and authorized diagnostics can continue |
| HR-004 / H2; P0-B | **Not requested** | Ten-window source packet exists at `artifacts/v2-subject-review/`, labels pending. Prepare a concise readable grading invitation/rubric; do not claim a grading request has been sent or gold labels obtained | Needed for human subject expectations; keep packet blind and preserve incomplete-exclusion/coverage limits. Can prepare a small calibration presentation before broader grading |
| HR-005 / H2,H3; M1 | **Not requested (future checkpoint)** | After the first usable bounded role/date outputs, prepare source-linked examples and unresolved role/date-scope questions for human grading | Do not infer calibrated speaker/date quality from AI review. Can build and run authorized diagnostic machinery before this checkpoint |
| HR-006 / H5; P0-G | **Not requested (not ready)** | Prepare the P0 decision packet only after readiness evidence; human has not selected final cleanup policy | P0 stays open; no full-run approval implied by a later decision |
| HR-008 / H2; existing subject POC | **Answered and applied to plan** | SF, 10/22/26; human confirmed completion in chat. [Exact answered packet](docs/archive/human-review/HR-008-v1/original.md) and [hash/processing receipt](docs/archive/human-review/HR-008-v1/receipt.json). S1 voting rights acceptable/B+; S2 military inference rejected and caution preferred; S3 compensation acceptable, procedure passing mention | Diagnostic calibration only. Finer topics, targeted image fallback and cross-page speaker context enter the next POCs/backlog; no model run, validated label import, full budget or P0 closure implied |
| HR-007 / H6; M6,M7 | **Not requested (not ready)** | Concrete pilot/release/full-run choice, provider/configuration, total estimate and recovery proof remain to be prepared | No corpus-wide launch or accepted research release approved; continue building the reviewable pilot |

**Current human-involvement state:** HR-008-v1 is fully answered and incorporated; original wording is archived and the active desk is cleared. Nothing currently awaits a human response. HR-003 standards, HR-004 blind grading and HR-005 speaker/date calibration still require concrete future packets. Do not repeat the completed questions. These three output-informed judgments do not establish corpus-wide accuracy, blind gold labels or a P0 decision.

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

To decide whether cleanup earns its cost, compare paired raw and existing static views with identical boundaries/settings. Separately test source-preserving search normalization and controlled enrichment. Include actual cleanup-plus-tagging/retrieval costs under a declared acceptance policy. Equal target ranks or similar tag counts do not establish that OCR never matters or that model calls can safely be skipped.

### Release decision

A passing code gate is necessary for shipped implementation, not sufficient for a research release. A release must demonstrate source traceability, the stated query/filter scenarios, unknown/mixed behavior, reviewed quality standards and coverage, reproducible builds/resume, and portable consumption by a separate client. Human approval of a concrete, reviewable pilot and its cost/time estimate precedes any full model/indexing launch. Do not claim complete unless these deliverables are actually demonstrated.

## 6. Current progress and evidence

### Current status — update this block in place

- **Active direction:** reviewed raw-text retrieval/enrichment pilot; retain optional cleanup for demonstrated failures. **P0 remains open:** no final decision to skip, selectively apply or broadly apply additional OCR cleanup.
- **Current milestone:** M1 offline role-only retry preparation complete: five predecessor cases plus one real cross-page case frozen with short aliases and AI-provisional expectations. No new role/date model calls. Next implement the bounded audited runner; date task and roster identity linking remain separate. The M3 Wikipedia candidate bundle remains available.
- **Human checkpoints:** HR-008-v1 answered/applied, original packet archived; no active unanswered request. Next POCs must honor accepted sample judgments, cross-page speaker evidence and requested granularity/image-fallback explorations. HR-003/004/005 remain future concrete checkpoints, not human blockers.
- **P0 decision readiness:** 0 of 7 required readiness items are fully satisfied; several have diagnostic evidence only. Track P0-A–P0-G below. Next P0 planning action is to draft the acceptance/coverage/cost scorecard for human agreement before a fresh benchmark; M1 diagnostic engineering may proceed in parallel.
- **Current code:** extraction, cleanup/export, embedding boundary, subject contracts/matcher/sampler and explicit human-label import are tracked. Production research search/enrichment workflow is not complete.
- **Latest project gate:** M1 role-alias preparation: `make gate` passed 164 tests, Ruff, ty, complexity ≤5 and Markdown formatting. Log `artifacts/role-alias-preparation-20261023-02/gate.log`; final commit is recorded in Git.
- **Active processes:** at 2026-10-22 23:51:03 UTC, queue inspection and a scan for known project worker commands found no matching workers (inspection shell/search processes excluded). Recorded POC handles are terminal. This is a timestamped observation, not proof that no unrelated external client can use Ollama. Reinspect before requests; a lock/status file alone proves neither liveness nor termination.
- **Queue last observed:** `static-final-20261011`, 1,339 completed / 423 review / 20,785 pending / 0 claimed. These are cleanup task states, not corpus accuracy.
- **Canonical snapshot:** 5,412 pages / 296,995 paragraphs / 19,803 page-bounded chunks. Its verified static export is older than subsequent SQLite AI results; do not describe it as refreshed from the live queue.
- **Human review:** ten raw windows / 92 paragraphs frozen, two windows per part, labels pending. Part-only sampling, length eligibility bias and incomplete historical exclusions mean diagnostic preparation, not established held-out gold.
- **Credentials:** Mini succeeded after the human replaced the expired `.env` key; no current credential blocker. Never copy the key into a document, log or chat.
- **Limits:** no full-corpus model enrichment or corpus-wide embedding job is authorized by this plan. The earlier specifically authorized one-hour cleanup worker completed; its authorization is not an instruction to drain the queue now. Historical two-hour scheduled POC permission does not authorize new recurring work.

### Live work record — update before launch and at each checkpoint

This is the shared handoff for every harness. Keep one record per active unit, including offline implementation and delegated file ownership. On completion move only the compact result into the evidence ledger, leaving a clear next unit here.

| Field | Current value |
| --- | --- |
| Work unit / research question | Completed M1 offline short-alias role preparation; next bounded unit is an audited role-only runner |
| Owner / harness / owned files | Codex root: role_preparation.py and current state; Luna m1_alias_contract: role_aliases.py and focused tests; Luna m1_context_audit: read-only source/context review. No model worker launched |
| State / last verification | Completed 2026-10-23: six prepared cases, reversible aliases, independent source review, source/code hashes verified; no provider calls |
| Run IDs / host / OS process identity | None; no new M1 retry launched. Existing known workers are terminal |
| Exact command / cwd / limits / configuration | Offline preparation command below; six diagnostic role-only packets, 56,813 provider-input bytes, zero calls. No audited model-launch command exists yet |
| Inputs / evidence | Five frozen predecessor windows plus part5 leaf403 last8 paragraphs / leaf404 first8; original and short packets plus source anchors in artifacts/role-alias-preparation-20261023-02 |
| Completed / remaining / failures | Offline preparation and source expectations complete; no model quality result. Runner, retries/resume proof, date task, dated roster linking, targeted-image fallback and finer vocabulary evaluation remain |
| Durable results / logs / task store | Tracked artifacts/role-alias-preparation-20261023-02/{manifest.json,provider-inputs.jsonl,frozen-inputs.jsonl,alias-maps.json,source-review.json,output.schema.json,prompt.txt,checks.json,gate.log}; no model task store yet; cleanup SQLite unchanged |
| Locks | Shared Ollama request lock: `congressional-globe-ollama-request.lock` in the OS temporary directory; inspect actual lock/process state, not file presence |
| Human requests / blocking scope | None currently awaiting response. HR-008 answered/applied; HR-003/004/005 future packets not requested. Sample feedback is not full-run/P0 approval |
| Safe next action / resume instruction | Verify prepared file hashes and source-review/checks, then implement an audited role-only runner for these six packets: frozen expectations, terminal process evidence, sequential Ollama, strict short-ID validation, usage/time/cost and raw failures. Inspect workers/queue before any provider request. Do not invoke old failed long-ID runner |
| Decision/stop condition | Inspect every tiny-batch role/date result, preserve unknowns/failures, record quality/time/cost and effect on P0; no full processing |

**Before each launch**, record unique run ID, exact argv/cwd, host, selected limits, input/prompt/schema/code/non-secret configuration fingerprints, durable output/store paths and stdout/event logs. Write `launch_intent` first; immediately after launch record **OS PID plus process start time/full command** and UTC observation. A harness terminal/session ID is secondary, never the only recovery handle. Never fingerprint or copy secrets.

Checkpoint completed/remaining/review/failed/cached counts, last persisted result, unresolved attempts and the exact safe next inspection/resume action as work happens. Record verified exit/termination evidence before marking terminal. If abruptly killed, the replacement agent reconstructs state from OS/store/events, preserving unknown outcomes and prior usage. A planned handoff must not leave these facts only in chat.

This is a mandatory coordination protocol, not an already implemented distributed scheduler. M2 must implement/test durable recovery across harnesses. Some current one-shot prototypes refuse existing directories and cannot resume partial runs automatically; documentation must not pretend otherwise.

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

| ID | Status | Work and dependency | Completion evidence / exit condition | Human checkpoint |
| --- | --- | --- | --- | --- |
| P0 | **Open research decision, in flight** | Determine whether additional OCR cleanup earns its cost across search, enrichment and answers; runs through M1–M6 | Reviewed paired evidence supports an explicit skip/selective/broad-cleanup policy with total time/cost and limits; human decides before M7 | H1/H2 establish standards/labels; H5 human selects cleanup policy; P0 choice does not authorize M7 |
| M0 | Foundation complete; preserve | Maintain immutable sources and verified canonical baseline; inspect old evidence | Saved hashes/ledgers and source coverage; known snapshot/queue distinction retained | Autonomous preservation/inspection; notify the human of an unexpected material source-integrity failure |
| M1 | **In progress: offline role packets ready** | Six-case short-alias role inputs and source expectations complete; audited runner, model comparison and separate date task pending | Per-case roles and scoped dates/unknowns, exact evidence, raw outputs/errors, time/cost; explain residual failures; diagnostic≠gold | H2/H3, HR-005: show first usable role/date sample and unresolved meaning/scope questions |
| M2 | Pending; offline work can overlap M1 | Prove a minimal durable enrichment slice through prepare→run→inspect→resume→review→export; generalize existing cleanup machinery only where needed | Forced interruption and partial failure recover; compatible results reused; version changes deliberate; auditable attempts/progress; no source mutation | Technical recovery tests are autonomous; H4 for resources beyond permission; present recovery evidence at H6 |
| M3 | Partial: Wikipedia candidates extracted; verified authority linking pending | Bounded people/place/legislation authority linking and topic hierarchy/coverage examples; use M1/M2 evidence | Real cited authority mini-datasets plus explicitly synthetic failure fixtures; roles/mentions/time-scoped identities and bill relations remain distinct | H3 for material authority/vocabulary policy; H2 for representative entity/legislation samples |
| M4 | Pending | Build source-preserving lexical search view and boundary/token-aware retrieval export; prototype hybrid search with trusted metadata | Tests and source examples for split words, exact names/quotes/numbers, mixed turns, dates and combined filters; no silent truncation or cross-speaker false matches | H1 standards and H2 relevance/filter examples; do not silently define acceptable false matches |
| M5 | Pending | Fresh reviewed end-to-end benchmark, selected vocabulary/authority releases and declared human acceptance standards | Correct evidence/metadata, relevant alternatives, negatives/abstentions, reviewer disagreements; separate raw/static, tags, lexical/vector/hybrid and answer findings | H1 criteria agreed before scores; H2 human blind labels/adjudication; preserve grader limits |
| M6 | Pending | Package portable backend/data pilot and simple operator commands with realistic estimates | Another client can consume export/query contract; reproducible setup/build/resume; no local ignored dependency silently required; code gate and human review passed | H6 acceptance of the concrete pilot/handoff and explicit limits; prepare it before asking |
| M7 | Human decision; not authorized by plan | Human selects provider/configuration and explicitly launches full workload/indexing | Reviewable release plan, resource/cost/time estimates and resume controls; after run validate coverage, failures, release manifests and source citations | H4/H6 explicit provider/configuration/budget/full launch, then human release acceptance |

Cross-cutting backlog: measured multiprocessing rollout after failure/equivalence checks; optional external metadata acquisition with preservation; model/dimension comparisons when a fresh evaluation can distinguish them. Do not let these replace the next research capability. Do not repeatedly tune on the five known topic cases and call it progress toward held-out quality.

### P0: is further OCR cleanup worth it?

**Unresolved, not abandoned and not settled by choosing a raw-first pilot.** Preserve the existing cleanup implementation, queue, ledgers and static snapshot. Earlier raw/static experiments compare original OCR with deterministic static edits, not perfect transcription or a fully AI-cleaned corpus.

| Open question | Current signal | Missing decision evidence |
| --- | --- | --- |
| Can researchers find passages without broad cleanup? | Similar target ranks in small raw/static vector diagnostics; useful source-preserving lexical joining | Fresh relevance labels, exact names/quotes/numbers, split-word/ambiguous-compound failures, negative controls and trustworthy filters |
| Does dirty OCR increase enrichment workload or errors? | Raw/static cue sets matched in one diagnostic; revised raw-topic proposals useful | Reviewed speaker/date/entity/bill/topic assignments and omissions; actual safe rule acceptance versus model/review routing, not cue counts |
| Can answers faithfully use returned raw text? | Some correct answers despite damage; also missing qualifications and incorrect abstentions | Human-supported claims/citations, unanswerable cases and consistent retrieved context in paired comparisons |
| Which workflow is worth many hours? | Tiny time/cost samples; resumable cleanup worker preserved | Total search-view/cleanup/enrichment/embedding/review/retry costs under a declared quality policy and representative throughput |

Compare frozen matched units: **A**, raw OCR plus source-preserving search normalization and enrichment; **B**, existing static text plus the same enrichment/retrieval; **C**, only when needed and explicitly bounded, targeted AI corrections for demonstrated failures. Match context, boundaries, queries, labels and configuration when attributing an effect to OCR. A broad AI-cleanup arm is not automatically authorized.

Every relevant POC must state its P0 hypothesis/arm, sample/configuration hashes, outcome, limits and next decision. M1 initially tests whether the revised role/date contract works over raw text; it does not by itself isolate OCR effects. A later paired comparison must separate OCR problems from prompt, authority and boundary failures. Reuse compatible saved inputs/results instead of paying to repeat completed work.

The final P0 deliverable is an evidence-backed policy: skip further cleanup within a demonstrated scope, apply deterministic/targeted fixes to defined failure classes, or justify broader cleanup where gains outweigh total costs. The answer can differ by task/document condition. Do not force a binary conclusion, hide the decision in an incidental backlog item, or start full cleanup merely to research it. Vector hits, useful tags and passing code gates cannot close P0.

### P0 decision-readiness tracker

**Current assessment: not ready for a final P0 decision. 0 of 7 required items fully satisfied.** This counts satisfied evidence requirements, not project percent complete. Existing POCs are useful partial evidence; they cannot be promoted to reviewed acceptance results. Update this table after every P0-related unit, with the exact artifact/run, observed result, remaining gap and next action. Keep the current-status summary synchronized.

| ID | Readiness requirement | Current status and evidence | What makes it ready / next action |
| --- | --- | --- | --- |
| P0-A | Agreed decision criteria and scope | **Missing.** Goals and evaluation categories exist; numerical tolerances and cost tradeoffs have not been agreed | At H1/H3 (HR-003), draft a scorecard defining required tasks/slices; acceptable misses, unsupported assignments/claims, unknown coverage and citation failures; minimum useful improvement and acceptable extra time/API/human-review cost. Human agrees these criteria before seeing the fresh comparison. Record version/date and decision scope |
| P0-B | Frozen benchmark and human expectations | **Prepared only; not ready.** Ten blind subject windows exist, but labels are pending, exclusions incomplete and document-type coverage not established | At H2 (HR-004 and subsequent grading packets), obtain human expectations for a manageable frozen benchmark covering all five parts and relevant document conditions: exact names/quotes/numbers, split words, date/legislation/speaker filters, substantive/incidental subjects, mixed/truncated text and unanswerable cases. Include relevant alternative passages, human labels and disagreements. Record hashes/splits/exclusions; do not call diagnostic cases held-out |
| P0-C | Paired search/retrieval evidence | **Diagnostic only.** Tier-2 target ranks and saturated raw/static comparisons exist; reliable relevance/filter labels do not | Run matched raw/search-view and static arms on the frozen benchmark with identical query/context/boundary settings. Report relevant/missed/false matches and filter coverage per task/slice against P0-A criteria. Explain when gains actually result from OCR repair |
| P0-D | Paired enrichment and workload evidence | **Diagnostic only.** Cue-set comparisons and revised raw-topic Mini/Qwen outputs exist. Reviewed speaker/date/entity/bill comparisons and safe routing rates are absent | Evaluate supported/unsupported/missed/unknown tags and attribution for matched inputs. Distinguish OCR causes from prompt, authority and boundary failures. Measure defensible deterministic acceptance, actual residual model calls and review work; candidate hits alone do not count as savings |
| P0-E | Paired grounded-answer evidence | **Diagnostic only.** Prior answer packets have mixed AI-provisional findings; no agreed human-supported benchmark | With matched retrieved context, review answer claims, attribution, qualifiers, numbers, citations and abstentions under P0-A. Separate retrieval failures from generation failures. If cleanup does not fix a failure, do not credit it |
| P0-F | Total cost/time comparison | **Partial measurements only.** Small provider timings/usage and a snapshot embedding projection exist; end-to-end quality-policy costs are missing | Report extraction/search-view preparation, cleanup, enrichment, embedding/indexing, retries and human review for each arm, with measured throughput, unknown usage and uncertainty. Estimate representative full-run resources under the same quality policy; do not extrapolate from five easy cases alone |
| P0-G | Independent confirmation and decision packet | **Not started.** No fresh confirmation of a selected P0 policy | After the primary comparison, test the proposed policy once on a fresh human-reviewed batch not used for tuning. Record whether the choice changes and why. Produce a concise skip/selective/broad-cleanup recommendation, affected task/failure classes, remaining risks and evidence links for the human decision |

#### Finite investigation and stopping rule

1. **Plan before more benchmark calls:** draft P0-A and the coverage/budget/sample design for P0-B. This is offline planning, not a request to rerun old experiments. Do not invent numerical historical-quality thresholds or silently treat unapproved criteria as agreed. Human approval is needed for those standards, not for every reversible preparation task.
2. **Run one frozen primary comparison**, reusing compatible saved outputs only where their inputs, labels and configurations qualify. Bound calls/runtime and publish the experiment manifest before launch. Use targeted correction arm C only to test demonstrated OCR-related failures; preserve the raw/static controls.
3. **Run one fresh confirmation batch** for the proposed policy. Extra experiments require a named unresolved failure or uncertainty that could change the decision, explicit bounds and a stopping condition. Repeating a known saturated sample is not a substitute for confirmation.
4. **Enough information:** P0-A–P0-G have supporting evidence, results meet the predeclared standards, observed cleanup benefits/costs are attributable enough to choose, and no unresolved material uncertainty could plausibly reverse that choice within the declared scope. Show counts and uncertainty, including slices where the conclusion is weak. If uncertainty is still material, name it and do the smallest discriminating follow-up; do not declare victory or start an open-ended benchmark program.
5. **Record the human decision:** mark P0 decided only after the human reviews the packet and selects the policy. Record the scope, evidence/criteria versions, exceptions, rationale and reopening conditions. Any omitted capability/slice needs an explicit human-approved scope limitation; do not silently waive a required readiness item. Narrow provisional recommendations remain provisional rather than closing the whole P0 question.

The result may be task-specific: raw text for broad discovery, source-preserving normalization for broken words, targeted repair for demonstrated name/number failures. **P0 readiness is separate from production readiness:** small evaluated prototypes can establish the cleanup policy before all M2–M6 production features ship. Conversely, a P0 decision never authorizes M7/full-corpus processing or certifies the historical metadata.

For each P0-related POC, its result must name which readiness item it advances, the evidence path and whether that item remains missing/partial or becomes ready. Add no alternative P0 checklist elsewhere. Before a new run, state which plausible outcome would change the policy; if neither outcome changes a decision or closes a necessary gap, do not run it.

### Human-requested technical exploration backlog

- **Targeted scan-image fallback for uncertain OCR (HR-008 S2, 2026-10-22):** the human reports the fragment actually reads “660 citizens … protection to American labor,” and rejects Mini’s military-affairs inference. Preserve that as human-reported source interpretation, not an independently verified agent transcription or accepted OCR patch. Explore whether an uncertain paragraph can return the exact IA scan/leaf and a geometry-linked crop for a bounded human/model review. The user specifically wants this investigated if selective OCR repair is worthwhile. First prove source-image mapping and retrieval on one saved case, estimate time/cost, then ask before expanding scope. This is a future opt-in diagnostic, not authorization for corpus-wide visual validation, re-OCR, or automatically replacing text. Continue to preserve unknowns/abstain when the existing evidence is truncated. HR-008 is now closed and archived; use the applied guidance above. This exploration remains planned, not implemented.

### M1 prepared role-only retry: current executable state

**Offline preparation completed, models not run.** Tracked code `role_aliases.py` validates Pydantic input/output boundaries, raw hashes, Unicode half-open spans and reversible short aliases. Candidate IDs must be supplied person/speaker cues (not paragraphs/date cues); targets must be supplied paragraphs; evidence references must exist. Unknown uses null candidate and empty evidence with an explanation. Structural acceptance does not validate the semantic claim or the scope of mixed-turn paragraphs.

Tracked `artifacts/role-alias-preparation-20261023-02/` contains all six raw diagnostic inputs, provider packets, host alias maps, strict output schema, role-only prompt, hash manifest, source-review expectations, checks and gate log. Five cases reuse the previous diagnostic windows; the sixth adds HR-008's actual page break. Source preparation scanned/hash-checked the canonical snapshot in **3.929 seconds**, produced **56,813 bytes** of provider inputs, and made **0 calls / $0 API cost**. These are preparation measurements, not model throughput, token counts or quality estimates. The canonical hash matches the previously verified snapshot.

Independent source inspection confirms leaf403's final body ends “The” and leaf404's first body begins “House came…”: short targets P12/P13 are a provisional Wade continuation supported by prior named C3. P14 introduces Sumner (C4), so Wade carry must stop. P15's OCR `Yv'ADE` is missed by the literal uppercase name detector; P15/P16 require unknown or explicit review instead of automatic name correction or Sumner carry. Exact source quotes, geometry/line references and limitations are retained. This is AI-provisional source interpretation, not new human grades or validated authority linking. Only selected 8+8 paragraphs are supplied; the detector is not complete, dates/confidence/person authorities are not role-output fields, and mixed-turn paragraphs still need semantic span review.

```bash
# Inspect the frozen source expectations without a model.
uv run python -m json.tool artifacts/role-alias-preparation-20261023-02/source-review.json
# Rebuild offline only if needed, using a NEW output directory; never overwrite the frozen run.
uv run python -m congressional_globe.role_preparation --predecessor artifacts/v2-pivot-20261011/metadata-filters/span-selection --pages artifacts/runs/static-final-20261011/canonical_pages.jsonl --output tmp/role-preparation-replay
```

**Next:** implement the bounded audited runner over the prepared packets, then use existing small-call authorization after recording limits and inspecting workers/queue. No provider launch command exists yet. Preserve raw replies/validation failures and actual tokens/time/cost; separate role semantics from reference validity. Date-positive/negative work and reliable dated roster linking remain separate tasks. HR-005 becomes a concrete human request only after usable proposals and their exact source context are ready. Do not rerun already completed topic diagnostics or claim the six-case preparation proves model viability.

### Next bounded experiment: M1

1. Read these exact files under `artifacts/v2-pivot-20261011/metadata-filters/span-selection/`: `frozen_inputs.jsonl`, `manifest.json`, `selection_protocol.json`, `prompt.txt`, `output.schema.json`, `review/case-expectations.json` and `review/two-provider-case-review.json`. Frozen JSONL contains full raw text, hashes, spans and anchors. `prepare_span_selection.py` / `run_span_selection.py` explain historical behavior; **do not relaunch their failed long-ID configuration**. Old `runs/span-select-mini-20261011-01/` and `runs/span-select-ollama-20261011-01/` are terminal with errors.
2. Prepare about five bounded source windows covering petition presentation, ordinary speech, a letter/quotation, an unnamed continuation and mixed turns. Include the HR-008 concern: a previous-page speaker introduction followed by a next-page continuation, plus a negative control where an intervening speaker/chamber/date/proceeding boundary prevents inheritance. Acquire real adjacent context before labeling; version expanded input windows rather than silently changing old frozen cases. Explicit date evidence and date-negative cases must both appear. Reusing old cases is diagnostic; fresh cases need a declared split and exclusion check.
3. Use short request-local paragraph/cue aliases mapped by the host to immutable sources. Separate speaker-role and date tasks if one combined response is too dense. Require paragraph/span-local role evidence, date kind/scope and explicit unknowns; do not silently fix invented IDs.
4. Freeze source expectations before calls, label AI assessments honestly, validate offline failure fixtures, and record request/time/output limits before using installed Qwen and a matched small Mini sample. Existing bounded-testing authorization applies; this is not permission to drain any queue.
5. Independently review every response against full raw context, including false positives and omissions. Save a short source→proposal→review scorecard and actual time/cost. At H2/H3 (HR-005), explicitly tag the human with the first usable sample and role/date-scope disagreements before calling the output calibrated. Human questions should concern concrete examples, not approval of unspecified future work.
6. Update M1/current status/evidence and select the next action from observed failures. If data or authority support is absent, retain unknown and report coverage; do not manufacture a passing result. Do not expand a plateauing POC into corpus work.

The original predecessor-inspection command below remains useful background. The current prepared packet and next executable inspection are in the preceding section; do not recreate completed preparation or start a provider request from this historical checklist:

```bash
uv run python -m json.tool artifacts/v2-pivot-20261011/metadata-filters/span-selection/review/two-provider-case-review.json
```

Role-only short-alias preparation is now complete in the preceding section. The bounded runner and separate date task remain. Register any new run paths/limits in the live work record before model work. There is no audited executable M1 provider retry command yet; do not invent one or relaunch the old configuration.

For offline M1 preparation from the already frozen cases, copy **the entire** `artifacts/v2-pivot-20261011/metadata-filters/span-selection/` directory, retaining its relative path. Its frozen JSONL includes the needed raw windows; no full-corpus regeneration or source download is needed just to inspect/remap those diagnostic cases. Verify `frozen_inputs.jsonl` against `manifest.json` field `frozen_inputs_sha256` (expected `ac7a47b51e65641e787baa108201ebf8e50cf082fc11c8a01cabec6b6da4f484`); prompt/schema/protocol hashes also match that manifest. Review files and per-run results stay alongside it. The manifest's original “offline preparation” description is historical; actual run outcomes come from saved run summaries/results and current process evidence.

For **regeneration or independent canonical/source comparison**, additionally copy `artifacts/runs/static-final-20261011/{canonical_pages.jsonl,workflow_manifest.json,independent_verification.json}` and the original `<item>_hocr.html`, `<item>_djvu.xml`, `<item>_page_numbers.json` for the five item IDs listed in §2. Preserve directory layout and verify recorded source fingerprints before claiming equivalence. `pyproject.toml`/`uv.lock` and tracked source contracts travel with Git; models and credentials do not.

Git alone cannot recover ignored artifacts. If the specific inputs are absent, do compatible offline contract work with explicitly synthetic fixtures; do not fabricate historical samples or restart old POCs to hide missing evidence.

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

### Current human-label work

Read `artifacts/v2-subject-review/review_packets.jsonl` alongside its frozen `vocabulary.json`; keep the packet unchanged. `artifacts/v2-subject-human-labels.jsonl` is already prepared and still pending. Do not regenerate it or fill it with AI labels called human judgments. Human fields need reviewer identity, timezone-bearing timestamp, decision/note and exact paragraph quotes/Unicode offsets. In-scope and OOV topics may coexist; no-subject/unknown decisions can retain evidenced incidental mentions. For completed human labels, create a new reviewed output:

```bash
uv run globe subject-review-import --sample artifacts/v2-subject-review \
  --reviews artifacts/v2-subject-human-labels.jsonl \
  --output artifacts/v2-subject-human-reviewed.jsonl
```

This is a future human action, not an instruction to import pending labels now. Import requires every window, verifies evidence/digests, refuses overwrite and keeps the original sample. It does not authenticate the author or establish historical truth. Older local HTML review packets can be inspected at `artifacts/v2-pivot-20261011/human-review/index.html`; their rendered UI was not independently verified. Current subject/model review JSON does not require a server or model calls.

## 9. Agent working rules and handoff discipline

### Stateless startup and mid-flight recovery

Use this same procedure in Codex, OpenCode or any other harness. Tool-specific startup files, if needed, must point here rather than copy the plan into another backlog.

1. **Orient:** read `AGENTS.md`, this plan's goal/P0/current status/live work record and active checklist, then `HUMAN_REVIEW.md` for actual responses and pending items and recent entries in `CHANGELOG.md` for completed work. Inspect `git status --short` and recent commits. Preserve uncommitted human/other-agent work; never reset it to obtain a clean start.
2. **Verify reality:** inspect the recorded host/PID **and process start time/full command** to avoid PID reuse, any accessible harness session, durable queue/results/events and fresh logs. `make status` describes cleanup only. On Mac, `ps -axo pid,lstart,etime,command` provides process identity; use an equivalent elsewhere and exclude the inspection shell/search itself. A loaded Ollama model or lock-file presence alone proves neither an active request nor a dead worker. If process inspection is denied, obtain the harness's available permission/tooling access or mark runtime state unknown and continue offline; denial is not evidence that no worker exists.
3. **If running:** do not restart, duplicate or interrupt the worker. Observe the same process/store and update the checkpoint. Review persisted rows or do explicitly separate offline work while waiting. Keep local requests sequential under the actual shared lock.
4. **If unknown:** retain `observation_unknown` and re-poll the same handle or inspect OS/store evidence. An observation timeout is not termination. If the old host is inaccessible, do not launch a duplicate job; continue safe offline work and identify the required host/state recovery.
5. **If terminal/interrupted:** retain logs/exit evidence, compare intended tasks with saved results and unresolved attempts, then use the documented compatible resume path. Reuse unchanged cleanup queue/run IDs. For a non-resumable POC, do not overwrite its directory or repeat every request under a new ID: first audit recovery/reuse of compatible results, or define a specifically bounded follow-up for unresolved cases with its reason and unknown prior usage recorded. Failed validation stays a recorded failure.
6. **If idle:** claim the next unclaimed work unit and owned paths in the live record, timestamp it and declare limits. Re-read shared state before launch; resolve another agent's ownership explicitly. Do not assume their worker stopped when your conversation ended or take over `tmp/performance/`.
7. **Continue the active plan:** currently implement the M1 role-only audited runner over the prepared six-case packet while P0 stays open; do not recreate completed preparation. Read saved topic results rather than rerunning Mini/Qwen. Existing bounded-testing permission applies; lack of full-run permission does not block useful offline engineering.
8. **Persist as you go:** launch intent/config before requests, OS identity immediately after launch, results/checkpoints incrementally, and exact state/evidence/limits/next action at handoff. Commit completed units. A final chat message must never be the only record.

**Handoff acceptance:** a replacement agent using only the repository, copied artifacts and observable runtime must identify the goal/P0 question, owner/unit, actual worker state, completed/unresolved work, human requests/answers and their blocking scope, exact safe next action, and bounds/authorization. If not, repair the live record before another model call. M2 must demonstrate this with an interrupted worker and a second harness or independent process; that runtime guarantee is still pending.

### Engineering rules

1. Read this plan first. Check actual Git/files/run evidence; distinguish current status from historical snapshots. State which milestone and decision a proposed unit advances.
2. Use Luna delegates for bounded preparation, evaluation and documentation when available, as requested by the human. Delegate with clear file ownership; inspect their findings. Do not treat an AI reviewer as human gold. If a different harness cannot provide that model, disclose the limitation rather than silently inventing delegation.
3. Use uv, Pydantic v2 at external-data boundaries and streaming parsers for large OCR files. Keep cyclomatic complexity ≤5; refactor rather than add exceptions. Tests should cover core behavior/failure cases, not broad low-value suites.
4. Raw OCR/IA metadata immutable. Derived products belong under `artifacts/`; disposable scratch under `tmp/`, ignored except `.gitkeep`. Do not edit/clean/commit the separate agent's `tmp/performance/` work. Secrets remain in ignored environment configuration, never evidence or Git.
5. AI requests remain opt-in. The human authorized bounded Mini/Ollama POCs; a full-corpus model run, model download or recurring schedule is a separate action. Do not infer full-run approval from this plan or a continuation message.
6. Preserve source anchors and patch-based cleanup. Inspect existing SQLite/run state and live handles before workers. Keep Ollama sequential under the shared request lock; local API key placeholder is `ollama`. Do not restart solely because observation timed out; verify the same handle/process to terminal first.
7. For code changes run `make gate` before handoff. It applies Ruff and the required elevated `npx prettier@3.9.10 --prose-wrap never --write "**/*.md"`, then Ruff format/check, ty, `complexipy src tests --max-complexity-allowed 5`, and pytest. Markdown edits require that Prettier command with elevation for Codex; original archived snapshots are intentionally excluded from reformatting. Check `git diff --check` before commit.
8. After a unit, update **this document**: current status, milestone status, evidence/limits, exact run IDs/handles and next executable action. Record terminal state before reusing resources. Keep the current block current; do not append another conflicting “latest next steps” section. Append a compact dated change entry to [CHANGELOG.md](CHANGELOG.md), not this plan.
9. Commit completed units with a single-line message and no agent attribution. Include authorized human changes deliberately; never sweep secrets or another agent's scratch files into Git.
10. A handoff reports what changed, evidence/checks, limits, active work and next action. Do not mark milestones complete on intentions, mock results, schema passes, credit exhaustion or a persuasive summary. The long-term goal remains incomplete until its stated release requirements are demonstrated.

## 10. Document consolidation and history

This plan replaces the active planning/progress roles of `PROJECT_GOAL.md`, `PROGRESS.md`, `V2_PIVOT.md`, `V2_HANDOFF.md`, `RUNBOOK.md`, `HAPPY_PATH.md`, `V2_EMBEDDING_MODELS.md`, `V2_TAGGING_EVAL.md`, `V2_TAGGING_RETRY.md` and `TAG_ARM_PROMPT.md`. Those paths are compatibility pointers only. Do not add new work or contradictory instructions there. `HUMAN_REVIEW.md` is the explicitly requested interaction companion for readable requests, demos and original human answers; it must not become a second roadmap or independent status register.

Original documents, the prior README and prior agent instructions are preserved verbatim in `docs/archive/2026-10-22-pre-masterplan/`, with original-file hashes in `manifest.json`. Archived checklists, pending states and commands are historical evidence, not an active task queue. Relative links in snapshots reflect the former root locations. Important detailed reports/hashes live in the archive/artifacts; summaries here do not turn provisional evidence into verified history.

Historical changes are maintained in [CHANGELOG.md](CHANGELOG.md). Agents must read recent entries when resuming work and append each completed unit there. Keep this plan focused on current goals, decisions, evidence and next actions; do not append dated history here.
