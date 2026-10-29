# T79: exact request capacity screen, without inference

The two available saved-failure audits are too large in their current text serialization. D1 has 8,445 literal message tokens and D2 has 6,912, before image accounting. Both exceed the unchanged 6,000 input cap. This screen measures the actual five T78 request bodies, rather than repeating the earlier illustrative T55 counter. All seven sample rows remain present, including the two missing-image rows S3/S4.

| Unit | Literal system + user tokens | Proposed compact system + user tokens | Exposure |
| --- | --: | --: | --- |
| S1 | 3,321 | 2,542 | Human-feedback-conditioned primary |
| S2 | 1,265 | 1,268 | Human-feedback-conditioned primary |
| S3 | Unavailable | Unavailable | Missing source image |
| S4 | Unavailable | Unavailable | Missing source image |
| S5 | 1,186 | 1,087 | Selected unguided primary |
| D1 | 8,445 | 5,747 | Exposed saved-failure audit |
| D2 | 6,912 | 5,336 | Exposed saved-failure audit |

These are sums of separately tokenized literal messages using the matching installed tokenizer JSON and existing cached tokenizers 0.22.2, with added special tokens disabled. A joined-text diagnostic is also retained. Neither count is an authentic rendered/expanded backend request. Actual renderer framing, image preprocessing and image tokens remain unknown. The schema is measured separately as a grammar/transport component (1,451–1,567 literal tokens if tokenized as JSON); it was not silently appended to the prompt or counted as proof of backend schema treatment. Transport image base64 bytes are recorded separately from decoded image bytes and unknown native image tokens. Component counts are diagnostic and are not additive proofs of full fit.

## One lossless input proposal

The proposed versioned column format replaces repeated diagnostic object keys with a column list and complete rows, and replaces repeated route-reason prose with an indexed reason table. It retains every flag, quote, offset, identifier, reason, paragraph, layer, saved proposal and image region. It leaves historical strings unchanged. A short decoding instruction is included in each proposed prompt and in its measured count. Each proposed input restores to the exact canonical original T78 user-message bytes; five equality/hash checks pass.

This is one proposal, not a runtime implementation or accepted new input contract. The existing projection/compiler/host and T78 bytes are unchanged. No compact proposal can create a valid job or clearance under the current contracts. D1's remaining literal-text headroom is only 253 tokens, and D2's is 664; no positive multimodal-fit conclusion follows. Any implementation must version/rebind the changed contract, prompt and request identities, retain exact source evidence, and prove native fit separately. No target omission, truncation, sample substitution, extra call or raised ceiling is proposed.

## Output illustrations and limits

Fifteen authored illustrations pass both the exact per-unit JSON schema and existing host semantic/replay validator. Their filenames and [index](output-examples.json) identify them as illustrations. They are not returned model replies, fresh image readings or a mathematical minimum/maximum. The small incomplete examples honestly withhold readings; they demonstrate a failure envelope, not a productive result. Complete raw-copy/no-finding examples illustrate required fields and full-reading costs, not actual successful inspections. In particular, raw-copy S1/S2 deliberately leave the known human feedback unresolved and must never be used as passing quality outcomes.

Separate S1/S2 examples replay the already saved T74 source-specific proposed edits and full reading; S5 uses saved static edits only. The examples contain hypothetical inspection/self-check/finding values solely to measure size. They add no historical findings or independent verification. Their sizes are 868, 295 and 296 tokens. They do not establish that all supported errors have been repaired.

An audit illustration with one unresolved concern per target is 705 tokens for D1 and **1,515 for D2**, above the unchanged 1,500 output ceiling. The concern prose is fictional and deliberately does not identify a new historical discrepancy. This is evidence that a valid, fuller result can overflow, not proof that every valid result must overflow or that a cap increase is authorized. Shorter truthful responses may fit; additional findings or explanations may cost more. Successful output capacity remains unproved. No output-contract change is adopted or second serialization proposal prepared.

## Evidence and checks

[Component measurements](components.json) pin all five actual T78 request/schema/image hashes. [Tool identity](tool-identity.json) pins the preparation source, tokenizer package files and installed tokenizer bytes. [Preparation source](screen-source.txt) preserves the exact one-off procedure; it is evidence, not a new installed command or recurring workflow. The cached tool was reused without dependency installation or network access. [Compact proposal](compact-input-proposal.json) records five exact round trips and separate prompt/user sizes. [Validation](validation.json) retains the unchanged 6,000/1,500 caps, missing rows and false launch status. [Bounded Luna review](review.json) identified two provenance omissions; both were fixed and independently checked, including all fifteen output examples.

No model/API/server call, image fetch, dependency/model download, canonical edit, native trace or clearance was produced by T79. M5.2 remains partial; T55/T56 remain blocked on missing source images, authentic native preprocessing/parity, actual compatibility/stopping and now these concrete serialization/output-capacity concerns. Existing human approval and prior cumulative consumption remain unchanged. Repository implementation was unchanged by T79; the prior full gate922 applies until the separate T73 code gate completes.
