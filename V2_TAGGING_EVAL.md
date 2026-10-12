# V2 subject tagging evaluation contract (draft)

**Status:** provisional design for human review. This is not an approved ontology, authority dataset, acceptance policy, or benchmark result. It was drafted from the broad subject scope in `PROJECT_GOAL.md`, before future held-out model calls; it is not fitted to the ten-window Mini diagnostic. Candidate aliases below are search/classification cues, not verified historical authorities.

## Draft controlled subjects

IDs are proposed stable identifiers: once accepted, labels or aliases may be versioned, but an ID must not be silently reused for a different concept. Human review should decide scope, hierarchy, aliases, and whether these are suitable granularity for the intended research questions.

| Draft ID | Preferred label | Candidate cues and scope boundary |
| --- | --- | --- |
| `subj.reconstruction` | Reconstruction | Postwar restoration/readmission and political reorganization; exclude incidental “reconstruction” in other senses. |
| `subj.citizenship` | Citizenship | National citizenship, status, naturalization, and its legal incidents; exclude a passing use of “citizen” as address or honorific. |
| `subj.civil_rights` | Civil rights | Equal civil/legal rights or protection, including race-related rights; exclude a bare person/place mention without rights discussion. |
| `subj.voting_rights` | Voting rights | Suffrage, franchise, qualifications, access, or right to vote; cues may include “elective franchise” and “right of suffrage”; exclude unrelated elections or office procedure. |
| `subj.constitutional_change` | Constitutional change | Amendment, constitutional interpretation, or federal/state constitutional power materially discussed; exclude routine bill amendments merely called amendments. |
| `subj.taxation` | Taxation | Tax policy, rates, collection, revenue, or tax incidence materially discussed; exclude an incidental tax label in an unrelated list. |
| `subj.military_affairs` | Military affairs | Armed forces, military administration, service, or demobilization materially discussed; exclude a passing veteran/person reference without military issue discussion. |
| `subj.congressional_procedure` | Congressional procedure | Chamber rules, debate, motions, jurisdiction, or legislative process; exclude ordinary bill content and a procedural word used incidentally. |
| `subj.infrastructure` | Infrastructure | Public works, transport, communications, and their construction/operation materially discussed; exclude a place or route mentioned only as context. |
| `subj.public_compensation` | Public compensation | Pay, allowances, or compensation for public officers/employees materially discussed; exclude private compensation and a name/title-only reference. |

These examples establish candidate boundaries for adjudication, not exhaustive definitions. Reviewers may propose split/merge, broader/narrower links, or an out-of-vocabulary subject; record the vocabulary version and rationale.

## Unit, labels, and evidence

- The classification unit is a source-linked passage window. Review its full context, but attach evidence to the smallest supportable paragraph/span(s). A paragraph/window is not assumed to be one speaker or one subject.
- Assign zero, one, or several subjects only where there is substantial discussion: an issue, claim, proposal, argument, consequence, or action is developed. A word hit, name, place, bill title, citation, list entry, or passing reference alone is a mention, not a subject assignment.
- For each proposed subject retain exact source paragraph IDs and quoted evidence aliases/spans, disposition, uncertainty, method/configuration, and review state. The host validates aliases against immutable source text; model paraphrase is not evidence.
- Dispositions must distinguish `in_scope`, `mention_only`, `no_subject`, `unknown`, and `out_of_vocabulary`. Multiple subjects can be in scope. Unknown means evidence/context is insufficient; it is not a negative. Record mixed passage composition separately: multiple evidenced subjects may coexist, and a mixed speaker window does not automatically make them unknown. No subject means reviewed with none in scope. OOV means meaningful subject matter exists outside this draft vocabulary.
- Keep controlled assignments separate from optional loose discovery tags. Loose tags are explicitly unverified hints; they cannot satisfy structured filters, count as accepted subjects, or be displayed as authority matches.
- Never accept a tag because it improves a retrieval hit. Candidate generation, subject adjudication, retrieval quality, and grounded-answer quality are separate evaluations.

## Held-out evaluation protocol

1. A curator selects a random, stratified sample across all five parts and document types (including proceedings, indexes, and Appendix). Include positives, incidental mentions, negatives, ambiguous/mixed windows, and OOV cases. Do not select only edit-rich, easy, or model-suggested examples.
2. Freeze and record sample manifest, source/text layer and hashes, window policy, vocabulary/prompt/configuration versions, and split assignments **before calls**. Held-out paragraph IDs must be disjoint from every prior diagnostic/evaluation paragraph ID, including previous Mini, Qwen, lexical, embedding, and cleanup-comparison samples. If disjointness cannot be established, label the result diagnostic, not held-out.
3. Human labelers independently review passage context and paragraph evidence before seeing system outputs. Preserve disagreements and adjudication; labels remain reviewable claims, not image-verified ground truth.
4. Compare raw OCR matching view and static-normalized matching view on the same frozen passages, with identical scope, aliases, and matching rules. Matching views may normalize OCR line-break/hyphen artifacts for comparison but must retain exact source offsets/IDs; do not alter canonical text.
5. Evaluate deterministic candidates under a declared acceptance policy. Candidate hits remain pending human review until that standard is established and validated. Do not infer a safe auto-accept threshold from candidate coverage or this contract.
6. Keep retrieval and answer tests on separately labeled sets/metrics. No retrieval hit, answer fluency, or exact cue hit changes a subject label.

## Reporting and decision record

Report per-subject and overall precision, recall, coverage, abstention, and unknown/OOV rates, with counts and uncertainty; separate mention-only false positives from missed substantive discussion. Report reviewer agreement and pairwise disagreements, per-part/document-type slices, and errors with source evidence. Include actual total cleanup-plus-tagging tokens/time, retries and request costs for each arm; distinguish billed/recorded usage from estimates. Do not invent numeric thresholds: humans must set them before examining held-out results. Publish sample/split hashes, exclusions, failures, and the accept/review/abstain policy alongside results. Any vocabulary or policy change after unblinding requires a new version and fresh disjoint evaluation.

Prior candidate matching and ten-call Mini results are diagnostics only, not this benchmark. This draft authorizes no model calls, corpus-wide processing, canonical edits, or historical fact assignments.

## Portable implementation available now

`src/congressional_globe/subjects.py` provides Pydantic v2 contracts for draft vocabularies, anchored paragraph snapshots, exact Unicode evidence spans, controlled proposals, human-review records and separate loose discovery hints. Vocabulary content digests change when scopes/aliases change, even if a caller accidentally reuses a version label. Evidence validation uses item, part, leaf, paragraph and text layer together; it preserves printed-page provenance, hOCR anchors and geometry where available.

`src/congressional_globe/subject_matching.py` exposes `match_subject_cues(paragraphs, vocabulary)`. It performs casefold/word-boundary matching and heuristic hyphen/whitespace joining on a derived view, maps matches back to exact source spans and emits only pending `mention_only` proposals. Joining does not prove a scanned line boundary; no canonical text is changed. The caller supplies a versioned vocabulary and bounded paragraph batch.

Use `validate_subject_proposals` before consuming assignments. The `reviewed_in_scope_subject_ids` helper validates source and vocabulary references and returns eligibility only from explicit human-reviewed decisions. Review records must come from a trusted host review channel; a provider response must never be permitted to claim human review. The helper neither authenticates a reviewer nor establishes historical truth. Loose discovery tags never enter it.

The implementation does not yet supply a curated vocabulary release, a model runner, a human-review import workflow, calibrated auto-accept policy, passage assessment for missing/OOV subjects, authority resolution or production routing. The evaluation protocol above remains necessary. `make gate` checks the portable contracts/matcher; historical quality requires separate human evidence.
