# T55: first-chunk readiness check

The approved AI run has **not launched**. Three newly selected passage crops are now cached and visually checked, alongside the two existing failure-example crops. Two other selected images could not be retrieved: the archive service timed out on both the original lookup and one deliberately bounded source-only recovery attempt. The original sample is unchanged.

This package records a **not-ready decision**, not a completed live-readiness gate. Your approval and workflow-review waiver remain recorded; the missing requirements are resources and implementation, not another request for the same permission.

| Unit | Assigned material | Image state |
| --- | --- | --- |
| S1 | One paragraph, part1/leaf526 | New crop cached, hash/registration checked and visually inspected |
| S2 | One paragraph, part2/leaf716 | New crop cached, hash/registration checked and visually inspected |
| S3 | One paragraph, part3/leaf1055 | Both metadata lookups timed out; no image received |
| S4 | One paragraph, part4/leaf83 | Both metadata lookups timed out; no image received |
| S5 | One paragraph, part5/leaf529 | New crop cached, hash/registration checked and visually inspected |
| D1 | Four previously exposed paragraphs, leaf1060 | Existing crop hash matches frozen selection; inspected |
| D2 | Nine previously exposed paragraphs, leaf741 | Existing crop hash matches frozen selection; inspected |

There are18assigned paragraphs across these seven units. No substitute passage or reserved confirmation text was used. Five available images cover16of those paragraphs. The [image records](image-readiness.json) distinguish source/registration/legibility inspection from a historical transcription or human quality grade. Neighboring print visible in the crop remains context, never an editable target. All five original hOCR and page-map files are present locally; their paths and sizes are recorded in [source resources](source-resource-paths.json). The absent resources are two remote image crops, not the original OCR files.

## What prevents launch

[Readiness decision](readiness.json) identifies four concrete conditions:

1. S3 and S4 still lack their selected source images. Their failed directories/events remain intact. The source-recovery bound is spent; no further fetch occurred in this step.
2. The T53 runner currently accepts declared offline test doubles only. An actual owned local HTTP adapter and response/usage mapping are still needed. Fake success cannot be relabelled as live integration.
3. Complete input fit is unverified. Image preprocessing, actual rendered messages, full diagnostics and the frozen saved proposals must be included; counting only text is insufficient.
4. Stopping and observing a real owned backend has not been proved. Cancelling the fake child tested in T53 does not establish control of the shared Ollama service. The client must not kill an unowned server or treat a client timeout as proof of no ongoing work.

T70 in the master is the independent implementation step that can proceed while the two image lookups remain unavailable. T55 remains blocked, and T56 cannot dispatch from this package. Actual launch must repeat fresh process/queue/lock checks; the snapshots here are dated observations, not continuing assurances of idleness.

## Model and capacity evidence

The installed server reports version0.40.8. Its existing `qwen3.8:27b-mlx` tag advertises vision and still has digest `5642e97495e1a088883805981563dcdc4a040c2f53388b7a41d1f24d3622cf7e`. The actual installed manifest bytes hash to that digest. The tag does not establish upstream model identity or productive-v2 transport behavior. Earlier JSON-object results remain historical evidence, not proof of the newly prepared schema path. Ollama's [official API specification](https://raw.githubusercontent.com/ollama/ollama/main/docs/openapi.yaml) describes image input and structured formats; that specification does not prove this installed MLX backend can complete these exact requests.

The local model includes a pinned tokenizer. A temporary `tokenizers0.22.2` counting tool read that existing local file; it downloaded no model and was not added to project/runtime dependencies. [Capacity measurements](token-capacity.json) count canonical authored example strings: primary no-finding outputs176–316tokens; the four-join S1 example818tokens; saved-audit no-finding examples390/810tokens. Those examples fit the candidate1,500output cap, but are not worst-case guarantees or returned AI readings. Every capacity-example JSON file is explicitly wrapped as authored planning data. No example was posted to the human desk as a model result.

The measured illustrative text portions are1,574–2,496tokens with the draft schema. These omit actual image handling, complete saved-audit proposals and full diagnostic projection. They are not completed token-fit records. [Image scenarios](image-token-scenarios.json) use the installed preprocessing configuration to illustrate a risk: D1's1,600×3,222image yields a5,050token native-grid scenario and7,518tokens when added to the illustrative text portion, above the candidate6,000input cap. Actual Ollama resizing/rendering remains unverified, so this is **not a measured server token total** or a categorical failure finding. It identifies what the next implementation must resolve. No ceiling was silently increased, image resized, target truncated or extra request added.

## Bounds, costs and validation

The approved prospective chunk remains five productive combined image+OCR requests plus two saved-failure audits, at most seven sequential calls,120seconds each,840request-seconds, planned360seconds setup/reporting and1,800seconds whole-session time, with zero model retries. These are prospective ceilings, not permission to launch with unknown fit or stopping behavior. The original T69 design and bounds are preserved byte-for-byte.

Source preparation made10IIIF HTTP attempts: six successful metadata/crop responses and four metadata timeouts. The first batch allowed up to10GETs and used8; the separately recorded [source-only recovery plan](source-recovery-plan.json) allowed up to4moreGETs and used2. There were no automatic retries, further source recovery, full-page archives or model downloads. [Costs](costs.json) keep source preparation separate from inference: roughly253known subprocess seconds excluding unmeasured S1 local preparation, plus retained individual HTTP timings. This incomplete preparation accounting is not a model-runtime estimate or a complete study cost. Earlier study usage and unknown timeout costs remain separate; no old allowance was reset or spent.

Real inference requests and newly generated historical readings are both zero. Production code is unchanged; the last full code gate remains809passing tests. This unit checks source/image hashes, exact model-manifest identity, selected scope, capacity-tool provenance, bounded fetch counts, preserved T69/T52/T53 artifacts and local documentation links. [Review dispositions](review.json) retain the bounded independent check. The master alone owns task status and subsequent work.
