# T20: four reused passage windows

2026-10-26. Offline preparation for M2.5/M5.1; **no workflow adoption or live authorization**. [Manifest](manifest.json) freezes four unique existing windows, exact local input/source hashes, expected supported/unknown outcomes, expectation provenance, prior exposure and saved-result compatibility. The copied inputs and results support inspection without parsing the corpus or calling a provider.

A researcher should find the right passage without receiving an invented speaker, a date copied across chambers, or a subject guessed from missing words. These cases expose those risks; preparing them does not show that a model or tool has solved them.

| Existing window | Purpose and supported expectation | Evidence and limit |
| --- | --- | --- |
| `t2-4-053` | Ordinary explicit Kasson cue, immediate preceding context for P2, Holmes turn stop; modal “may” supplies no date. | Exact historical role input plus T10 hand-authored date fixture. Expectations are AI-provisional raw-text interpretation. T10's per-paragraph date regions do not certify speaker continuity. |
| `hr008-cross-page-p5-403-404-v1` | Inspect the previous-page cue and continuation into compensation discussion on P12/P13. | Existing frozen leaves403–404 packet includes P7 “Mr. WADE.” and P8 continuation. HR-008 supports the need for cross-page context, not a new human-confirmed Wade label for P12/P13. Page print was not inspected here. |
| `house-opening-december-4-1865-v1` | Explicit1865-12-04 in P3 supports proposed date scope P3–P6; Senate P1/P2 remain unknown. Stop FOOT attribution at the House boundary. | Frozen preparation and T10 executable host fixture; AI-provisional expectations and host-declared regions, not human gold. No continuation after P6 established. |
| `rawstatic-distractor-p2-01` | Truncated petition cannot support military-affairs inference; preserve petition discovery and the missing object. | HR-008 S2 rejects the military guess. Human-reported “660”/“American labor” remains separate from the exact raw fragment ending “American.” No new correction or subject label is imported. |

## What can be reused

[Role inputs](role-inputs.jsonl) copy the two original provider-input JSON lines byte for byte, with line hashes excluding the newline. [Source maps](role-source-maps.json) retain their original alias maps. [Date fixtures](date-fixtures.json) copy the two existing T10 packet/result/mapping records. [Topic window](topic-window.json) retains the complete historical raw/static paragraph records for the missing-evidence case. [Frozen expectations](frozen-expectations.json) retain both original date-preparation expectation objects.

[Saved role replies](saved-role-replies.json) retain the two historical cross-page Mini/Qwen raw replies, hashes and v2 revalidation outcomes. [Saved topic results](saved-topic-results.json) retain the historical Mini/Qwen records for the truncated-petition window with original line/file hashes. Both providers' frozen topic windows match this copied window. Their saved results are existing evidence; role/date/topic tasks and newly augmented requests are not interchangeable. There is no saved T19-tool result. A compatible reuse claim requires the exact original request, prompt, schema, provider/configuration and source/target identity, not just the same passage. No historical request is repeated by this preparation.

For `t2-4-053` and the House-opening window, the inventory contains offline hand-authored date results, not live date-provider replies. No matching `t2-4-053` role-provider result appears in the inspected four-record v2 revalidation inventory; this is a bounded inventory statement, not an assertion that no other local output exists. All cases are development-exposed. They are not held-out gold, representative samples or an accuracy estimate.

## Constraint to carry into T21

The frozen cross-page packet closes the source-availability gap that exists in the earlier same-page topic window. It does **not** prove T19 can retrieve the useful cue: immediately before P12, P11 is “July 25,” and P10 is the running title, preceded by the P9 page number. T19's fixed anchors and two-paragraph ceiling therefore stop before P8 continuation or P7 speaker cue. Repeating calls cannot move the anchor. Do not skip headers, change ceilings or fabricate a supported edge silently. T21 must decide whether this limited path has enough value, or propose a separately reviewed amendment with matched evidence access. Context-only targets and source-bound speaker-continuity policy also remain unimplemented.

P1→P2 in `t2-4-053` is a smaller same-window illustration where one preceding paragraph is accessible; treating its text as supporting continuity is a provisional design interpretation, not a calibrated attribution or extension of T10's deliberately local date scope. Historical source availability, tool access policy and human judgment remain separate.

The missing-evidence case uses an actual truncated OCR passage. Future fake missing-source/invalid-argument responses are synthetic transport negatives and must be labelled as such; they are not extra historical findings or new cases. No presidential passage or roster-absence search occurred. Scans and roster tools remain outside T19.

## Review and validation

A bounded Luna delegate independently inspected the proposed cases and the existing cross-page packet. [Review record](review.json) preserves the actual final verdict and its scope; this preparation review is not T22's required human-run independent GPT-6 workflow verdict and is not a human grade. Root inspected the frozen paragraphs, source maps and saved-result inventory and incorporated the context-reach and human-label cautions.

Checks replayed the exact t2 provider-line hash, role span offsets/text, date paragraph raw hashes, topic raw/static hashes, historical raw role-reply hashes and equality of the two saved topic-provider windows. Every source/snapshot hash in the manifest is checked again before commit; original inputs remain unchanged. Required Markdown formatting, local links, JSON parsing, four-window bound and `git diff --check` are checked. Documentation/data preparation only: no full code-gate rerun; the last recorded code gate is T13 (511 tests). No fresh corpus search, fetch, experimental provider call, image inspection, accepted-ledger edit or human-label import occurred. Parent M2/M5 remain PARTIAL; T21 is now actionable design work.
