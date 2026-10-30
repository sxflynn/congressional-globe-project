# T99: request and host agree about complete and uncertain replies

The user asked to fix the next demonstrated issue. The existing validator is unchanged. The new opt-in conformance-v4 schema and matching prompt now advertise its existing rule:

| Reading state | Text | Reason |
| --- | --- | --- |
| Complete | Entire nonempty target reading | JSON null |
| Incomplete or uncertain | JSON null | Nonempty explanation |

This remains the same text-reply-v3 reply contract and fields. Schema-artifact v4 adds two explicit object alternatives rather than changing what the host accepts. `prepare_text_host(..., conformance_v4=True)` and `compile_request_projection(..., conformance_v4=True)` select it. Default schema/prompt paths retain their original bytes. Host validation binds strict prompt prefix and strict per-unit schema hash in both directions; source-specific feedback can follow the prefix.

## Input → expected → actual software outcomes

The unchanged actual T90 reply supplies the expected complete sentence with `reason: "No further action required."`. The old wire schema accepted that combination while its host rejected it. Under the new advertised schema, both checks reject it for the same inconsistency. The original result stays invalid; it is not silently repaired or accepted.

Authored offline complete example: the same full sentence with reason null. Both new schema and host accept the shape and return an unreviewed source-linked proposal. This is not a new model result.

Authored offline uncertain example: incomplete coverage, null text and a concrete reason. Both checks accept the uncertainty, no proposal is produced, and status remains unresolved. Empty/contradictory variants fail. These shape checks do not verify reading accuracy.

## Evidence and limits

- Full `make gate`: **1,094tests pass**, including15new focused controls for the actual failure, complete/incomplete shapes, prompt/schema mixing, original bytes, source identity and request selection. Ruff, ty and complexity≤5 pass.
- Original T97 S5 prompt/schema/body reconstruct byte for byte using the recorded host/code identity. Original source/image/static/target fields and source/feedback/bracket/number guards remain unchanged.
- The exact stricter S5 candidate request, prompt, schema, host, projection, resource closure and local outcomes are saved here. It uses the existing installed model name/output ceiling. No token-fit, live readiness, extra call or provider enforcement is claimed.
- Bounded Luna review identified prompt-version ambiguity and mixed prompt/schema acceptance; both are corrected and checked. Native provider enforcement of `oneOf` remains untested.
- HR-013v8 presents input, expected reply shape and actual software outcomes with4evidence comment boxes plus an overall comment. Isolated AppTest/render checks have no exceptions; source/model/transcription spans remain plain, with glossary help in surrounding prose. The scan URL is copied from verified HR-013v7, not reconstructed. No Computer Use/browser/device interaction.

All actual provider calls for T99: **0**. Both prior S5 slots remain spent and their raw results unchanged. A later actual verification needs separately bounded authorization and exact code/request/runtime bindings; no additional offline helper inventory is needed to explain this fix.
