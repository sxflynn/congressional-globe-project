# M1 role protocol v2.1 status/schema correction

This immutable offline evidence version corrects the transport-schema mismatch found in v2-01. The frozen status vocabulary is `proposed`, `unknown`, `mixed`, and `needs_review`. `proposed` requires a supplied candidate cue and nonempty evidence. `unknown` requires a null candidate and permits only paragraph evidence. `mixed` and `needs_review` preserve the permissive candidate/evidence shape from v1; the host still requires every candidate and evidence alias to resolve to the supplied packet.

`schema.json` is the generic transport schema; `protocol.json` records status semantics, the generic unknown identity example, and source hashes. Tests validate representative values with Draft 2020-12 JSON Schema and independently through host validation, including malformed status shapes and packet-unknown aliases. `revalidation.json` retains exact saved reply text, hashes, prior v1 outcomes, validator/revalidator hashes, and the separate v2 outcomes for all four saved replies.

Revalidation used only saved inputs/replies:

```sh
uv run python -m congressional_globe.role_v2_revalidate \
  --preparation artifacts/role-alias-preparation-20261023-02 \
  --comparison artifacts/role-comparison-20261023-02 \
  --output artifacts/role-protocol-v2-20261025-02
```

The four-reply outcome remains three structurally valid and one invalid. This does not claim semantic correctness, source-image inspection, or human approval. The prior v2-01 artifact is unchanged.
