# T69: one productive OCR repair request

HR-011 asked that one narrowly scoped image request fix both the misread word and the misread number, rather than showing only a number fragment. This revised **draft** makes the complete assigned passage and its exact changes the primary output of one combined request. It does not implement a runner, establish that Qwen can complete the work, or dispatch any inference. [Master task](../../MASTER_PLAN.md#ordered-task-queue).

## What one request must produce

The default role is `productive_repair_and_self_check`. It receives the frozen image, original/static OCR, exact static edits and diagnostics, and target/context boundaries. It returns one inspection, complete proposed reading and structured self-check for every assigned target, plus findings and all source-bound patches. Every supported word, number or other error is in scope, including text not flagged by the detector and apparently successful static edits. Printed brackets, repetition, names and historical spelling must be preserved unless a specific source-supported repair is proposed. No image-only pass is required by default.

The [joint example](examples.json) includes **both** `Tlie`→`The` and `GCO`→`660` in one reply. Its complete proposed text is exactly the replay of those two changes on the unchanged original paragraph. This example was authored from the human's request; it is not an observed model reply, a complete new source transcription or an accepted corpus correction. It does not append neighboring `labor.`. Real whole-target coverage, print omissions and target endpoints still require image/geometry validation; they cannot be decided by automatically extending an OCR paragraph into nearby print.

The model supplies exact unique original quotes, not character offsets. Software must derive positions, reject ambiguous/overlapping/no-op or foreign-target patches, bind each finding and image, replay from **raw**, and require byte-for-byte agreement with the full proposed reading. A full reading with an unexplained difference is invalid, even if it looks fluent. Contradictory finding/patch replacements are invalid. A `no_finding` result must return unchanged raw target text and complete inspection/self-check with no concerns; this is a limited model report, not verified correctness.

For incomplete inspection or unresolved evidence, return withheld/null readings, explicit reasons and no patches. Do not fabricate a complete reading or sell partial output as a successful repair. Context is never an editable target. Missing, wrong or unregistered image evidence blocks readiness independently of the model's claim that an image is clear. Every valid proposal remains unreviewed AI evidence.

The two saved-failure audits retain a separate, productive diagnostic purpose: report whether the frozen old proposal contradicts the image, including consequential numbers and printed repetition. `audit_saved_proposal` requires empty `patches` and `target_readings`; it does not rerun, salvage or alter the old repair. It still supplies findings, uncertainty and full inspection/self-check coverage. Any additional independent image/transcription comparison needs a separately named study question and justified incremental cost; it is not an automatic extra call.

## Versioned files and boundaries

| File | Draft boundary |
| --- | --- |
| [Host input](host-input.schema.json) | `ocr-productive-repair-host-input-v2`; immutable source/layer/image/resource/sample/model/prompt/budget identities. |
| [Provider input](provider-input.schema.json) | `ocr-productive-repair-input-v2`, with explicit reply identity and closed role-specific input projection. Fixture oracles/human expected answers must never leak into a live request. |
| [Reply](reply.schema.json) | `ocr-productive-repair-reply-v2`; adds required full `target_readings` and per-target `self_check` to source-bound findings/patches. |
| [Host export](host-export.schema.json) | `source-bound-productive-ocr-repair-v2` and binding-v2; preserves original request/reply/usage and keeps semantic validation separate from historical quality. |
| [Host rules](host-rules.json) | Prospective strict Pydantic v2 mapping and cross-field/source/replay/state/registration/recovery requirements. These are not production Python validators. |
| [Prompts](prompts.json) | Single productive repair and two saved-failure audit instructions; no hidden previous response and no default image-only role. |
| [Sample binding](sample-binding.json) | Exact seven preserved T60 units and new five-repair/two-audit request order; host bookkeeping is not provider input. |
| [Bounds](bounds.json) | Frozen prospective ceilings and explicit unknown-fit/overflow/stop behavior. |
| [Adoption proposal](adoption-proposal.json) | Revised concrete T51 scope/risks for the existing runner, with no new SDK, scheduler, provider, dependency or command. |

The default remains the same five T60 primary identities and two saved-failure units. It proposes at most7 sequential calls×120seconds=840request-seconds, plus360planned setup/report seconds:20planned minutes within the existing1,800second whole-session cap. No retries, extra warmup/compatibility calls or automatic use of spare time. The joint/bracket illustrations are **not** added study targets. The remaining20primary and10confirmation targets stay outside this chunk. Cumulative old costs and unknown timeout usage remain in the eventual report; a new design is not a spending reset.

Input6,000tokens including actual prompt/schema/image accounting and output1,500tokens are **candidate ceilings**, with at most42,000input/10,500output across7slots. Full proposed text is additionally capped at6,000codepoints per target. These limits do not establish that a whole result fits. Actual model tokenization, image costs, provider transport/schema support and worst-case usable output remain unknown. Serialized fixture byte lengths in validation are not token measurements.

If a frozen whole target cannot fit, block it with the measured reason. Do not truncate the reading, omit patches/inspection, choose an easier sample, raise the ceiling, retry or split it into another call silently. Any revised scope/bound requires a deliberate new readiness identity and applicable authority. Client timeout is not proof that backend work stopped; T53/T55 must implement and prove owned-request cancellation/observation before promising a strict machine-runtime stop.

## What the offline checks prove

Four Draft2020-12 schemas were checked. Eight bounded authored cases reuse the six T50 scenarios and add the human-requested joint repair and a synthetic bracket/reaction control. Their replies and one synthetic provider-input shape pass. [Validation](validation.json) records24negative controls:19are rejected by shape or the disposable fixture-rule sketch; five remain structurally coherent but disagree with the constructed expected print. Checks include missing/duplicate/foreign full readings, legacy/extra-offset fields, unreported adjacent text, overlap/no-op/ambiguous quotes, inconsistent findings, wrong role, unresolved patches, incomplete self-check and output overflow.

A response can repair `GCO` but leave `Tlie` consistently in both patches and full text. Its replay is valid, yet it fails the joint quality fixture. Likewise a coherent proposal can delete brackets or printed repetition, alter a correct rare name, or substitute the wrong number. The constructed-print controls expose those failures **without claiming that replay validation detects them in real images**. Same-request self-check is correlated model evidence, not an independent auditor or gold reference. Real efficacy, missed/harmful-error rates and source fidelity need the applicable independent evidence and criteria.

The wrong-image control supplies a simulated failed host-preflight flag, separately from a model's unsuitable-image claim. This is a rule illustration, not executable proof of actual bitmap/registration verification. The synthetic10×10provider geometry and absent image bytes are never launch-ready. The joint image hash is a reference only; no new image was read or fetched for this unit.

The disposable `/tmp/t69_check.py` performs only P1 fixture replay/state/oracle checks; it is not a general host validator or a new adopted workflow. Production alias/layer/hash/geometry binding, all state interactions, fresh-process journaling/recovery, provider compatibility, token fit and dispatch still require T53/T55. No full code gate is rerun for these documents/schema drafts; the last production-code gate remains683tests.

Original T50/T60 files and all human answer/packet bytes remain unchanged; [prior input hashes](prior-inputs.json) and the final manifest make that preservation checkable. T69 completes revised contract preparation only. T51 still lacks its actual independent human-run verdict or explicit override; HR-011's “See above” supplied neither. P0/full-run and live-call authority remain open. T67 bracket annotations and T52 deterministic-only library work remain independent READY work.
