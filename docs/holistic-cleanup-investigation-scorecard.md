# Holistic cleanup investigation scorecard

This is a bounded P0 design artifact, not a second roadmap. [MASTER_PLAN.md](../MASTER_PLAN.md) remains the authority for project scope, status, human checkpoints and next action.

## Decision to inform

Determine whether the five-part 39th Congress corpus should receive a broadly cleaned, separately versioned reading transcription in addition to its immutable raw OCR. The decision considers human reading, copy/quotation, text-to-speech, RAG/retrieval and historically grounded annotation together. It does not decide whether raw OCR/scans remain authoritative: they do.

The investigation can recommend one of three scoped paths:

1. Keep raw OCR plus search normalization for a stated use case.
2. Use deterministic or selective image-grounded repair for defined failure classes.
3. Produce a broad clean reading layer through a measured repeated-LLM workflow.

No outcome authorizes a corpus-wide job until the human reviews a concrete provider/configuration, cost/time estimate, recovery plan and quality evidence.

## Non-negotiable text layers

| Layer | Purpose | May it overwrite another layer? |
| --- | --- | --- |
| Scan + immutable raw OCR | Primary-source evidence, audit and re-evaluation | No |
| Clean reading transcription | Reading, copy/quotation, text-to-speech, RAG context and model input | No; it is a separately versioned derived layer |
| Annotation/enrichment | Speakers, dates, topics, legislation, boundaries and other evidence-backed assertions | No; it cites the text layer and primary-source anchors used |

Any uncertain or disputed clean reading remains explicitly uncertain/reviewable and links back to raw text and the source page/crop. A fluent model output is not evidence by itself.

## Repeated-workflow contract

The repeated work is performed by a selected LLM provider, not by an interactive Codex conversation. It may compare an installed local vision-capable model with an OpenAI API model if a later bounded run explicitly authorizes both.

For each item, persist:

- composite source identity, raw-text hash, whole-enough source context and exact scan/geometry reference when an image is used;
- prompt, schema, model/provider/runtime digest, decoding parameters and policy version;
- launch intent, raw request/reply, usage, elapsed time, cost or local-runtime measurement, validation and review result;
- proposed clean text, no-change, unknown/review or failure state; and
- compatible-resume/cache identity and any ambiguous/interrupted attempt state.

Process local requests sequentially under the shared lock. Do not silently retry, overwrite prior outputs or collapse unknown into success. Image retrieval is selective and source-anchored; it is not a bulk image archive.

## Representative POC design

Freeze a source-hashed packet before calls. It should include all five parts and deliberately cover:

- clean controls and ordinary OCR damage;
- names, numbers, dates, bill identifiers, punctuation and line-wrap cases;
- proceedings, index-like entries and longer connected passages;
- text relevant to speaker/date/topic/bill annotation and retrieval; and
- missing, irrelevant or insufficient source-evidence controls that must remain unknown/review.

Use identical packets, output limits and evaluation rules for every provider/workflow comparison. Keep any tuning set separate from a fresh confirmation packet. Earlier diagnostic cases may establish feasibility but are not held-out evidence.

## Quality scorecard

The human must approve concrete thresholds before seeing fresh results. The scorecard reports counts and examples, not a single synthetic “accuracy” number.

| Dimension | Measure | Failure examples |
| --- | --- | --- |
| Source fidelity | Correct words, names, numbers, punctuation and historical wording against scan evidence | Invented word; changed person or bill number; omitted sentence |
| Uncertainty discipline | Unsupported readings remain unknown/review with evidence reference | Model guesses from context where image/text does not support it |
| Reading and TTS | Sentence flow, audible names/numbers, punctuation and harmful spoken artifacts | Garbled OCR sent to speech; incorrect spoken name/number; broken sentence |
| Research utility | Effect on exact/lexical/vector retrieval, RAG context and structured tags | Cleanup harms recall, makes a false attribution look supported or obscures evidence |
| Workflow reliability | Validation, cache/reuse, interruption recovery and auditability | Lost attempt, hidden retry, incompatible resume or missing provenance |
| Cost and scale | Per-item throughput, local memory/runtime, API/image/review cost and cautious full-run projection | Extrapolation from easy cases only; unknown usage reported as zero |

## Required comparison report

The bounded POC report must state the exact inputs/configuration, provider/runtime identity, per-stratum results, raw outputs and failures, measured time/cost, human/independent review method, limitations and the plausible decision changed by the result. It must separately compare raw OCR, existing static cleanup and the candidate clean reading layer where applicable.

The next step after a representative primary comparison is one fresh confirmation batch. Only then prepare a human decision packet choosing raw-first, selective repair or broad cleanup with stated exceptions and reopening conditions.

## Primary comparison specification v1 — proposed for HR-003

This specification is frozen for standards review, not yet an executable source packet. All numerical targets below are proposals awaiting human agreement. Source selection, visual expectations and the executable runner remain to prepare; no fresh provider call is authorized by registration of this document.

### Sample and matching

Use 18 real units plus two evidence controls per provider. Select three units from each of the five parts: one ordinary proceedings passage, one passage with OCR damage affecting a name/number/date/bill, and one index or other compact structured entry. Add three longer connected passages (different parts), including at least one page/column continuation and one quoted letter or legislative text. Record missing strata rather than relabeling a convenient passage. Target 200–700 words per ordinary unit and 700–1,200 per long unit, at most 12,000 raw words overall. Include punctuation, hyphenation and apparently clean spans within these units; “clean” requires later image inspection, not an OCR appearance judgment.

Choose candidates deterministically within strata (seed20261024, source-order reservoir, record eligibility rules and all rejected candidates). Document type and damage classification require source review. Prior model-exposed S0/S1/M1 examples and HR-004 windows may be calibration material only, excluded from these 18 primary units. Check all available exposure inventories, record incompleteness, and call this a deliberately balanced diagnostic sample rather than representative population prevalence or certified held-out gold. Reserve five fresh confirmation candidates, one per part, before tuning; their later calls require a separate registered bound.

The two controls are duplicates of real units with (a) no image and an explicitly designated raw span requiring source verification and (b) a deliberately mismatched image. Mark these manipulations in the audit manifest, conceal the expected answer from the provider, and exclude them from real-unit improvement rates. A control must route unsupported repairs to review, while preserving independently supported text. Do not seek degraded scans.

Compare A (raw plus the existing deterministic search view), B (current static text), and C (whole-unit clean reading proposed from raw plus the same source images). Freeze A/B text and mappings before generation. Providers see the same raw/context/images; B is an evaluation baseline, not an unrecorded hint. Use one image-assisted policy for this primary comparison; a text-only/image-routing ablation is a later question only if it could change the policy. Identical source segments and boundaries apply to all comparisons. This unit measures clean reading and downstream input integrity; it does not substitute for the separate retrieval, grounded-answer and enrichment evaluations required by P0-C/D/E.

### Input, reply and provenance contract

Implement these external boundaries with Pydantic v2 before launch; this table specifies required semantics, not a claim that code exists.

| Record | Required fields and guards |
| --- | --- |
| Frozen manifest | version, run ID, seed, selection/exclusion record hashes, ordered unit IDs, policy/prompt/schema/code hashes, provider options, budgets and approved HR-003 submission reference |
| Source unit | part/item/scan leaf/printed-page value plus provenance; ordered paragraph IDs, raw UTF-8 SHA-256 and text; source-file SHA-256; hOCR page/line IDs and geometry; target and context distinguished; context hashes and neighbor order; static text/version/hash and raw mapping |
| Image binding | target/bundle/receipt SHA-256, image bytes SHA-256, IIIF URL, dimensions, native region and transform, exact associated source spans; validate against immutable source hashes; wrong-image control explicitly marked in host manifest |
| Provider reply | unit ID, status (`unchanged`, `proposed`, `needs_review`), ordered nonoverlapping raw-offset patches with exact old/new text, evidence image/region IDs and reason; uncertain spans with raw offsets and reason; no historical metadata assignments |
| Derived clean text | host replays patches against exact raw text; rejects wrong old text, overlapping/out-of-range patches, missing image evidence for changed readings, altered context or inconsistent status; saves full derived text/hash and raw-to-clean span map; deletions/insertions have explicit anchors |
| Attempt/review | fingerprint, attempt ID/state/timestamps, exact request/reply, usage/unknown usage, duration, validation failures, source-review findings, human-review state, selected output version; no software validation state named human approval |

Preserve spelling, historical grammar and all substantive wording. Join typographic line breaks only under the recorded policy; preserve lexical compounds. Do not modernize, summarize, expand abbreviations or infer missing text. A model may suggest a reading; source review determines whether it is supported. Unsupported or disputed spans retain the raw reading with an explicit review marker in the derived presentation. Quotation remains linked to scan/raw evidence. Never infer clean-to-image coordinates without the validated raw mapping.

### Provider and resource limits

Proposed first phase: installed Qwen27B, Gemma31B and Muse30B, 20 units each, at most 60 local inference attempts total, strictly sequential under the existing shared lock. No paid API calls, new models, downloads, recurring jobs or canonical edits. Reuse previous diagnostic results for context only; they do not satisfy the changed whole-passage inputs.

At launch inspect actual installed IDs/digests, image capability, runtime and supported context/output options. Freeze a common supported envelope of at most16,384 context tokens and4,096 output tokens; preflight actual token/image allowance including prompt. If any selected input cannot fit any provider, stop and version the packet or record that provider as ineligible; do not silently truncate or split one provider's input. Output-length failure remains a failure. Use the same temperature0 request where supported; report unsupported options explicitly. No model-server restart/configuration change is implied.

Limit each request to120seconds, each model batch to2,400seconds, total inference window to7,200seconds including model loading. Check remaining wall time before dispatch; the request timeout is additionally capped by remaining batch/total time. No automatic retries, even after invalid JSON. Abort the batch on an ambiguous transport outcome until the server/process state is reconciled. At most24 new crop files /12MB transferred through the existing S0 resolver; cache reuse first, no full-volume scans. If sufficient source context exceeds the crop budget, stop and revise the bound before fetching. Log loaded-memory reports and observed swap/pressure when accessible; unknown measurements stay unknown. Do not unload another client's model or treat model file size as measured memory.

Human review proposal: at most60minutes for primary review, in short packets; source expectations prepared before provider outputs. Compare anonymized outputs with scans and raw/static controls. Measure actual minutes, including disagreement handling. If the time cap prevents completion, report unreviewed coverage and stop acceptance claims; do not silently accept the remainder. No actual synthesized audio or paid TTS in this phase: assess pronunciation-relevant text and sentence flow, explicitly leaving listening tests unresolved.

### Proposed decision criteria and contrasting outcomes

These are conservative pilot routing criteria, not estimates of corpus error rates. Report every count and denominator by provider/stratum, including invalid, timeout, review and unchanged results; failures remain in the20attempt denominator. Reading results use18real units and separately report supported-to-scorable coverage. An unknown is not a correct transcription.

| Dimension | Proposed primary criterion | Examples |
| --- | --- | --- |
| Critical fidelity | Zero observed unsupported substantive changes in selected outputs; any one blocks automatic adoption and requires a named repair/review policy | Changing a person, amount, date, negation, bill number or omitting a sentence is critical; a scan-supported repair preserves meaning |
| Ordinary fidelity | Report character/word edits and residual errors against source review, separately from harmless typographic normalization | Joining a line-wrap can help; changing a historical compound without print support is an error |
| Usable reading | At least17/18 real units usable without substantive repair; at most3/18 require manual review; both targets must hold | Readable sentence with supported names/numbers passes; fluent invented wording fails; uncertain critical text routes to review |
| Evidence discipline | Both controls route unsupported readings to review; all changed real spans have validated evidence anchors | Missing evidence prompts a review marker; a plausible guess from the wrong crop fails |
| Incremental value | At least3/18 real units have a source-supported meaningful reading/TTS-text improvement over B, with zero critical regressions; report gains over A separately | Removing distracting OCR artifacts helps reading; a cosmetic change alone is not a meaningful gain |
| Reliability | All saved selected outputs replay exactly; completed resume makes zero calls; simulated interrupted attempt remains unknown until reconciled | Silent retry or reusing an incompatible result blocks launch/adoption |
| Resource feasibility | Stay within caps, report review minutes and elapsed seconds per raw1,000words by stratum; no corpus projection from this balanced sample alone | A fast easy crop does not establish throughput for long speeches |

Human may amend these targets in HR-003. Passing supports a provisional next confirmation/evaluation step only; failing identifies whether a selective policy or one cause-specific revision is worth investigating. No result here can close P0 or establish a general model winner. Retrieval/RAG/tagging effects must subsequently use identical queries/context and evidence-backed labels across A/B/C; list them as unmeasured until that work occurs.

### Durable execution and recovery proof

Before inference implement an offline dry run that resolves every hash, replays static/clean mappings, measures the input envelope and writes an ordered launch plan without provider access. Persist `launch_intent` and an attempt fingerprint before dispatch; append request-start, reply-saved, validation and review events atomically with durable records. Save raw output before parsing. Use distinct terminal states for valid, invalid, timeout, failed and interrupted/unknown. OS PID/start/full argv and observed UTC belong in the master live record.

Compatible cache identity includes raw/context/image bytes, provider digest/runtime, prompt/schema/policy, options and code version. A completed compatible attempt is reused without network; an incompatible one is retained and refused. A second process must demonstrate recovery after an injected interruption, with no duplicate attempt and unknown usage preserved. Do not claim the existing one-shot vision runner already implements this contract. After any outage, inspect process and persisted events before retrying a single unresolved unit under a newly recorded cap.

### Readiness and next decision

This design advances P0-A/B/F preparation; all remain incomplete. HR-003 asks for standards, review effort and the local resource envelope. After its answer is archived/applied, freeze the actual source packet and pre-output source expectations, implement/validate the bounded runner and recovery checks, and register the exact launch manifest. Use H4 for any changed bound. HR-004 continues independently as source-only topic calibration. Confirmation, full downstream comparisons, final P0 decision and full processing each retain their existing checkpoints in the master plan.
