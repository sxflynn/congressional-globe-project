# Source-bound reading failure fixtures

This package completes the master plan's next offline P0 unit: freeze concrete pilot failures and guard requirements without rerunning models or changing accepted text. These are ten deliberately selected, output-informed diagnostic cases, not a held-out benchmark, human gold, a new fidelity score or an implemented acceptance policy.

## Results

| Case | Existing host outcome | What the case establishes |
| --- | --- | --- |
| F01 | Valid,4patches | Qwen changes OCR CCCXL to CCCXLI despite inherited source reading CCCXI. Structural validation cannot certify identifiers. |
| F02 | Valid,4patches | Gemma removes one printed “that” inside a broader useful patch. Grammar smoothing can violate fidelity. |
| F03 | Valid,5patches | Gemma moves LOAN between source records without an explicit relocation map. |
| F04 | Valid,9patches | Qwen moves both LOAN and the fragments of evening; one original record becomes empty. |
| F05 | Invalid | Wrong unit ID is already rejected; preserve the whole reply/error without repair. |
| F06 | Invalid | A no-op is already rejected, even though other index repairs are useful. |
| F07 | Valid,needs_review | Zero patches,13uncertainties, all target text unchanged; valid transport does not mean improved reading. |
| F08 | Invalid | Gemma's unrelated-image abstention adds four forbidden fields; semantic abstention and schema success differ. |
| F09 | Valid,needs_review | Qwen abstains within schema with four uncertainties; source text remains unchanged. |
| F10 | Valid,5patches | Gemma changes the same OCR CCCXL to the inherited source reading CCCXI. A guard must permit reviewed legitimate correction, rather than ban numeral changes. |

The10replays match the original outcomes exactly:7valid/3invalid. Four structurally valid cases contain inherited fidelity/mapping failures; one is a source-backed comparator and two remain unresolved. None becomes an accepted clean reading here.

## Evidence and portability

`fixtures.json` preserves each full candidate, exact raw provider envelope/string hash, model/digest, request hash/index, image IDs/hashes/span coverage, exact focus patches, prior assessment reference/hash, inherited observations and complete current derived output or rejection error. `validation_record` holds only the existing transport validator's required fields, with no endpoint or image payloads. `replay.json` is the compact outcome table; `portable-replay-proof.json` verifies that all10cases replay exactly from this fixture alone, without reopening original corpus/request/image files. The existing `reading_dispatch._parse_and_derive` function takes the stored `validation_record`, Pydantic `ReadingCandidate` and parsed `raw_reply` envelope; it performs no request. The exact validator source hashes are pinned in the fixture. No new script, command or worker was added.

Preparation verified the frozen request/candidate file hashes, reconstructed each exact request locally with the existing materializer, checked original image-file hashes, raw target hashes and reply hashes, and compared successful replay outputs byte-for-value with saved host results. Transport revalidation includes completion/model identity, context/token envelope, quote-v2 schema, exact anchors, patch/image coverage, uncertainty and evidence controls. Invalid replies remain invalid; they have no accepted derived output. The subsequent portable replay used only this package and existing modules.

`existing-guard-tests.log` records28passing tests across `test_reading_quotes.py`, `test_reading_contracts.py` and `test_reading_controls.py`. Production/test code was unchanged, so the prior full397-test gate remains applicable; no redundant full gate was run for this data/document unit. Package hashes are in `manifest.json`.

## Guard requirements and limits

`guard-requirements.json` separates six concerns: critical identifier review, repeated-word deletion review, cross-record provenance, existing transport rejection, unresolved/readiness accounting, and evidence-control reporting. G01–G03 are missing semantic/provenance checks, not implemented guards. G04 and G06 retain existing strict checks; G05 describes readiness requirements. Every requirement includes a counterexample or a prohibited shortcut.

The smallest useful next evaluation is a risk-only contract for G01–G03, retaining current structural validity and routing flagged changes for source review. Source-correct and source-incorrect identifier edits should both be flagged; text heuristics cannot decide what print says. Cross-record relocation needs a many-to-many source-span account or an unresolved state. Any later workflow/automation implementation remains subject to the master's independent-review rule; this package does not adopt it.

No new scans were fetched or visually certified. All visual judgments here are attributed to earlier AI-provisional observations and assessment files; no human grade or exhaustive reference transcription is created. No provider calls, model loads, canonical edits, accepted-ledger changes or new human-review request. P0 remains open and HR-010/004 still await actual submissions.
