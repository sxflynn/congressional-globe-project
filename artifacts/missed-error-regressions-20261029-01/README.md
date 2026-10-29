# T75: regressions for the two human-reported misses

The new bounded library detects the stray-mark and damaged-token cases without rewriting raw OCR or changing the saved T52 results. It also implements source/image-bound instructions and named feedback checks for a proposed edit list. No model was called.

## What changed

`repair_review.py` explicitly routes standalone straight/curly quote marks to image review. The old token regex did not tokenize the isolated apostrophe after loyal. It also routes unfamiliar internal-hyphen words and, with a pinned dictionary, suggests only known forms reached by removing the internal hyphens and making at most one letter substitution. For the actual S2 case, property appears as a dictionary-only candidate. These candidates are not automatic corrections or verified readings.

The report preserves all original text, carries raw spans/source/resource/code identities, and exports checked signals through the existing host Paragraph/Signal types. The exact host paragraph source ID, raw hash/text and target role must match; an arbitrary valid alias is insufficient. A complete host request still needs its own frozen diagnostics, source/image registry and normal validation. This task did not assemble or send the seven real study requests.

`repair_feedback.py` binds each named requirement to the original source and exact image bytes. It generates an instruction quoting the actual source-specific concern, and checks that proposed raw edits produce the requested local reading at its exact mapped boundaries. An unchanged or incorrect local reading stays not addressed; a larger edit hiding those boundaries stays unresolved. A proposal containing the right word plus unsupported extra words cannot pass this local check. Correct smaller edits may satisfy the same local requirement. Passing says nothing about the rest of the reading.

## Evidence and limitations

[source-cases.json](source-cases.json) retains new reports, typed host signals and source-bound instructions for S1/S2, alongside checks of the old missed outputs and T74's separate case-specific proposed copies. Both old outputs fail their named check; both separate proposed copies satisfy it. Original OCR, historical outputs, packets and human answers remain unchanged.

Five authored negative controls preserve ordinary apostrophes, possessives, contractions, known hyphenated words and spaced quotation marks. Spaced genuine quotes may still be routed as ambiguous; nothing deletes them. Missing vocabulary and search/finding overflow remain explicit. There is no whole-corpus accuracy estimate, general punctuation-deletion rule, completed image-grounded correction or new human grade.

The focused tests cover actual failure cases and negative/tamper/overflow controls. Review found and fixed the arbitrary-alias bridge; root also strengthened the local check against extra replacement text and larger deletions. [review.json](review.json) records bounded Luna closure. [clarification.json](clarification.json) corrects T74's loose claim that this particular apostrophe was already flagged; the earlier committed disposition remains intact.

The new library bridge and feedback helpers are implemented and tested. T55 must still incorporate these exact requirements and checks into its genuinely prepared live requests. Native fit, two missing images and actual backend compatibility/stopping remain unresolved. No launch clearance was supplied.

Final gate outcomes, preserved-evidence hashes and code identities accompany this record. Timing is local CPU work for two cases only, excluding dictionary loading; it is not an AI runtime forecast.
