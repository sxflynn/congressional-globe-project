# T50: image-reading, repair and audit contract draft

A researcher must be able to distinguish what the image appears to say, what a model proposes changing, and exactly which original words support that proposal. This draft defines those records for T60's first small study chunk. It provides strict typed shapes and proposed host checks, not implemented validators, working dispatch, source readings or approved historical corrections. [Master task](../../MASTER_PLAN.md#ordered-task-queue).

## Three roles, with different evidence

| Role / reply contract | What the model sees and returns | Host meaning |
| --- | --- | --- |
| `image_only_observation` / `ocr-image-observation-v1` | Verified bitmap and short target/context region aliases only. One transcription/inspection record per target, with uncertainty and image suitability. | A tentative image reading bound to frozen image/unit/request identities. It cannot cite unseen original OCR or provide raw positions. It supplies no raw-support bindings or derived corrections. |
| `combined_repair_and_audit` / `ocr-repair-audit-reply-v1` | Same image plus original/static text, exact deterministic edits and diagnostics. Returns inspected scope, discrepancies and optional exact-quote-bound repair proposals. | Host derives positions in original text; proposed readings and resulting mappings remain unreviewed. Same-request self-audit is not independent verification. |
| `audit_saved_proposal` / `ocr-repair-audit-reply-v1` | Image plus original/static material and the exact frozen saved proposal. Returns discrepancies/uncertainty, with no repair patches. | A new audit request, not a replay of the old repair or permission to rewrite/salvage its stored answer. |

The two primary passes use separate stateless conversations; the later request never receives the earlier image-only reading. The same model can make correlated mistakes, so agreement never establishes gold or actual accuracy. Source text/model prose are evidence, not instructions to the worker. No first-pass output, reference answer or historical failure grade is included in an audited provider packet.

## Typed boundaries and identities

| Draft schema | Boundary |
| --- | --- |
| [Host input](host-input.schema.json) | Strict immutable-payload design: raw/static/saved layers, source aliases/hashes, exact ledgers, diagnostics/resource versions, one image's source/geometry/registration evidence and prompt/schema/code/model/sample/budget identities. Packet hash covers canonical payload JSON, excluding its own hash field. |
| [Image-only provider input](image-only-input.schema.json) | Closed allowlist containing only contract/unit/image aliases and target/context crop regions, with the bitmap attached separately. No original source identifiers, raw offsets/text, diagnostics, lexicons, proposals or previous conversation. |
| [Repair/audit provider input](repair-audit-input.schema.json) | Explicit role plus the frozen original/static/diagnostic material and saved proposal only when permitted. No separate image-only observation. |
| [Image-only reply](image-only-reply.schema.json) | Completeness, suitability, transcription and uncertain transcript wording per target. Any uncertain quote is anchored only within its own tentative transcription, never original OCR. |
| [Repair/audit reply](repair-audit-reply.schema.json) | Complete inspection accounting, findings, original quote anchors, affected layer/quote, proposed reading, evidence basis and optional patches. No model offsets. |
| [Host export](host-export.schema.json) | Raw reply/request/payload/model/schema/image/diagnostic/source-layer fingerprints, original parsed proposal, semantic outcome, host-derived raw/layer positions and reversible derived proposals. Always unreviewed AI evidence. |

These are Draft2020-12 JSON Schemas with all object keys required, explicit nullable values, closed extra-field rules and finite arrays. [Host rules](host-rules.json) specify their future strict Pydantic v2 model mapping and the cross-field/source checks JSON shape alone cannot establish. Hashes for source text use exact UTF-8; object hashes use the documented canonical JSON encoding. Image hashes cover actual bitmap bytes. Freeze the actual provider request bytes independently before transport.

Existing reading models already provide reversible raw edits, image-span checks and unique quote binding; T35 similarly separates model quote text from software positions. The T3 risk artifact currently contains only a heading/status notice, so this draft does not invent substantive fields or claim to implement a missing risk schema. Its requirements come from the current evaluation method, T60 and the inspected reading contracts. Exact inspected-file identities are recorded in [validation](validation.json).

## Position binding and separate layers

The model supplies an exact `raw_quote` and a short paragraph alias. Software resolves that alias through the frozen original source/hash registry, finds the quote exactly once within that paragraph, counts overlapping matches and derives Unicode half-open positions. It does not normalize whitespace/case/Unicode, fuzzy-match, choose the first occurrence, or accept model-authored offsets. Missing, repeated, out-of-scope or incompatible evidence is rejected. Extend the quote to make it unique; do not guess its location.

The proposed replacement is a separate string and need not occur in original OCR. An audit of static/saved wording also returns an exact affected-layer quote. The host binds that quote in that specific frozen layer, uses its reversible edit map to establish original support, and records both sets of positions. A static offset cannot be treated as an original offset. A whole-paragraph uncertainty anchor may name unclear/missing print without fabricating a precise quote, but cannot by itself authorize a replacement patch.

Every patch must lie inside its linked finding's raw support and match the same paragraph/image; no-op, overlapping, disputed or cross-paragraph relocation is refused. Supported proposals are replayed from raw, preserving explicit unchanged/replacement mappings. The saved static layer and earlier model outputs stay immutable. A finding about a harmful earlier edit does not make the opposite correction automatically accepted.

## No finding is different from incomplete or unresolved

A returned record must explicitly account for every target once. Context is not an editable/scored target. Missing/duplicate aliases and omitted inspections are invalid; `not_inspected` is an honest explicit state. The host checks actual image source/hash/geometry/registration evidence; a model saying “clear” cannot establish a correct image binding. Draft input can contain missing/unknown image evidence for preparation, but preflight must block a live send.

For image-only observations, partial/not-inspected targets make the result incomplete. Complete inspection with uncertain wording or unsuitable imagery is unresolved; otherwise it is a complete model observation, still provisional. Complete inspection does not imply source certainty. A null transcript means nothing readable, not blank historical print.

For combined/audit replies, partial/not-inspected targets mean incomplete; unsuitable evidence or unresolved findings mean unresolved. Both allow discrepancy reports but require no patches and an explanatory reason. A findings result needs findings; a no-finding result requires all targets inspected completely with clear images and empty findings/patches. Audit-saved-proposal always forbids patches. These consistent states are semantically valid records; T60 nevertheless stops on incomplete/unresolved. Invalid schema/source binding is a separate rejection. No-finding means no issue reported in the stated scope, never error-free text or safe automatic acceptance.

Six [synthetic illustrations](examples.json) cover a plausible wrong year, a correct rare name/place, a harmful static hyphen join, missing/irrelevant/wrong-image behavior, a saved proposal deleting printed repetition, and an apparent no-error real-word substitution. Each includes image-only and repair/audit reply shapes. They have no image bytes and cannot pass launch preflight. Their constructed print and expected failure behavior are software-design examples, not new source readings, human grades or live model results. Negative variants specify required later host checks; T50 does not implement or execute those semantic checks.

## Minimal integration and recovery proposal

[Adoption proposal](adoption-proposal.json) specifies extending existing typed reading adapters, exact request materialization, shared sequential lock, raw-first journal and source-linked export. It recommends no new provider, scheduler, SDK, dependency or command. Separate new role/contract identities prevent old journals, schemas or rejected replies from being silently reinterpreted. This is the concrete proposal for T51 evaluation, not an actual independent adoption verdict.

Host projection must be checked byte-for-byte for forbidden original/diagnostic/previous-response leakage. Image-only and later combined roles remain distinct even when using one model. Unknown token/image usage or an ambiguous in-flight send blocks further dispatch; saved compatible raw replies are validated/reused without another send. T53 must prove fresh-process recovery at before-send, ambiguous-send, raw-saved and terminal boundaries with fake callers before any real integration claim.

T60's12slots/24request-minutes+6overhead,120seconds per call, input/output/image caps, zero retries and cumulative study accounting remain in force. Target/static sums are capped at6,000characters each and context sums at2,000each per unit, not per paragraph. One image per unit and at most32paragraphs are generic shape limits; actual packet aliases and bounds are narrowed to the frozen sample. Nine targets in a saved failure case do not license extra calls or output tokens. Exact token fit, real provider/schema support, fresh process/queue/log/lock checks and backend cancellation/observation still require T55 readiness. A client timeout does not prove the model stopped.

## Checks and next executable work

T50 checks generic schema validity, closed object fields, local references,18illustrative role-shape validations across six cases, forbidden extra offset/input fields, local links and immutable prior inputs. These checks establish draft structure only. No live request, new image, corpus scan, production module, reference reading or accepted ledger changed. No full code gate is rerun for this data/document unit; last evidence remains T44's643tests. [Luna preparation review](review.json) is not the human-run T51 adoption verdict.

T52 deterministic-only library implementation becomes ready with this draft and the existing T47–T49 inputs; it does not need T51 approval because it adopts no orchestrated workflow. T51 can prepare/obtain its actual independent verdict in parallel with that offline work. T53 workflow integration remains blocked on T51/T52. M1/M2/M5 and P0 remain incomplete; this unit completes requirements drafting only.
