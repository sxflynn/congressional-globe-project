# First actual S5 result: returned, stopped, invalid

The approved single S5 request ran once. The backend returned a complete JSON response, then the owned server and its child stopped. The host rejected the response, so there is **no valid clean-text export**. The raw reply, failure and usage remain unchanged; S5 is spent and will not be retried automatically. The six other original units remain pending.

The measured cold cycle was **53.34 seconds**, including local model-file verification, startup, request and stopping. Qwen reported **1,391 input / 762 output tokens** with a normal stop, below the1,500output ceiling. These reported counts do not prove complete native image/text accounting. The explicitly approved6,000input reporting threshold was not exceeded by the reported count; authentic native fit remains unknown.

The backend separately reported45.08seconds total:6.01loading,11.55prompt evaluation and27.51generation. From the frozen session start through the terminal receipt was102.77seconds, including49.44seconds before the client lifecycle. These timing categories overlap; do not add them. Earlier offline implementation time, full study wall time, energy and human review cost remain unknown. There was1model call,1owned server start,0retries,0new image fetches and0requested model/dependency downloads. Two nonloading shared-service metadata GETs and bounded logs/process/queue checks were separate operator checks, not inference calls.

## What failed

The first host rejection is `whole-paragraph anchor has no quote`: the returned finding declares a whole-paragraph anchor while also supplying a quote, which violates that contract. Additional direct observations from the unchanged reply are saved in [diagnostic.json](diagnostic.json):

- It declares `no_finding` while returning a finding and a patch.
- It proposes a repair with `image_unclear` as its evidence basis, while its prose claims clear print.
- Its full reading joins `recom- mended` to `recommended`, but its only patch repairs `on- Appropriations`. Replaying that patch on original OCR leaves `recom- mended`; the returned full reading is therefore not reproducible from its patches.
- It claims a complete self-check while omitting four required categories and retaining a concern.

The parent inspected the cached target image. The proposed full sentence appears to match this short printed target and preserves `non-concurrence`; neighboring sentences were not copied. This is a source-inspected provisional observation, not blinded gold or a quality rate. The system correctly refuses to accept fluent full text when its source-bound edits and status are contradictory. No source or accepted ledger changed, and no repaired copy of the rejected model reply was created.

## Initial conditional collection timing

The collection has296,995paragraphs. These scenarios assume **one paragraph per request, the same53.34-second cold cycle, and a1%audit of paragraphs not routed for repair**. Routing rates are assumptions, not detector measurements. They exclude source acquisition, larger-passage overhead, human review and software development. The final column illustrates an additional25%rework workload; it is not permission to retry.

| Assumed repair routing | Attempted requests incl. audits | Cold-cycle attempt time | With assumed25%rework |
| --- | --: | --: | --: |
| 10% | 32,373 | 480 hours / 20.0 days | 600 hours |
| 25% | 76,477 | 1133 hours / 47.2 days | 1416 hours |
| 100% | 296,995 | 4400 hours / 183.3 days | 5500 hours |

That is approximately20–183continuous machine-days for the illustrated attempted-processing scenarios before extra rework. This is **not a forecast of successful cleanup**: the actual valid-result count is0of1. If that failure rate persisted, successful cleanup would not finish. Larger passages, batching, persistent loading, actual routing/audit rates and valid-response yield have not been measured; no observed range for those unknowns exists. Local inference has no measured per-call API fee here; energy/hardware cost remains unknown.

## Limits and next action

[Report/accounting](report.json), [unchanged terminal result](run/result.json), [exact freeze](freeze.json), [source scope](source-scope.json) and [implementation/checks](implementation.json) preserve identities, costs and unknowns. The receipt and independent process check establish the observed normal-completion/owned-termination path. They do not establish forced timeout cancellation or arbitrary-crash stopping. General T55 native readiness, S3/S4 images, audit capacity, independent quality, P0 and M6/M7 remain open.

The smallest next question is whether a minimally revised prompt/schema can enforce consistent anchors/status/evidence, all edits against raw OCR, and complete self-check fields. Prepare that change offline against this immutable failure and existing synthetic controls. Any further real attempt requires its own exact bounded scope; this result grants no second S5 call.
