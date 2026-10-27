# T60: a smaller, roughly 30-minute AI pilot

The human asked for something smaller that might take about30minutes of the computer running an AI model. This design replaces the large reference-reading exercise as the **first diagnostic**. It needs no new human grading. It preserves the original T49 design unchanged for possible later independent verification. [Master task](../../MASTER_PLAN.md#ordered-task-queue).

## The smaller experiment

| Work | Units | AI requests |
| --- | --- | --- |
| Image-only observation, then a separate combined repair/audit pass | 5random paragraphs, one per part | 10 |
| Audit two fixed saved failure cases against their source images | 2exposed cases: a wrong chapter number and removal of a printed repeated word | 2 |
| Host comparison and report | Same fixed inputs; no further model request | 0 |
| Total ceiling | 7units | 12 |

Use the first frozen T49 primary priority in each part, with no rescoring or new corpus search. These remain top1 selections from the original full frame: inclusion probability1/N and expansion weight N for that part. The five targets total882raw characters; the two historical challenge units add3,420. This is enough to test request size, grounding behavior, obvious failures and practical runtime. It is too small to estimate corpus accuracy. With one paragraph per part, within-part sampling variance cannot be estimated. Do not report precise population error rates or mix exposed challenge outcomes with random-sample counts.

The remaining20T49 primary paragraphs and all10reserved confirmation paragraphs are outside this run. Confirmation text stays withheld. No sample is replaced because it appears too short, clean, difficult or expensive. Historical exposure is carried forward as known/unknown; this is not fresh confirmation.

For each random target, first ask the preferred image-capable Qwen candidate to read the complete target image **without original OCR, static text, dictionaries, detector results or proposed corrections**. Record its transcription, inspected scope and uncertainty. This observation binds to the image/unit; it cannot supply an exact raw-text quote because it has not seen raw OCR. T50 must keep this distinct from repair-patch anchoring.

Then start a separate stateless request with the same image, original/static text, exact deterministic edits and diagnostics. Ask for proposed repairs and a structured audit, including apparent successful edits and text the detector did not flag. Bind repairs/findings to exact original quotes with host-derived positions. Do not provide the first response to this second request. The combined repair/audit is one configuration; its self-check is not an independently validated auditor.

For the two known failures, audit the fixed saved proposal under the new audit contract. Do not repeat the old repair request or salvage its result. Compare the new discrepancy report with the earlier exposed AI-provisional finding, not with invented gold. A chapter-number correction and preservation of printed repetition test consequential content that fluent prose or a dictionary can miss.

## Computer time and hard-stop limits

The proposed envelope is1,800seconds for the whole session, starting before fresh runtime checks, model loading, image acquisition and reporting:

- At most12requests, each at most120seconds:1,440seconds, or24request-minutes.
- Reserve360seconds, or6minutes, for checks, images, deterministic work and the report.
- One local model, sequential requests, zero retries or automatic substitutions. No extra warmup, token-count or compatibility inference calls outside the envelope.
- Proposed output cap1,500tokens per request /18,000total; proposed input cap6,000tokens including images per request /72,000total. Actual input/image fit remains a T55 prerequisite, not a measured fact.

Earlier18Qwen requests took a median69.23seconds each, with two timeouts near120seconds. That gives a reason to investigate this size, not a promise that all12will complete. Their inputs and per-attempt accounting differ; model loading and session overhead were not fully measured. [Exact timing provenance and bounds](design.json) preserve the distinction.

Before each request, require at least120seconds of remaining request allowance and at least150seconds until the session deadline, leaving30seconds for terminal records/reporting. If initial setup/images/token fit exceed360seconds, stop as not ready rather than improvise a shorter sample. Stop on missing/wrong/unclear images, invalid or incomplete responses, refusal, timeout, unknown usage, identity mismatch, exhausted budget or deadline. Keep all attempted/remaining units and unknown usage visible; a partial report is a feasibility outcome, not a completed quality evaluation.

**A client timeout does not prove that server computation stopped.** T53/T55 must establish and test how an owned request is stopped/observed before promising a strict30-minute computer shutdown. After an ambiguous timeout, launch nothing else and reconcile backend activity. This document supplies finite dispatch/wait bounds; it does not claim that the current runner already enforces backend cancellation. Do not stop an unrelated worker or restart a shared server to satisfy the clock.

## Images, text and processing

Use at most one verified crop per unit:7bindings and16MiB total image payload. Each target may contain at most6,000original characters and6,000static characters; context may contain at most2,000characters in each layer, complete or omitted. The frozen selected targets fit those bounds. If a whole unit needs another crop or cannot fit a reliable request, stop with an explicit blocker; no silent target truncation or easier substitution.

The five random targets have no image bound yet. The two challenge image identities are inherited and still need coverage/registration/legibility verification. Any separately authorized new image acquisition must fit the session/byte budget and has no automatic retry. This design performs no image fetch or reading. Existing source hashes, raw/static text and edit mappings remain immutable.

T52 can use deterministic lexical/pattern signals on these fixed units, preserving raw text and edit provenance. The image-only request sees none of those signals. The repair/audit pass sees them, and the host compares both AI observations with raw/static/derived text. Preserve disagreement and uncertainty instead of choosing the more fluent version. Token/span alignment and distinct input/output contracts remain T50/T52 implementation work.

## What this can tell us

If later authorized and run, report actual completed/invalid/timed-out pairs, structured proposed changes, provisional number/name/word discrepancies, disagreements, unflagged/apparent-success inspection, and measured CPU/model/image/time costs. Distinguish source-linked software checks from AI opinions about print. Detector-negative text and names/numbers remain in the audit scope; dictionary success does not imply correctness. If the random sample contains no particular category, say so; the known failures add diagnostic coverage without producing a prevalence estimate.

The image-only pass is a provisional comparison, not a reference transcription certified correct. Same-model errors are correlated even with separate prompts and hidden earlier responses. Agreement is not gold, and AI-only relative discrepancies cannot establish actual detector/auditor recall, verified repair efficacy/harm rates or corpus safety. The report should say exactly that, without manufacturing quality percentages.

The useful decision is narrower: can this request pattern finish on the machine, preserve source bindings, expose the known number/repetition failures, and identify a specific remaining repair/audit defect? Those observations can justify a targeted contract/runtime fix or a later independently checked sample. They do not close P0, approve canonical text or authorize full cleanup. Human readability, audio/TTS and trusted downstream search/metadata/answer quality remain unmeasured.

## Human effort and next steps

This first diagnostic requires **zero new human-review minutes**. It does not ask Stephen to undertake the T49 ceiling of516reader/adjudication minutes. That larger independent-reference design is deferred as an initial-run requirement; it remains relevant if verified quality claims are later sought. Existing HR-009/010 permission remains unchanged. A genuinely decision-changing dispute can lead to a separate small review proposal later, never an automatic extra round.

T60 completes design only. T50 must freeze the image-only versus quote-bound combined output contracts, T51 governs applicable workflow adoption, T52/T53 implement/check the path offline, and T55 must freeze actual images, provider/digest/capability, request identities, token fit, cumulative accounting and cancellation/stop behavior. A concrete authorized launch is still required before T56. The user's request to design a roughly30-minute option is not silently treated as permission to dispatch unknown requests now.

[Validation](validation.json) checks sample derivation, finite accounting, input identities, old-file preservation and scope/claim limits. [Luna review](review.json) is preparation review, not historical grading. Documentation-only work; last full code gate remains T44's643tests. No model/provider requests, new source scan, image fetch, independent reading, human packet or accepted historical label was created.
