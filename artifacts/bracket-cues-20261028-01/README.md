# T67: preserve bracketed cues and record them separately

A researcher should be able to find a reported interruption or reaction without losing the original bracketed wording. HR-010 specifically identified `[Here the hammer fell.]` and emphasized cues such as laughter. The [offline library](../../src/congressional_globe/bracket_cues.py) now extracts exact bracket spans, records a conservative literal cue where supported, and compares proposed readings for bracket changes. It does not infer that an event happened, who caused it, a speaker, sentiment or historical truth.

## What is implemented

`BracketSource` requires a declared composite source ID, exact raw text and matching SHA-256. `annotate_brackets` returns an immutable typed report containing the unchanged source, each exact bracketed quote, original Unicode character positions, source hash, deterministic annotation ID and versioned rule hash. End positions are exclusive. Duplicate identical quotes have distinct position-based IDs; word repairs outside brackets can shift positions in proposed text without rewriting the source annotation.

Classification uses a small exact phrase list after classification-only case/whitespace normalization and optional final period removal. Original text is never normalized. Current cues cover literal laughter phrases, applause phrases and “Here the hammer fell.” Numeric and editorial markers have separate literal-form labels; all other wording keeps an unknown cue. `[No laughter.]`, `[Laughter?]` and a sentence merely mentioning laughter are not promoted to known event cues. Numeric `[42]` does not establish a citation relationship. `[sic]` or `[unclear]` does not establish an independently verified editorial history.

Only balanced, nonnested ASCII square brackets become candidates. Nested and unmatched structures produce explicit review issues, including a nested structure whose outer bracket never closes. Inner wording in a nested/malformed region is not salvaged as an event. `[]` is retained as an unknown candidate. Parentheses and fullwidth brackets are outside this version's extraction rules; an empty candidate list does not mean there were no historical events.

Reports and comparisons validate their embedded source/hash and recompute exact positions, text, labels, IDs and issues. Altered JSON, missing candidates, wrong hashes, inferred extra fields and copied model instances with bypassed validation are rejected at validated boundaries. Strict frozen models and tuple fields preserve records. The literal phrase mapping is read-only. Future parser/classification changes need a deliberate rule-version/identity change.

One source is limited to6,000codepoints and512square-bracket symbols; source IDs are capped at256characters. Proposals have the same text/symbol limits. Overflow raises an error with no partial or silently truncated report.

## Checking a proposed reading

`compare_brackets(source, proposed_text)` preserves both texts and their hashes. It returns:

- `same_literal_sequence`: exact bracket quotes, count and order agree, even if changes outside brackets shift their positions.
- `changed_literal_sequence`: a quote was changed, deleted, added, duplicated or reordered. This is a review concern, not an automatic instruction to restore old OCR.
- `needs_review`: source or proposed brackets are nested/unmatched; their exact issue spans remain available.

A legitimate image-supported correction inside brackets can also change the literal sequence. The repair host must retain and explain that concern with its source evidence; this library cannot decide which text is historically correct. An unchanged cue moved elsewhere among surrounding prose may retain the same sequence, so this check does not verify contextual placement or speaker association. Same literal sequence is not a source-fidelity certificate.

## Scope, examples and integration

[Examples](examples.json) contain one already-exposed raw passage from HR-010 and seven synthetic reports, plus four synthetic proposed-reading comparisons. The real passage is identified by its existing source/hash, without a new image reading. Laughter/applause/control strings in this unit are software fixtures, not new human historical grades or corpus findings. [Feedback follow-through](feedback-receipt.json) links the exact submitted note.

[Report schema](report.schema.json) and [comparison schema](comparison.schema.json) describe portable shapes; semantic checks require the Pydantic models/library, not schema validation alone. The caller must supply a registered original source: a self-consistent declared ID/hash is not proof of corpus membership or printed-image accuracy. The library does not fetch, read the corpus or inspect a bitmap.

[Consumer contract](consumer-contract.json) specifies handoff to T52/T53: keep literal raw text, carry annotations separately, and retain proposed-text preservation concerns after full-reading/source-map validation. The existing T69 draft already requires bracket preservation and self-check. Its historical draft files remain unchanged. No new command, scheduler, provider request, UI question or review round is introduced. Actual sample/repair/export/UI integration and broader source/human evaluation remain ahead; this library does not close M1 or establish a complete event taxonomy.

## Verification

The full code gate passes726tests, with43new cases covering the real exposed hammer quote, literal/unknown/numeric/editorial forms, Unicode positions and duplicates, malformed/nested brackets, report tampering, strict revalidation, resource bounds and preservation changes. The bounded Luna review identified nested-but-unclosed and ellipsis classification edges; both have regression coverage and are fixed. [Validation](validation.json) preserves checks and [manifest](manifest.json) preserves file identities. No provider call, scan download, canonical-text edit, accepted-ledger change or new human answer occurred.
