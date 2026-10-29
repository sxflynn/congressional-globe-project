# T80: strict offline diagnostic codec

The T79 column proposal is now a tested library. It encodes each original provider input as a compact diagnostic table and decodes it only when the entire restored input equals a separately held original with a matching canonical SHA-256. All five available T78 inputs restore exactly and reproduce the T79 proposed compact bytes. S3/S4 remain explicit missing-image rows in the unchanged seven-unit sample.

This completes the offline codec task. The existing request compiler, host, fit, job and transport paths are unchanged and do not import this module. No compact input has been adopted for production or sent to a backend. The image-fit and output-capacity concerns remain unresolved.

## Contract and trust boundary

`productive_ocr_compact.encode_provider(original_json, expected_provider_sha256)` validates the original input and independent hash, then returns canonical JSON using `ocr-productive-repair-input-v3-column-proposal`. `decode_provider(compact_json, original_json, expected_provider_sha256)` validates both shapes, restores the diagnostic objects and requires exact equality with the canonical original. The caller must obtain the original and hash from trusted evidence separately. Supplying both from an attacker-controlled payload cannot establish authenticity; this library does not independently authenticate historical sources or replace host/resource validation.

Only diagnostic representation changes. Every original signal field becomes a column; repeated route-reason prose becomes an indexed dictionary. Rows preserve their original order. Raw/static source strings, punctuation, Unicode composition, static edits, target/context regions, flags, detector identities, negative-target declarations and saved-audit evidence remain unchanged. Canonical JSON preserves source strings but standardizes object-key order and transport whitespace; the five actual frozen inputs were already canonical, so their restored bytes match exactly.

The Pydantic v2 models forbid extra or missing fields and coercion. Columns must equal the canonical ordered Signal fields. Row arity is exact, ordinary cells use the existing strict Signal types, and reason indices must be integers in range, excluding booleans. Reasons must be sorted, unique, nonempty and fully used. An empty signal set has empty columns, rows and reasons. Duplicate JSON object keys and nonfinite numeric constants are rejected before model validation.

Resource bounds are explicit: two MiB of serialized UTF-8, nesting depth32, at most128signals/reasons and32paragraphs. Existing aggregate source-layer limits remain6,000codepoints for targets and2,000for context. These are offline parser/shape protections, not increased token or image budgets. Oversized inputs fail without truncation. The supplied JSON schema describes structural constraints; semantic table validation and the independent-reference comparison require the library functions.

## Exact evidence

[Unit results](units.json) bind each actual T78 request hash, original provider hash, compact provider hash and restored provider hash. Each unit directory contains the compact and restored canonical bytes. An independent standard-library inverse rebuilds signal objects from the columns/reason table without calling the decoder, and matches all five originals. T79's compact proposal matches all five encoder outputs byte for byte. Its existing literal token counts are carried forward by those identities; tokenization was not repeated and no native fit is inferred.

| Unit | Original provider bytes | Compact provider bytes |
| ---- | ----------------------: | ---------------------: |
| S1   |                   9,534 |                  5,425 |
| S2   |                   1,834 |                  1,474 |
| S5   |                   2,770 |                  1,921 |
| D1   |                  29,340 |                 16,036 |
| D2   |                  22,917 |                 14,992 |

The five fixtures cover16targets with S1/S2's actual feedback-conditioned inputs and D1/D2's exposed unreviewed saved-proposal audits preserved. These are source-bound input transformations, not new historical readings or quality labels.

[Proof source](proof-source.txt) preserves the one-off evidence procedure. [Proof report](proof.json) pins that procedure, implementation, tests and structural schema, and records bounds and false launch/adoption status. [Validation](validation.json) records the final checks and unchanged production-path identities. [Bounded Luna review](review.json) records independent findings and their dispositions.

## Validation and remaining readiness

The67focused cases cover exact frozen-input round trips, empty diagnostics, Unicode/context/saved-proposal preservation, malformed columns/rows/reasons, strict cell types, unknown/missing fields, wrong contracts, duplicate JSON keys, nonfinite constants, byte/depth/count/text overflows and coherent source/scope/evidence tampering against an independent original. The full gate passes formatting, Ruff, ty, complexity at most five and996tests.

No model/provider request, actual backend server call, source-image fetch, dependency installation, canonical-source change or new historical finding occurred. The6,000input/1,500output token caps and original seven-unit selection remain unchanged. T79's D1/D2 compact literal message totals remain5,747/5,336before authentic native image accounting; its fuller D2 output illustration remains1,515tokens. The codec does not resolve either problem or supply authentic preprocessing/build parity, actual backend compatibility/stopping, missing images or launch clearance. M2.4/M5.2 and their stages remain partial; T55/T56 remain blocked.
