# OCR repair: evaluation and workflow contract

This reference translates the 2026-10-27 human discussion into engineering requirements. [MASTER_PLAN.md](../../MASTER_PLAN.md) is the only task queue, progress and ownership record. [Archived dialogue](../archive/human-dialogue/2026-10-27/HUMAN_DIALOGUE.md) preserves the original proposals; the latest human instruction authorizes this operational plan. Existing evidence and original sources remain immutable. This document is a design contract, not an implemented workflow or an approved numerical quality standard.

## Direction and decision boundaries

The immediate investigation measures **how accurately and efficiently damaged OCR can be repaired**, with deterministic processing first and image-grounded AI where needed. The intended destination is a clean reading layer across all five parts, separate from original OCR. Do not repeatedly reopen whether consequential damaged words matter. P0 remains open on the safe method, routing, costs, exceptions, review burden and eventual deployment policy. A clean-looking result or working search is not historical verification.

Offline inventory, research, sample preparation, typed contracts and software checks can advance under bounded master tasks. Bounded deterministic-only library implementation and fake/offline tests can proceed under their task without waiting on adoption of a new orchestrated workflow. New workflow adoption follows the existing engineering review rule; new provider requests require a separately frozen authorized run and fresh runtime checks. No model downloads, full-corpus scoring/cleanup, changed human-review allowance or live calls are granted by operationalizing this discussion. Full launch remains the separate M7/H4/H6 decision. A cleanup diagnostic does not have to wait for the entire search/MCP backend; M6 still retains its full acceptance conditions.

## Reuse first, without repeating spent experiments

Inventory the existing static rules and lexicons, source word geometry/confidence, image cache, reading contracts/journals, failed primary outputs, T35 quote binding and T33/T44 source-mapped retrieval. Record file hashes, versions, input/config compatibility, actual reuse eligibility and known defects. A compatible saved output may be reused only with its exact identity and previous-exposure status. A static edit is not an AI-clean result, a schema-valid answer is not a correct reading, and a saturated diagnostic is not fresh confirmation.

The previous primary comparison is terminal. A new diagnostic must name the unresolved failure it discriminates, the changed method, finite scope and a stopping rule. Do not reconstruct its48attempt allowance as permission or repeat its spent requests. The six-paragraph raw/static pairs are useful software fixtures, not a representative evaluation sample or a substitute for an absent clean arm.

## Small chunks throughout the investigation

The human clarified that manageable chunks apply to **the whole study process**, not merely one small pilot. About30minutes of computer AI work is a per-experiment planning target. The total investigation can contain several finite experiments; eventual whole-corpus processing may take much longer. Do not treat one tiny sample as the complete study or cut required evidence merely to make every research question fit that sample. Exact limits and authorization still belong to the named task/readiness manifest.

Each experiment must fix one question whose answer could change the next engineering/research decision, a small exact sample/control set, the compared settings and finite resource limits. Save inputs, outcomes, failures, unknowns and actual consumption, then state what was learned and which uncertainty merits the next chunk. Reuse compatible saved evidence, keep completed experiments terminal and change only the intended variable in a comparison. Do not automatically repeat a successful or inconclusive packet or launch the next chunk as a recurring chain.

For example, one chunk can test whether image auditing catches a plausible wrong number; another can examine apparent deterministic successes and unflagged text; another can test harmful edits to correct rare names. These are examples of questions, not newly selected tasks, sample labels or call permissions. The master remains the only execution queue. T60 is one proposed first chunk; later sample choices and bounds are frozen only when their named uncertainty, inputs, dependencies and authority are ready. T49 reserved confirmation cannot become routine development material.

Keep cumulative study calls, time, image/human costs and unknown usage across chunks; a new packet does not reset a spending allowance. Combine findings only when source units, arms, definitions and sampling weights are compatible; deduplicate reused evidence and report selected challenge cases separately from probability samples. Several small AI-only runs do not become independent truth merely by accumulation. Source fidelity, independent-reference limits, coverage, P0 acceptance and the separate full-run decision remain explicit. Human review is proposed only for a concrete decision-changing need within actual authority, not automatically after every chunk.

## Small AI-only feasibility diagnostic

The human's later2026-10-27 direction asks for an initial option taking about30minutes of computer AI runtime. T60 in the master narrows the first diagnostic to5probability paragraphs plus2exposed failure audits, at most12sequential requests/24request-minutes plus6minutes setup/report, with zero required newhuman review. Preserve T49's larger sample/reference design; it is deferred as an initial-runtime requirement, not accepted or erased. This is a design envelope, not live authority or proof of backend cancellation.

An image-only observation followed by a separate combined repair/audit request can expose discrepancies without newhuman grading. Keep the first observation hidden from the second request; same-model agreement remains correlated AI evidence, not independent truth. Report feasibility, source bindings, provisional disagreements/failures and actual consumption. Actual efficacy/recall/harm-rate claims, human gold, P0 acceptance and full-run decisions still need their applicable independent evidence/criteria. Do not make the larger independent-reading plan a prerequisite for this clearly provisional diagnostic. Unknown/missing/timeout outcomes remain visible, and a client deadline does not prove server work stopped.

## Sample and independent references

Prepare a reproducible probability sample from the whole five-part collection, with an explicit page or paragraph unit, eligible frame, selection algorithm/seed, inclusion probabilities, allocation and hashes. Freeze selected IDs before observing new model outcomes. Propose finite size and image/text budgets with rationale; no number is human-approved merely because it appears in a plan. Account for blank/unusable pages without silently replacing difficult material. A content-type oversample needs explicit weights or separate reporting; a random sample spanning five parts does not automatically guarantee every rare document type.

Keep a separately reported difficult-case set for damaged names, places, years/other numbers, line splits, punctuation, historical vocabulary, apparently correct text and insufficient images. Known fixtures/synthetic errors test plumbing or challenge behavior, not population prevalence. Track prior exposure; preselect a disjoint confirmation set or document why disjointness is not proved. Any post-score inspection across risk bands is a separate validation sample with its selection probabilities retained.

Freeze independent page-image readings and unresolved spans for the evaluated text, including unflagged and apparently clean passages. Correctness must not be defined by the detector or the same AI being evaluated. Specify reviewer provenance, evidence available, disagreements and adjudication; AI-only readings remain provisional. Whole-unit references are needed to count misses: checking only model-suggested repairs cannot establish recall. Preserve ambiguous image readings rather than forcing a reference. Do not expand HR-009/HR-010 review time or create another human round without an explicit decision on a concrete bounded request.

## Deterministic repair, detection and lexicons

Preserve raw OCR/hash/geometry. Apply only versioned rules with exact expected-source checks and reversible raw-to-derived mappings. Record each proposed or applied mechanical edit, rule version, reason and provenance. Line-break joining must not indiscriminately collapse meaningful hyphens. Never silently modify source files or accepted ledgers.

Evaluate at most the bounded options named by the research task: historical/general dictionaries, historical spelling variants, congressional names and city/place lists, plus available OCR confidence and character-pattern signals. Record primary source, license, redistribution limits, version/checksum, period/geographical coverage and known omissions. A roster absence does not disprove a name; a dictionary miss does not prove damage. Dictionary suggestions are candidates, not evidence of print. Keep auxiliary lexical names separate from accepted person/place authority identities. No new dependency or download is automatically adopted by research.

Candidate records need source identity, raw interval/quote/hash, context, token category, detector/rule version, signals and route reason. Separate unfamiliar words, names/places, numbers/date-like tokens, mixed alphanumeric text and word-split patterns. A real word or plausible number can still be wrong. The study must explicitly evaluate numeric/name verification routes rather than classify them clean just because spell check passes. Whether every number/name goes to AI is an experiment policy to compare, not a settled automatic-edit rule. Benchmark CPU work and model load instead of promising a whole-corpus pass in seconds.

## Matched processing paths

Freeze identical source units and deterministic settings for raw, existing static, and new derived proposals. Separate three model roles in provenance and budgets:

- **Targeted repair:** an image-capable model inspects flagged text, sufficient surrounding text and hash-bound image crops. It proposes a reading or abstains; missing/irrelevant/unclear image evidence yields unresolved status. Qwen is the human's preferred candidate to investigate, not a verified capability or final provider choice.
- **Audit of apparent success:** inspect original OCR, exact deterministic edits, resulting text, spell-check results and other diagnostics against the original image, **including detector-negative/no-error units**. Return structured discrepancies rather than an unsupported clean bill of health. Include known-correct historical names and clean controls to measure needless changes as well as missed damage.
- **All-unit comparison within the finite sample:** propose an image inspection path that is not restricted to detector flags, to measure flag-only misses. This was discussed, not separately authorized to dispatch. Its audit/repair role, independence and costs must be explicit; share an exact compatible saved observation where valid rather than paying twice.

The audit may be a separate call or a deliberately designed combined output, but those are different configurations requiring frozen identities and accounting. An audit informed by deterministic proposals can be biased; a blinded first reading or dictionary-suggestion ordering comparison is an optional design choice, not a granted extra arm. An auditor's acceptance does not certify no errors. Independently measure the auditor's false alarms and misses; do not treat its output as gold or automatically apply its corrections.

## Typed outputs, source binding and failure behavior

Design strict versioned Pydantic boundaries before implementation. Distinguish the original OCR, deterministic layer, model proposal, derived host coordinates, audit findings and actual human decisions. Preserve raw replies before parsing. Prefer model-supplied exact source quotes with host-derived positions; never ask a model to count raw offsets or silently salvage a failed old contract. A repaired spelling need not occur in raw text: bind its raw evidence quote separately from the proposed reading.

An audit record should bind unit/source and image fingerprints, input/derived layer hashes, detector/lexicon/rule versions, completeness/inspected scope and a list of findings. A finding needs its affected source anchor, category (missed damage, incorrect deterministic change, number/name concern, unsupported proposal, or evidence uncertainty), original/derived wording as applicable, proposed reading if any and evidence basis. Allow explicit no-finding, incomplete inspection and unresolved states. No-finding means no issue reported in inspected scope, not error-free source. The exact schema/prompt is a task deliverable; these semantic requirements do not invent model results or human labels.

Host checks must reject wrong hashes, quote ambiguity, unsupported source/image links, out-of-scope evidence, malformed results and incompatible request/result reuse. Preserve disagreement between repairer and auditor. Keep raw and derived spans separate through T33/T44-style support mapping. Retain accepted/abstained/rejected/unreviewed states without converting proposals into accepted ledgers.

Reuse the existing bounded runner/journal, shared Ollama lock and sequential dispatch; do not introduce an agent SDK, new scheduler or generic automation by default. Integrate exact request/raw-reply checkpoints, unknown usage, refusal/truncation, timeout, output budgets, cumulative attempt accounting and no automatic retries. Prove interruption/reuse in fresh fake-provider processes. Code gates establish mechanical behavior, not source truth or general recovery guarantees.

## Negative testing and measurable outcomes

Use these complementary failure groups, with independent reference scope and correct denominators:

| Question | Report before/after and by category |
| --- | --- |
| Does the detector miss real damage? | Flagged reference errors / all independently established reference errors; missed errors in detector-negative text. If whole-unit references are absent, report recall unavailable. |
| Does it flag correct text? | Correct text flagged / reference-correct opportunities under a defined token/span unit; false alarms per inspected page as a separate measure. |
| Does repair help? | Reference errors correctly repaired / reference errors; attempted-repair correctness; unchanged, missed and abstained cases kept separate. |
| Does repair introduce harm? | Newly incorrect readings among reference-correct text, with the inspected denominator and unsupported inventions shown. |
| Does the image auditor miss mistakes or invent alarms? | Independently confirmed discrepancies detected/missed and unsupported audit findings, including deterministic no-error cases and known-correct controls. |
| Are names/numbers protected? | Separate name/place/year/other-number results and uncertainties, not only an average word error rate. |
| Is the reading useful? | Source fidelity, readability/copy/quotation and reading/TTS outcomes kept distinct from lexical-hit changes; state whether audio was actually produced and assessed. |
| Does it help downstream? | Matched search, metadata and grounded-answer outcomes with compatible contexts and citations; retain negatives and unsupported answers. |
| What does it cost? | CPU time, calls/model time, input/output/image usage, image fetch/storage, retries/failures, human review and unmeasured hardware/energy separately. |

Report raw counts, sample design, weights where needed and uncertainty. Small challenge sets do not yield corpus accuracy percentages. Unresolved source readings are not silently counted as correct, wrong or omitted; report their coverage separately. Predeclare consequential-error categories and proposed acceptance/miss/harm/unknown tradeoffs for H1/H2 agreement. Do not invent a pass threshold or call AI feedback a human grade.

## Optional prediction of cleanup reliability

A pre-cleanup risk score may predict input damage, post-cleanup errors or review workload; these are different targets. Keep local number/name flags alongside page summaries so one consequential error is not averaged away. Freeze candidate features/versions before observing evaluation outcomes and measure computation time. Original OCR confidence is a feature to investigate, not a calibrated probability of correct cleanup.

Compare pre-cleanup scores with independently checked outcomes across score bands and held-out units. Avoid fitting and evaluating on the same pages. Use probability calibration/error metrics only when a probability is actually defined and supported; otherwise report ranking and observed outcome rates with denominators. Compare with a simple baseline and account for scoring cost. If it adds no useful prediction, defer it. **Scoring must not block detector/repair/audit implementation or sample cleanup.** No whole-corpus scoring run is authorized by a sample study.

## Finite launch, reporting and decision

Before live work, freeze sample/arms, independent-reference plan, exact model/backend/digests/capability proof, prompts/schemas/images, request identities, per-call and cumulative calls/time/token/image/dollar/wall limits, review effort, zero automatic retries, stop/recovery rules and prior usage kept separate. A live capability check has its own authorized budget; no model substitution or synthetic trial is free or implicitly included. Ask for an explicit bounded authorization only after the concrete launch package is reviewable. Preserve failure cases and unknown usage; an old remaining allowance is not new permission.

After terminal execution, report repair efficacy, detector/auditor misses, new harm, unknowns and review workload with total costs. Project full-collection cost cautiously from sample weights, runtime and category mix; include uncertainty and failure/review workload, and distinguish measured from assumed hardware/energy. Show which unresolved result could change the method/routing decision. Reuse the old primary comparison as evidence, not as an authorization to repeat it. A separately bounded fresh confirmation requires explicit authority and a finite stop; repeated open-ended experiments are not implied.

The recommendation concerns the method for a safe, efficient clean layer and its exceptions. P0-A–G remain the only readiness register in the master; no duplicate progress checklist lives here. Full cleanup execution, accepted pilot/release and canonical-text changes remain separate decisions. Missing reading/TTS/downstream evidence must be measured or explicitly presented as an unresolved scope limitation to the human, never silently waived.
