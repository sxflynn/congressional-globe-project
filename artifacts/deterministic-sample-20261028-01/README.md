# T52: bounded deterministic repair and review signals

The new library proposes cautious line joins and shows which words, names, numbers and unusual character patterns merit image inspection. It preserves original OCR and the old static result. Nothing here is an accepted transcription, historical grade or automatic correction to the corpus. No model was called and the human desk was not changed by this unit.

The frozen first chunk contains five probability-selected paragraphs (S1–S5) and two already exposed failure units (D1 has four paragraphs; D2 has nine). These are18paragraphs and4,302Unicode codepoints in total. No reserved confirmation text was analysed. The challenge units are reported separately from the probability subset; neither supplies a population accuracy estimate.

| Unit | Paragraphs | Proposed line joins | Raw tokens with signals | Raw tokens without signals |
| --- | --- | --- | --- | --- |
| S1 | 1 | 4 | 26 | 95 |
| S2 | 1 | 0 | 3 | 6 |
| S3 | 1 | 0 | 0 | 4 |
| S4 | 1 | 0 | 3 | 4 |
| S5 | 1 | 0 | 6 | 1 |
| D1, exposed | 4 | 0 | 83 | 233 |
| D2, exposed | 9 | 2 | 50 | 228 |

A signal is a reason to inspect a token, not a detected historical error. One token can have several route candidates, so route counts overlap. Tokens without signals remain available for whole-unit audits: a dictionary match cannot establish that the printed word, name or number was read correctly. Route candidates do not dispatch work or establish an approved routing policy.

## How a line join works

A proposed join needs an exact boundary between two adjacent recorded OCR lines, lowercase letter parts, an exact joined-word match in the pinned vocabulary, no matching hyphenated word and no ambiguity from both parts being ordinary words. It also needs the supplied line records to match the separately pinned geometry registry. Balanced bracket contents are protected; malformed bracket structure blocks joins in that paragraph. The library retains a reason whenever it declines a join.

The human's HR-010 note “You missed re-gard” led to a synthetic regression: `We re-` on one line and `gard 660.` on the next produces the proposal `We regard 660.` with a reversible original-text record. The actual pinned vocabulary contains `re` and `regard`, but not `gard`, so its membership satisfies this guard. This test does not regrade the old image or replace its immutable model output. Tests also cover missing or forged line evidence, same-line splits, ambiguous words, names, protected brackets and malformed brackets.

Each edit records the exact original quote, original interval, proposed replacement and rule identity. The output maps proposed-text positions back to original text. A replacement maps to its entire supporting original interval; it does not pretend each proposed character has its own original character. The previous static layer has its own checked replay record and is never silently replaced. The stricter new guard proposes six joins across these units; the saved static comparator contains16edits. That difference is a rule comparison, not an improvement score.

## Inputs and limits

[Input manifest](input-manifest.json) pins exact selected input bytes, prepared geometry, upstream selection artifacts and local vocabulary resources. [Frozen inputs](frozen-inputs.json) retain original/static text and the preparation record. One metadata-header stream located seven allowlisted pages; only their18selected paragraphs were extracted for analysis. Primary page-record fingerprints match the prior sample. The full canonical-file fingerprint was inherited from T49 rather than recalculated. The library checks the supplied registry; it does not independently authenticate its relationship to canonical pages or prove image fidelity.

The word lookup uses the existing supplemented macOS-derived vocabulary, without the old suffix heuristic. Proper-name lookup uses the pinned local `propernames` file as a hint. Neither is an1865 spelling authority or a congressional identity roster. Licensing, historical coverage and redistribution limits remain unresolved; this artifact does not copy the vocabulary bytes. No place list was acquired, so place lookup explicitly says `not_assessed`, rather than reporting dictionary misses. Word/name/place resource identities are separate.

Capitalization and nearby titles supply name/place candidates; numbers remain unverified even when plausible. Roman-looking strings remain ambiguous. These are narrow token patterns, not entity recognition or complete detection of broken words, punctuation, unusual names or real-word errors. An unavailable resource is distinguished from an unfamiliar word. Known words and unflagged controls remain unverified.

T67 bracket metadata is carried beside each exact source. D2 has one balanced literal candidate and one malformed-bracket issue. Seventeen paragraphs have the same balanced literal sequence; the malformed paragraph remains `needs_review`. Balanced quotes are unchanged in all18outputs. Literal preservation does not prove event occurrence, contextual placement, speaker or complete event coverage.

## Evidence and cost

[Results](results.json) contain all18strict typed outputs; [schema](result-schema.json), [summary](summary.json) and [validation](validation.json) record exact replay, JSON roundtrip and recomputation using the actual resources. The one-off analysis also verifies exact unit/source membership and raw/static hashes against the pinned upstream selection, with counts1/1/1/1/1/4/9. Input hashes alone are not claimed to prove correct selection.

[Costs](costs.json) report one local execution: roughly0.03seconds loading lookup resources and0.02seconds analysing18paragraphs. Timings separate wall time and process CPU time, and exclude input preparation, fingerprint checks, output encoding/writes and verification recomputation. This is not an image-model timing estimate, an energy estimate or a corpus extrapolation. No GPU or provider work occurred.

The five new library modules, existing bracket library and26new test cases pass the full gate:752tests, formatting, lint, type checks and complexity≤5. [Gate log](gate.log.gz) retains the check output. [Review](review.json) records the bounded Luna review and the exact-selection fix. Tests establish software behavior using constructed examples; no new image-backed accuracy labels were created.

[Preparation source](input-preparation-source.txt) and [analysis source](run-source.txt) retain the one-off evidence-generation code. They are not installed commands or adopted operator workflows. No new runner, desk view, provider integration or recurring process was introduced. T51 workflow review and T53 integration/recovery remain separate acceptance work. P0 stays open.
