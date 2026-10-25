# M1 role protocol v2 offline revalidation

Protocol v2 permits paragraph-only evidence when a role is unknown, while requiring `candidate_id: null`; an unknown attribution cannot name or resolve a person. Proposed roles still require a supplied speaker/person cue alias plus evidence. The JSON Schema handles the status-dependent shape, and host validation binds each alias and controlled value to its frozen request.

`schema.json` is the generic transport schema. `protocol.json` records the policy and a generic unknown-speaker example. `revalidation.json` preserves exact saved reply text, its hash, the prior v1 status/error, source artifact hashes, validator code hashes, and separate v2 outcomes for the four Mini/Qwen replies. Nothing here changes v1 artifacts, canonical text, or human labels.

Offline command used:

```sh
uv run python -m congressional_globe.role_v2_revalidate \
  --preparation artifacts/role-alias-preparation-20261023-02 \
  --comparison artifacts/role-comparison-20261023-02 \
  --output /tmp/role-protocol-v2-replay
```

Result: three structurally valid and one invalid under v2. Qwen's previously invalid unknown floor-speaker row citing its supplied paragraph is now structurally valid. Mini's two proposed person-mention rows with null candidates remain invalid; the reply is not partially salvaged. This is structural protocol evidence only, not semantic/source validation, human approval, or a request to retry models.
