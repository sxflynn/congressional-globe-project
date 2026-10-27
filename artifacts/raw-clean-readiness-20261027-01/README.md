# What can be compared without another AI call

T43 prepares the next bounded T34 step, under M5.2/P0. A researcher typing `Constitution` into the six-paragraph raw search gets no exact hit; the existing deterministic static view contains that joined word. The question here is whether saved alternatives cover precisely the same passages, and what must be preserved before showing a derived-text match as a primary-source citation.

## Observed evidence

[Six paired paragraphs](pairs.json) bind T33's exact raw paragraphs to the saved static baseline. The baseline was read sequentially only through its118th JSONL record, the target item `congressionalg7391unit`, leaf117; no other page was selected. Its exact line fingerprint and the original T33 collection fingerprint are in [the inventory](inventory.json). All six raw strings and fingerprints match. Only P3 differs in the static view: two recorded edits join `Consti- tution` into `Constitution` and `mem- bers` into `members`. The other five paragraphs are unchanged. Replaying the two saved edits, with exact expected-text checks, reproduces the saved static text. Original sources, static snapshot and accepted ledgers were not edited.

These are existing deterministic edits, not new AI cleanup, human-approved transcriptions or a new canonical text. The saved static provenance is retained verbatim. Its input fingerprint has its original meaning; it is not substituted for the paragraph's raw fingerprint.

The named primary expansion manifest contains36requests plus4prior-reuse records, covering150distinct hash-bound source records. None matches any of these six paragraphs by item, leaf, paragraph ID and raw fingerprint. This absence finding is limited to that named manifest and reuse inventory; it does not claim that every historical artifact was searched. Baseline records for these six paragraphs are `not_queued`, with no AI provenance. There is no compatible arm C from these inspected records, and no permission to generate one follows from this finding.

## Mechanical search outcomes

[Outcomes for12fixed queries](mechanical-outcomes.json) use the existing T33 library for raw results and the same exact substring position helper for static strings. This is an offline compatibility/expectation diagnostic, not a completed derived-text search interface or a rerun of the spent model experiment.

| Query | Raw occurrences | Existing static occurrences |
| --- | ---: | ---: |
| `Constitution` | 0 | 1 |
| `Consti- tution` | 1 | 0 |
| `members` | 2 | 3 |
| `mem- bers` | 1 | 0 |
| `McPherson` | 1 | 1 |
| `House` | 3 | 3 |

The remaining six fixed queries preserve the supplied exact counts as well: the date string, year and Senate phrase each have one occurrence; `Freedmen`, lowercase `mcpherson` and the cross-paragraph phrase each have none. The outcomes reveal a mechanical matching difference only. They do not measure recall, relevance, readability, spoken output or historical fidelity, and do not establish that static cleanup is sufficient or better overall. All cases are previously exposed diagnostics, not held-out benchmark samples.

Static occurrence positions are explicitly marked as static-text positions, **not raw-source offsets**. T33 deliberately refuses changed collection bytes, so feeding it the static text under the raw collection identity would be wrong. A derived match must carry both its displayed text and a verified raw supporting span. Joining a broken word changes coordinates; even unchanged words later in the paragraph shift after an earlier edit.

## Frozen next implementation scope

T44 may extend the existing library with an explicit separate static-view path, using only these six committed pairs and the two saved edits. This is an extension to the already authorized search library, not a new command, service, scheduler or corpus workflow. No new provider request, source fetch or dependency is needed. New CLI/UI or broader orchestration would require its own adoption decision.

- Pin the exact UTF-8 pairs.json byte fingerprint, recorded as pairs_sha256 in inventory.json; no reserialization or caller-supplied replacement manifest may redefine this trust root. Pin the exact paired-input fingerprint and validate raw fingerprints, order, identity, declared regions and static text fingerprints. Verify each edit's expected raw slice, nonoverlap and deterministic replay; reject mismatches rather than finding approximate replacement locations.
- Search raw/static with identical query, matching, overlap, first-N and declared-neighbor rules. Offsets are half-open Unicode codepoint positions; overlapping occurrences count. Expose the chosen layer and its fingerprint; retain exact raw text and evidence separately from the derived display.
- Build a deterministic mapping from each static character to a supporting half-open raw interval. Unchanged text maps one-to-one; each replacement character maps to the whole replaced raw interval. A match crossing an edit reports the minimal contiguous raw envelope, the raw supporting text and whether the mapping is an exact copy or includes a saved edit. Never call the raw envelope an exact quote of the derived query when they differ.
- Return raw-source citations using the raw interval and fingerprint, alongside separate static positions and fingerprint. Preserve the unverified page-link status. Context remains raw, separately marked, within the same declared region.
- Prove the12frozen query outcomes, changed-position mapping for words after both edits, match inside/across edits, exact unchanged matches, malformed/overlapping edits, changed hashes/order/regions, raw/static identity separation, Unicode handling and first-N counts. Run the required full code gate and bounded Luna review.

The mapping policy is a software provenance rule, not a historical correction policy. T44 can be READY on this finite scope without an arm C or a new human review round. T34's broader reading/downstream raw/static/clean comparison still lacks a compatible clean arm, appropriate reviewed criteria and reading/TTS/annotation/answer outcomes; these limits remain explicit rather than inventing results.

## Costs, stopping rule and decision limits

New provider calls/time/tokens are zero. The primary investigation's48attempts/3693.79conservative seconds remain a separate immutable history; unknown timeout usage stays unknown, and its remaining allowance is not authorization. Offline elapsed time, human-review minutes and hardware/energy cost were not measured here and remain null in the inventory. Reusing saved edits avoids another model request but is not evidence that total cleanup cost is zero.

Stop this preparation after verifying these six pairs, the40manifest records and12queries. No substitution, fresh sample, model retry, new review packet or broad artifact/corpus search is authorized. T44's potential source-mapping outcome can decide whether this small derived-view slice can cite original evidence correctly. It cannot select a P0 policy. P0-C remains partial; P0-A/B/D/E/F/G remain unresolved as recorded in the master. M5.2/M5 and M6 acceptance are not completed by these diagnostics.
