# More definitions on the human review desk

T37, supporting M5.1. Direct human instruction on 2026-10-26: “I need even more words underlined with glossary definitions. Do it now and make it a rule.”

The shared glossary grew from 66 to 178 entries, covering 417 term/alias spellings. Definitions now also appear in packet titles and the version line. Existing instructions, questions, answer-term help, evidence labels and historical passages use the same dotted-underlined buttons.

For example, “paragraph boundaries” explains where paragraphs begin and end; “provenance” explains where material came from and what happened to it; “faithful” explains matching the print without changing its meaning. The historical passage also explains “broom corn,” “tub to the whale,” “the hammer fell,” “franking privilege” and old printed House/Senate measure-number prefixes. Phrase matching prevents “habeas corpus” from receiving the unrelated project meaning of “corpus.” JSON and schema, imports and importers, and the historical “mere blind” versus “blind review” have separate definitions.

The standing rule is in [AGENTS.md](../../AGENTS.md) and the [review protocol](../../docs/reference/human-review-protocol.md#mandatory-plain-language-and-glossary-rule). Future review authors must use plain English, generously define unfamiliar terms and displayed variants, check the rendered review, keep meanings neutral and verify that opening definitions does not lose an answer. Shared definitions improve registered packets without changing their immutable contents.

## Evidence and checks

[Before](before.json) and [validation](validation.json) record dictionary size, rendered coverage and preservation checks. The HR-009 text now contains 82 underlined occurrences covering 60 distinct displayed spellings; HR-010 contains 274 occurrences covering 106 distinct spellings, compared with 111/16 before. Counts include rendered packet fields, with custom packet definitions applied; the live page additionally has answer-term help. They demonstrate a substantial increase, not proof every unfamiliar word has been found.

All packet JSON files checked before the edit retain their exact file fingerprints. Read-only content fingerprints of registered packets, submissions and drafts match the baseline. Removing glossary popups from rendered fields reconstructs every original character, including case and punctuation. No human answer, source text or registered packet changed; no review was saved or submitted during browser checks.

The live HR-010 desk rendered without an exception. Mouse opening/closing and keyboard Enter/Escape worked. A temporary unsaved note retained its value and the same input element through those interactions; zero form-submit events occurred. The note was then cleared. [Desktop screenshot](desktop-definition.png) and [375 × 812 screenshot](phone-width-definition.png) were visually inspected. The narrow popup fits inside the viewport without internal horizontal overflow. This was a desktop browser resized to phone width, not a physical iPhone/iPad test.

Three added regression tests cover expanded vocabulary, distinct meanings/source-word preservation and title/version help. An existing scan-order test now inspects visible text because “image” can itself be underlined. Full `make gate` passed: 565 tests, Ruff, type checks and complexity ≤5. [Readable gate output](gate.txt); [compressed original output](gate.log.gz). The final documentation update receives the required Markdown formatter and diff check separately.

A bounded independent Luna review found no blocker. Its suggestions to explain franking/bill prefixes and make the gavel phrase more contextual were incorporated. This is software/editorial review, not a human grade or historical acceptance. No model inference experiment was run. M5.1 and M5 remain PARTIAL; HR-010 and broader benchmark decisions remain outstanding.

## Historical definition references

Definitions explain vocabulary without adjudicating the proposed OCR corrections. The [Senate glossary](https://www.senate.gov/about/research-tools/glossary.htm) supports congressional terms; the [House forms of legislation](https://www.house.gov/the-house-explained/the-legislative-process/bills-resolutions) and [GovInfo bill guide](https://www.govinfo.gov/help/bills) distinguish modern bill prefixes/types. Old HR-010 prefixes are deliberately explained with their surrounding “bill” or “resolution” text rather than silently assigned a modern type. The [Senate Historical Office](https://www.senate.gov/artandhistory/history/minute/Senate_Ends_Franked_Mail_Priviledge.htm) explains the changing franking privilege.

The [USITC broom-corn report](https://www.usitc.gov/publications/tea/pub238.pdf) explains the plant's use in brooms. The [historical slang dictionary](https://wehd.com/farmer/Tub.html) explains “tub to the whale” as a diversion. [House precedents](https://www.govinfo.gov/content/pkg/GPO-HPREC-PRECEDENTS-V1/pdf/GPO-HPREC-PRECEDENTS-V1-5.pdf) provide gavel/procedure context; the definition leaves the particular signal to its surrounding passage. The [CRS habeas-corpus overview](https://www.congress.gov/crs_external_products/RL/PDF/RL33391/RL33391.5.pdf) supports the general meaning of court review of detention. These references do not certify any sample's proposed wording or grade.
