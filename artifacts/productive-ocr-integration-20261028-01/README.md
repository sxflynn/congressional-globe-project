# T53: productive OCR repair and recovery, tested offline

A researcher should be able to see the complete proposed passage and every supported change, while keeping the original OCR intact. This implementation checks that the proposed reading is exactly what its listed changes produce. It also checks source identities, the registered image, target versus context boundaries, saved comparison text and uncertainty states. These software checks cannot establish that a model read the print correctly.

The human explicitly approved the workflow and waived independent adoption review after oral discussion. [Exact approval and run limits](../ocr-workflow-approval-20261028-01/approval.json) remain separate from any independent AI review. The discussed real diagnostic has approval, but actual readiness remains T55. This unit made zero real provider requests and produced no new historical readings or human review packet.

## What is implemented

Five modules implement the strict productive-v2 host/reply contracts, original-text binding, execution and stop-observation checks. Nested objects reject extra fields and invalid states. Wordings and positions are never silently normalized. Hashes bind original/static/saved text, ordered edits, registry evidence, image bytes/dimensions, prompt/schema, implementation, session bounds, model identity and token-fit evidence. The image's registered source/geometry and external inspection evidence are checked separately from a model's suitability claim. The supplied registry is a trusted external evidence boundary; fabricated registry records cannot become historical proof merely by having valid hashes.

Provider projection carries the assigned targets and separately marked surrounding context. Context can help interpretation but cannot receive corrections. Productive replies must contain exactly one full reading and complete inspection/self-check per target for a completed result. Audits of saved failures remain readings-free and patches-free. Incomplete or unresolved productive replies withhold full readings and edits, with reasons. A no-finding reply returns unchanged original text and complete checks; it does not certify correctness.

Finding quotes bind uniquely to original OCR. Static/saved-layer quotes map back to their supporting original intervals. Patches must match their findings, avoid overlap/unresolved concerns, and replay from raw into the full returned reading. The old static and saved proposal layers stay unchanged. Bracket annotations and literal-preservation concerns are exported alongside source-supported proposals; bracket fidelity and real event meaning remain unverified.

The runner reuses `RoleRunStore` without migrating old journals. It freezes exact caller bytes and uses the shared Ollama request lock without waiting indefinitely. Requests, raw responses and usage are durable before parsing. A separate immutable record binds the owned-worker stop observation to that exact request and raw response. Missing observation blocks recovery instead of assuming the backend stopped. Known usage, unknown usage, cumulative limits, output ceilings and the frozen session deadline survive process restart. There are no retries or implicit new tasks.

This version explicitly accepts declared offline test doubles only. There is no default HTTP provider adapter, new CLI, scheduler or SDK. Synthetic token-fit records are labelled synthetic and cannot serve as actual model-tokenization proof. Future real dispatch needs its actual adapter and fresh runtime/model/queue checks under T55/T56, using the already recorded run approval.

## Proof and limits

The [fake results](fake-results.json), [frozen fake requests](frozen-fake-jobs.json), [session bounds](fake-session-bounds.json), [invented registry](fake-registry.json) and `journal/jobs.sqlite` show two constructed targets completed and then reused with zero extra sends. The white PNG contains no historical print; invented registry/legibility data tests the evidence checks, not actual image quality.

[Fresh-process observations](recovery-observations.json) cover six real SIGKILL boundaries:

- Before the durable claim: pickup can send the pending jobs once.
- After the claim or after send: ambiguous work blocks further dispatch.
- After raw persistence but before stop observation: the reply remains saved, while missing stop proof blocks reuse and new sends.
- After raw persistence plus stop observation: pickup validates the saved reply without resending.
- After terminal persistence: pickup reuses the finished result without resending it.

The full repository gate passes809tests, including57new cases, with formatting, lint, types and complexity≤5. [Gate output](gate.log.gz) is retained. Earlier pre-inspection software proof is preserved under `checkpoints/before-inspection-proof/`; it is superseded by the current root-level proof and is not new historical evidence.

The focused suite also times out a real owned fake subprocess, terminates it and observes exit. This proves the injected process-control path only; it is not evidence of actual Ollama/Qwen cancellation. Deadline checks run immediately before dispatch and after observing stop; exceeding the deadline preserves evidence and blocks further work.

Tests cover wrong images/resources/registration, exact saved-proposal record substitution, malformed or unordered edits, missing/foreign/duplicate target records, target/context separation, contradictory readings, incomplete audits, unresolved paragraph-wide uncertainty, hidden request fields, mismatched token-fit/model identifiers, clock/deadline boundaries and unknown usage. Eight authored T69 cases are exercised. A coherent wrong-name proposal can still pass structure while disagreeing with constructed print: quality is explicitly not established by validation. Missed words, wrong numbers, harmful bracket/name/repetition changes need independent print comparison, not a software success label.

[Validation](validation.json) and [review dispositions](review.json) distinguish implemented contracts, fake transport/recovery proof and remaining live-readiness gaps. [Host schema](host-schema.json) and [reply schema](reply-schema.json) describe the implemented models. The unchanged T69/T52 manifests are checked against their original bytes. The draft host-rules phrase “7 bindings” conflicts with D2's nine frozen target paragraphs; the authoritative schema's32bindings per packet is retained, with no sample substitutions or extra request slots.

T55 must still freeze exact cached image/registration/inspection evidence for all seven assigned units, actual provider/schema compatibility, model name/digest, tokenizer/image/output fit, full projected requests and actual owned-backend stopping/observation. No claim of a proven30minute real backend stop, historical efficacy, accepted correction, P0 closure or corpus readiness follows from this unit. The original OCR and accepted historical records remain immutable.
