# T103: tighter source target and visible-neighbour exclusion

The actual T102 reply appended a sentence from the neighbouring paragraph. This offline implementation fixes the source-region input and adds a checked exclusion for the visible context; it does not rerun a model or alter that failed result.

## Inputs, expected and actual software results

The original999×206S5 crop remains byte-identical. The assigned paragraph’s hOCR bbox and original crop frame give target-local bounds **64,64,935,142** instead of the whole image. The adjacent line19 has local bounds **105,149,842,184**, exact parent source/hash, line identity and raw span0:35. Its parent extends outside the image, so only that fully visible line is provided as context and the parent is marked partial. Hidden line20/remainder is not sent or claimed visible.

Expected behavior: inspect and return only the assigned paragraph, using the nearby visible span for orientation. The provider input explicitly states image pixel dimensions/coordinate convention, the tight target region and context-only role. It retains the strict complete/incomplete reply rules.

Actual offline replay of the unchanged T102 copied-neighbour reply: **rejected on the new input**. The old input’s structural behavior remains reproducible. The saved result stays unresolved with its original unknown-stop receipt. The later process-absence evidence is not rewritten.

A separate authored software test supplies the recorded expected target reading. It passes as an unreviewed source-linked proposal and preserves the genuine hyphen; this is not a new model response or accepted reading. Incomplete replies still withhold text and remain unresolved.

## Implementation and evidence

- Existing host validation gains an opt-in typed `ScopedImageBinding`/versioned boundary scope. Old image types/default serialization and old request bytes remain supported.
- `productive_ocr_scope.py` derives real boundary/context data through the existing hOCR paragraph parser. It streams to the selected page, checks source ID/page ancestor/ppageno, rejects duplicate paragraph identities, matches target raw text, and checks exact line text/offset/hash/visibility. A context line must be completely inside the crop; incomplete parent visibility is separate from selected-span visibility. Ambiguous mapping, overlap, unavailable geometry and clipped lines fail closed.
- Original registration is linked to its crop bundle; both new geometry records bind the exact scope hash. The same image/legibility/source identities are retained, and no old record is overwritten. Scope requires one-to-one source crop pixels; it refuses scaled/inferred coordinate transforms. That image-coordinate requirement is not proof of the model’s internal input fit.
- Only declared visible context text is projected; the full hidden parent text is not exposed. Raw/static/visible context text fields together are limited to2,000characters in the new mode. Legacy budget semantics stay unchanged.
- The output guard checks normalized complete declared-visible-line occurrences, allowing any original raw/static baseline occurrences and catching added/repeated copies with spacing/case/word-separating punctuation variants. It does **not** prove full fidelity or detect arbitrary paraphrases, fused-word rewrites, smaller fragments or unknown context. Ambiguous overlap is withheld. Scope provenance and that limited check are explicit in the derived export.
- No model-authored offsets/edit lists, new CLI or generalized workflow is introduced. Existing freeze/request/export/journal mechanisms remain in use; a future real request needs its own exact authorization and new slot.

## Verification and limits

Full `make gate` passes formatters, Ruff, ty, complexity≤5 and **1,132tests**, including29new focused source/geometry/actual-response/valid-target/clipped-context/ambiguous/duplicate/overlap/hash/budget/compatibility cases. Bounded Luna review found the context budget needed both transmitted layers counted; corrected and tested. The final scoped input also declares its pixel frame explicitly.

HR-014v3 shows the actual saved failure, expected boundary, derived input and actual software outcomes. Typed/plain-source/glossary/isolated AppTest checks verify4evidence comment boxes plus overall comment,0exceptions and no glossary buttons in source/model spans. The verified source URL is inherited unchanged. No Computer Use/browser/device interaction.

Saved candidate host/request/prompt/schema/projection, hash-addressed resources, authored test export and outcome checks provide a reproducible offline handoff. Actual provider calls: **0**. The new scoped model input has not been tested live; no quality/native-fit/corpus claim or new call authority follows. Original source/accepted ledgers/old packets, all actual replies and spent slots remain unchanged.
