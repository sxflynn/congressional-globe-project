# T13: role-v2 transport specialization repair

2026-10-26, OpenCode DeepSeek V4.1 Flash. Repairs the existing role provider specializer for the frozen `role-result-v2` schema. This is offline contract engineering only: no provider/model calls, downloads, source edits or human labels. M1 remains PARTIAL because live backend acceptance is still unproved.

## Research behavior

A researcher trying to identify an unnamed speaker needs a result that can cite a paragraph without inventing a person. Before this repair, every role-v2 request failed in the local adapter with `KeyError: 'properties'` before any request was sent, because the frozen schema uses `oneOf` status branches with `allOf` field groups while the specializer expected one flat `properties` object. That defect prevented the v2 contract from being offered at all, even offline.

The repair lets a request carry packet-bound alias lists into every status branch. A model can then choose only supplied paragraph targets and evidence, supplied candidate cues and controlled role/status values, while each branch keeps its own frozen status shape: `proposed` needs a cue and evidence, `unknown` needs a null candidate, and `mixed`/`needs_review` keep the permissive v1 shape. The generic schema is copied, not edited, so later requests do not inherit one packet's aliases.

## Implementation

[Module](../../src/congressional_globe/role_provider.py) now detects the role-v2 `oneOf` items, specializes each branch's shared `allOf` fields and preserves the branch-specific `const`, `pattern`, `type` and minimum-length constraints. Role-v1 and date specialization paths are unchanged.

This binds `candidate_id`, `target_ids`, `evidence_ids`, `role` and `status` to the exact packet. The host validator in [role_v2.py](../../src/congressional_globe/role_v2.py) remains the authority for alias kind, unknown-candidate and duplicate rules; the transport schema does not add `uniqueItems`, so duplicates are deliberately caught by host validation rather than silently accepted.

## Limits

**Live backend compatibility remains BLOCKED/unproved.** Fake-client tests prove that the existing OpenAI Responses and Ollama chat envelopes carry the specialized schema and that a synthetic result passes host validation. They do not prove that a remote constrained-schema engine accepts `oneOf`/`allOf`, nullable type unions or every enum. The Ollama adapter still sends `json_object` with schema instructions rather than a native grammar. No remote schema check, model call, launch readiness or new execution wrapper is claimed, and no inference is authorized.

The frozen role-v2 schema and protocol are unchanged; the generated schema was checked equal to the frozen artifact. Historical role-v2 revalidation results were not rerun. No canonical labels, source images or human decisions changed.

## Checks

Six new tests in [test_role_provider.py](../../tests/test_role_provider.py) cover all four status branches under Draft 2020-12 and host validation, serialized branch copies, unbound/wrong-kind/duplicate rejection, both fake-client request envelopes, and preserved raw/incomplete/refusal behavior. The former blocker assertion in [test_scoped_dates.py](../../tests/test_scoped_dates.py) now verifies specialization succeeds without mutating the generic schema.

Focused role/date tests: **53 passed**. Full required gate: **511 passed**, with Ruff format/lint, ty, complexity≤5 and Markdown formatting. [Gate log](gate.log).
