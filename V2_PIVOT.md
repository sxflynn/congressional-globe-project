# V2 pivot: research-first corpus without OCR repair

Draft next-stage subject scopes and evaluation requirements: [V2_TAGGING_EVAL.md](V2_TAGGING_EVAL.md). Historical diagnostics remain frozen; this contract is not an approved vocabulary or a quality result.

## Evidence checklist for the pivot decision

Offline audit after commit `cfe5a39`; this checklist records the original scope, not a claim of completion. Evidence paths below are relative to `artifacts/v2-pivot-20261011/` and require copying local artifacts when moving machines.

| Requirement | Evidence currently available | What remains open |
| --- | --- | --- |
| Preserve existing cleanup and immutable OCR | Separate raw/static inputs, source hashes and exact anchored spans; queue unchanged in latest checkpoint | Preserve both paths in the eventual pilot/export |
| Organize raw text for retrieval | Source-linked windows across all five parts; `raw-vs-static-transfer/windows.jsonl` | Speaker-turn/debate boundaries remain unverified; windows are not speeches |
| Raw vectors versus cleaned vectors | Native Qwen4B rankings in `raw-vs-static-transfer/embedding-runs/raw-static-transfer-live-20261011-01/retrieval-report.json`, both10/10 intended targets first; harder125-window/29-question experiment also recorded | Human relevance judgments, harder held-out questions and negative controls; current samples nearly saturate |
| Controlled subject tagging and OCR workload | `tag-cleanup-cost/report.json`: improved raw/static candidates identical; ten Mini proposals and pending human packet | Scoped vocabulary, accepted subject labels, precision/recall and actual residual-call workload |
| People, cities and legislation | Evidence-linked lexical candidates in `tier2/tagged_pool.jsonl`; five-case role diagnostic with held failures in `metadata-filters/span-selection/` | Person/place/bill authority resolution, historical affiliations and reviewed relationships; candidate mentions are not resolved identities |
| Loose discovery tags | Proposed as a separate unverified layer | Separate bounded evaluation; no validated loose-tag result |
| Hard metadata plus vector retrieval | `metadata-filters/report.json` demonstrates candidate-only filtering | Verified speaker/date coverage remains zero; no trusted combined filtering benchmark |
| Grounded answers from returned raw documents | Actual top-three inputs and paired Mini/Qwen outputs in `raw-vs-static-transfer/runs/`; provisional review with exact citations | Human adjudication; qualification, attribution and abstention failures remain |
| Reproducible human-operated workflow | Frozen inputs/config/scripts, audits/progress and offline commands in `PROGRESS.md` and `V2_HANDOFF.md`; provider-neutral embedding contracts in source | Portable pilot packaging, reviewed release and full-run decision; Git alone omits local prototype scripts/evidence |

**Recommendation supported today:** continue toward a reviewed raw-text retrieval pilot; retain optional static matching/readability and targeted cleanup. Do not treat vector success as proof that historical metadata or subjects are correct. The full pivot objective remains active because the controlled authorities, trusted hard filters, loose-tag evaluation and packaged pilot are not established.

**Next executable work:** inspect the saved human-pending subject/answer packets before making more calls. Freeze explicit vocabulary scope notes and a held-out evaluation contract, then measure acceptance and residual workload against human labels. Do not rerun completed experiments to manufacture confidence.

## Latest tagging checkpoint

The user also asks whether dirty OCR increases AI tagging workload. Provider-free comparison on 50 windows found **identical raw/static candidate topic sets** with word boundaries and hyphen/whitespace folding:78 assignments in 44 windows, 1.70 seconds. Literal raw matching found72/43. Source OCR remained immutable; exact spans and full anchors were checked. The earlier substring comparator was confounded; final report supersedes preliminary cleanup gains. These are candidate counts, not subject precision/recall or proof 44 windows can bypass AI.

Ten paired GPT Mini tagging calls completed in 18.055 seconds for estimated $0.01967325. Raw input 8,551 tokens/static 8,422; five cases and fixed prompt overhead do not establish corpus-wide token costs. Both arms expose vocabulary-scope mistakes, such as Senate salary debate assigned to ministerial-office compensation. All 10 responses are structurally valid, historical judgments remain pending. No more model calls in this unit. Main gate passed107 tests.

Latest evidence and exact hashes are in the final `PROGRESS.md` checkpoint and `artifacts/v2-pivot-20261011/tag-cleanup-cost/`. Mini run `subject-tags-mini-20261011-01`/session 97596 is terminal; do not restart. Next: human scope/negative labels, a frozen broader vocabulary, held-out precision/recall, and an audited residual-routing policy before estimating savings. A cue hit is not an accepted subject and no hit is not absence. Copy ignored evidence/scripts for another machine.

## Latest decision checkpoint: raw OCR versus cleanup

The current question is whether further OCR cleanup must precede vector retrieval and grounded answers. Fresh POC `raw-static-transfer-live-20261011-01` compares original OCR with existing deterministic static edits across50 windows,10 questions and all five parts, excluding earlier sample paragraphs. Both native Qwen4B arms rank all 10 intended targets first. This supports a **reviewed raw-text retrieval pilot**, with targeted cleanup for demonstrated failures; it does not justify full processing or declare OCR errors harmless. This is not a comparison with perfect transcription.

Actual retrieved top-three contexts fed20 Mini answers (32.44 seconds, estimated $0.048741) and10 matched local Qwen answers (251.89 seconds, $0 API). All responses pass schema/citation-ID checks; AI-provisional review finds Mini raw 7 supported /3 partial versus static 6 supported /4 partial, and Qwen each arm 1 supported /3 partial /1 incorrect abstention. These are small diagnostic counts, not accuracy estimates. Five pairs have different top-three contexts, and single completions cannot establish a causal cleanup effect. Raw OCR still yielded the correct twenty-dollar monthly guardian allowance; cleanup did not consistently fix omitted qualifications, hedge loss, clipped answers or abstention.

All workers are terminal (embedding 77553, Mini 87884, Qwen 40536); do not repeat their IDs. Main gate passed 107 tests. Latest queue remains 1,339 completed /423 review /20,785 pending /0 claimed. Exact audit hashes, freeze-timing caveat and resume command are in the final `PROGRESS.md` checkpoint.

Human review is next: `artifacts/v2-pivot-20261011/raw-vs-static-transfer/review/human-review-pending-20.json` and `qwen-human-packet-pending.jsonl`, with paired source evidence in `mini-answer-review.json`, `pairedscorecard.json` and `qwen-answer-review.json`. All decisions are pending. These packets are separate from the older HTML viewer. Then establish harder human-adjudicated tasks and unanswerable controls, and package the pilot; metadata interface tuning is secondary to this main decision. No further calls are needed to inspect saved results. Copy these ignored machine-local artifacts when moving harnesses/machines; a Git checkout alone omits them.

## Status and hypothesis

For the local embedding-model recommendation and compatibility checks, see [V2_EMBEDDING_MODELS.md](V2_EMBEDDING_MODELS.md).

For another AI harness to continue, follow [V2_HANDOFF.md](V2_HANDOFF.md) and the latest `PROGRESS.md` checkpoint. The user authorizes bounded GPT Mini and Ollama POCs; full processing remains human-launched.

This is an alternative, unvalidated direction. It does not replace, invalidate, or authorize discarding the static cleanup, patch ledgers, queue, canonical exports, or RAG work already completed. Keep those artifacts immutable and available for comparison.

**Hypothesis:** research discovery may improve more from structuring page/turn windows and adding evidence-linked person, place, topic, and legislation tags than from spending the next iteration repairing OCR. Preserve the OCR as-is for this experiment. Do not treat normalized OCR as ground truth; the existing static and AI outputs remain separate comparison inputs.

The target remains all five parts of _The Congressional Globe_, 39th Congress, 1st Session. The pivot changes the next experiment's objective, not the historical scope or the long-term requirement for trustworthy canonical text.

## Product boundaries

- **Immutable sources:** retain hOCR, DjVu, page maps, available catalog metadata, and hashes unchanged.
- **Canonical transcription:** retain original OCR and accepted normalized revisions with existing correction ledgers. V2 adds no text edits. A passage window is a derived view with links to its ordered source paragraphs; it does not replace or merge canonical records.
- **Controlled enrichment:** store candidate person/place/topic/legislation tags separately from transcription, with vocabulary/authority version, evidence paragraph and text span, method, uncertainty, and review state. Multiple tags, no tag, unknown, and conflicting candidates must be representable.
- **Loose discovery tags:** optional free-form search hints live in a separate, explicitly unverified field/layer. They cannot satisfy structured historical filters or be presented as authority matches.
- **Retrieval and answers:** retrieval units point to canonical paragraph IDs, source item, part, scan leaf, printed page, hOCR page/line IDs, and geometry where available. Generated answers cite retrieved evidence. A retrieval chunk is not presumed to be one speaker or one topic.

### Evidence and unknowns

Date and speaker assignments require positive evidence in the cited window or an explicitly linked, reviewed boundary/continuation assertion. Record source paragraph and quoted span. Do not copy a date or speaker across a boundary just to fill a field. For mixed or uncertain windows, preserve multiple candidates or `unknown`; do not assign one speaker, chamber, party, date, topic, or bill to the whole window. Party/state affiliation is time-scoped and requires a separate sourced authority assertion. A mention of a person is not a speaker assignment; a bill mention is not proof the passage debates that bill.

## Existing contracts: useful foundation and gaps

Current support is in [models.py](src/congressional_globe/models.py), [chunking.py](src/congressional_globe/chunking.py), [structure.py](src/congressional_globe/structure.py), and [PROJECT_GOAL.md](PROJECT_GOAL.md).

- `PageRecord`, `ParagraphRecord`, `TextEdit`, and `RAGParagraphSource` preserve raw/normalized text, source identity, hOCR anchors, geometry, and cleanup provenance. These remain the source-link layer for V2.
- `RAGChunk` is page-bounded, cites its constituent paragraph IDs, and carries per-paragraph sources. This is a retrieval baseline, not yet a speaker-turn or proceeding-window model.
- `structure.py` conservatively derives some date/chamber facts and review hints. Current `context` is a string dictionary; it is not a typed, versioned historical assertion with alternatives, evidence offsets, adjudication, or authority links.
- There are no dedicated person/speaker, place, subject, legislation, affiliation, or boundary authority contracts. Current tags and context must not be stretched to imply those capabilities.

For V2, add versioned enrichment records linked to immutable source identity and a named canonical text layer/hash. Validate every evidence span against that exact text. Keep assertions append-only or versioned so a new proposal does not silently overwrite an earlier one. Full schemas are a later design unit; this note does not claim they exist.

## Comparative POC

### Question

On a small, labeled historical-query set, does an evidence-linked structured/discovery layer over unchanged page/turn windows improve finding and citing relevant material compared with text-only retrieval? Compare inputs built from (A) raw OCR and (B) the current static-normalized text. This separates the value of the V2 organization/tagging idea from the effect of existing cleanup.

### Controlled setup

1. Freeze a small, stratified set of source windows from all five parts, including proceedings, indexes, and Appendix material. Preserve paragraph order and source anchors. Include single-speaker candidates, mixed/uncertain windows, explicit dates, and windows with no safe date or speaker assignment.
2. Build both text variants from the same windows: raw OCR and the current static-normalized layer. Do not run new cleanup or edit either input. Record hashes and the canonical release/source IDs.
3. Compare a text-only baseline with page-bounded retrieval against the same retrieval plus V2 evidence-linked tags and explicit unknown/mixed handling. Keep chunk boundaries, retrieval settings, and query wording fixed across variants.
4. Use a small query set covering person/speaker, topic, place, legislation, and date/chamber filters, including ambiguous and negative cases. Human-label relevance and supported answer claims before examining system outputs; label expectations provisional, with disagreements retained.
5. For each retrieved item, inspect whether the cited paragraph/window supports the answer claim and whether its citation resolves to the exact source. Score structured tag correctness separately from loose discovery-tag usefulness.

### Decision gates

- **Integrity gate:** every returned citation resolves to a source window and exact paragraph IDs; every structured assertion has a valid evidence span, method, version, and review state. Any unsupported answer claim or falsely filled mixed/unknown field is a failure to investigate.
- **Retrieval gate:** report precision/recall at a predeclared small set of cutoffs and per-query results for raw and normalized text. Adopt no retrieval claim from aggregate scores alone; inspect misses and false positives by document type and part.
- **Tagging gate:** report precision, recall, abstention, and reviewer agreement separately for each tag family. A candidate with weak evidence must remain unknown/review, not be counted as a correct assignment.
- **Value gate:** compare against text-only retrieval on the same queries. Continue the pivot only if it improves useful discovery or grounded answer coverage without reducing source traceability or increasing unsupported structured claims. Otherwise keep the current workflow and revise the hypothesis.
- **No OCR-quality claim:** this POC measures retrieval, tagging, and answer grounding. It does not measure transcription accuracy, certify static edits, or establish image-level truth.

## Scope and handoff checklist

The user requested this exploratory POC and explicitly authorized small GPT Mini and Ollama tests. Current work prepares an isolated ten-query, fifty-window comparison, with at most twenty sequential local Qwen requests per run after preparation checks, then a selected small Mini comparison. No full-corpus processing is part of this experiment. Production OCR, cleanup queues and exports stay intact. The first lexical retrieval baseline will not prove vector retrieval; a separate bounded embedding comparison is still needed. Qwen3 embedding 4B and 8B are now installed. Exact execution state and delegate ownership are in `PROGRESS.md`.

- [x] Establish the user-requested experiment objective while preserving the cleanup path.
- [x] Select and freeze the initial fifty-window pool and harder 125-window tier; record source/text hashes and provisional query labels. Full relevance labeling remains pending.
- [ ] Define typed, versioned tag/assertion and evidence-span contracts, including alternatives, unknown/mixed, and review states.
- [ ] Write provisional labels and decision thresholds before running systems; keep ambiguity and reviewer disagreement visible.
- [x] Compare raw/static lexical baselines and deterministic appended-tag arms on the same inputs. Separate candidate filters and the harder semantic comparison are complete; verified metadata and human relevance labels remain pending.
- [ ] Report per-part/document-type errors, citations, unsupported claims, and all limitations before deciding whether to continue.

## Risks to test

The offline design audit is saved at `artifacts/v2-pivot-20261011/design-review.json`. Before deciding on the pivot, compare raw-only retrieval against the same raw text with proposed metadata; raw versus normalized text alone cannot show tagging value. Until all pool windows have relevance labels, report intended-target ranks/hits rather than precision or recall. Explicit unanswerable, mixed-speaker and unknown-date controls are required, and exact quotations need entailment review. Qwen3 embedding 4B and 8B are installed; native 4B inference works. The first embedding sample saturated at all intended targets ranked first and cannot establish comparative quality.

- OCR errors may obscure names, dates, or legislative references; adding tags can give false confidence if evidence spans do not support them.
- Page windows can mix speakers and topics. Page-bounded chunking is a starting point, not a boundary detector.
- Historical names, offices, parties, and bill numbers require period-appropriate, sourced authorities; contemporary name matching is insufficient.
- Easy index entries may inflate results. Stratify and report by proceedings, index, and Appendix rather than only an aggregate score.
- Loose discovery labels may help search but must not leak into accepted structured filters or grounded answers.
- A small purposive POC can reject an unsafe approach or reveal a promising one; it cannot establish corpus-wide quality.

## Current evidence and provisional direction

The unchanged-OCR route is **promising but not ready for full processing**. Qwen and Mini can summarize selected substantive passages despite OCR noise; source evidence and attribution remain harder than general comprehension. The first 4B embedding experiment successfully indexed fifty paired raw/static windows (110 inputs including queries, 140.867 seconds), but all ten queries ranked their intended target first, so it establishes functioning infrastructure rather than a quality advantage. The harder 125-window lexical experiment put 25/29 intended targets first on raw versus 24/29 on static; distractor relevance is unannotated, so these are not precision/recall estimates.

Appending broad deterministic tag words to BM25 text did not improve raw hit@1 and reduced MRR (0.931 → 0.9164), including the Dakota target dropping rank 1 → 13. That tests one use of tags, not whether separately stored filters or ranking fusion help. Regex name cues are not speaker assignments, and exact source spans do not prove the role attached to them. Do not populate hard historical filters from these candidates.

Six matched Mini calls on the first three targets took 16.691 seconds and approximately $0.015387 at uncached token rates; all six still require review. This is diagnostic replication of known Qwen failures, not a held-out model benchmark. Paired source/model outputs and a pending human rubric are saved in `artifacts/v2-pivot-20261011/mini-matched-review/`. The latest prompt-only diagnostic and terminal status belong in `PROGRESS.md`, which supersedes older checkpoints.

A defensible next evaluation must separate (1) retrieving relevant raw passages, (2) correct evidence-backed roles/topics/dates with unknown/mixed handling, and (3) grounded answers. Test separate discovery metadata rather than concatenating all tags into prose; use held-out queries and independent relevance/role labels. Retain optional cleanup for demonstrated OCR-sensitive misses instead of treating perfect cleanup as a prerequisite. Human review and a broader independently labeled benchmark remain necessary before recommending corpus-wide processing.

A prompt-only three-raw-case Mini diagnostic improved literal evidence and letter-author separation in one case (one validated/two review; 8.259 seconds, approximately $0.007323). It still missed a floor speaker and retained malformed `186-1` as a literal cue, not a resolved historical date. These observed limitations reinforce separate role/date validation and explicit unknown values. The harder Tier-2 semantic benchmark and separately scored metadata filtering/fusion are now complete below. Next: evidence-ID role selection and human review; no corpus-wide processing recommendation yet.

## Harder semantic and separate-filter evidence

The Tier-2 semantic comparison completed on the same frozen 125 windows and 29 questions. Native Qwen3 4B vectors put the intended passage first for 27/29 questions on both raw and static text, and within the top three for all 29. The locally derived 1,024-vector variant put 28/29 first on both layers; it is not a native 1,024 run. The two native top-ranked alternatives also support the questions according to provisional independent AI review. This remains selected-query evidence with incomplete human relevance labels, not a corpus-wide accuracy percentage.

| Retrieval over raw text         | Intended target first |    MRR |
| ------------------------------- | --------------------: | -----: |
| BM25                            |                 25/29 | 0.9310 |
| Native 2,560 semantic           |                 27/29 | 0.9655 |
| Derived 1,024 semantic          |                 28/29 | 0.9828 |
| Fixed equal-weight RRF, native  |                 25/29 | 0.9310 |
| Fixed equal-weight RRF, derived |                 26/29 | 0.9483 |

RRF used k=60, chosen before results, and required no new model calls. It helped the easy questions but hurt other bands relative to semantic search. All approaches place intended targets within the top five. Preserve exact lexical search as a separate capability; these results do not establish a universally better fusion policy. Full rankings and provenance are in `tier2/hybrid-report.json` and the semantic run directory.

Separately stored candidate filters kept the raw text and ranking intact. A Rogers cue narrowed 125 windows to five candidates and moved the target rank 2 → 1; Dakota remained first among 30 discovery candidates, avoiding the appended-tag arm's rank-13 regression. These filters were selected from known cases, and unanchored speaker cues can include mentions. Four AI-authored role fixtures distinguish floor speakers, petition presenters and letter authors but are not authority verified. Strict historical filtering therefore leaves all windows unresolved, rather than treating missing tags as confirmed nonmatches. Synthetic policy controls are excluded from historical results.

The harder embedding run used 34 new requests and 22 compatible cached batches, finishing in 168.743 seconds with 112,415 new prompt-eval tokens and $0 local API charge. An offline Pydantic-validated scan of all 19,803 current chunks measured 63,160,061 Unicode characters; simple extrapolations suggest roughly 6.1 hours by passage count or 6.3 hours by character count at the observed 4B pace. This describes the current static chunk snapshot: future raw boundaries, sustained load, context lengths and index/export time may change the result. It is not permission or a command to start full indexing.

Human review is available as the self-contained local `artifacts/v2-pivot-20261011/human-review/index.html`: 31 pending entries with exact sources, provider results and provisional assessments. Ratings download as a draft JSON file; nothing is applied to canonical data. Structural/schema/JavaScript checks passed; a rendered browser check was unavailable in this harness.

**Current recommendation:** proceed with a reviewed raw-text retrieval pilot; do not make more OCR correction a prerequisite for the next pilot. Preserve the cleanup option for demonstrated OCR-sensitive cases. Do not run full processing yet: verified speaker/date/authority metadata and human relevance/answer review remain open. Next investigate an evidence-ID protocol so models select immutable spans and controlled labels while the backend supplies literal source evidence, rather than asking models to recopy OCR text.

### Evidence-ID interface diagnostic

The five-window Mini source-span selection test completed with one valid output and four failures held by the validator. It used 21,823 input /2,705 output tokens (zero cached), 14.812 seconds summed request time, approximately $0.02854 at current token rates. Exact-source materialization eliminates quote copying only when supplied IDs are selected correctly: long composite IDs were invented in two cases, a paragraph was selected as a person candidate in another, and the mixed-turn case exceeded the 1,200-token cap. The one valid case correctly distinguished Sumner presenting a citizens’ petition from the petitioners. Independent AI review also found Burnett wrongly assigned quoted-speaker status in a rejected response; exact IDs alone cannot establish role correctness. Evidence and all failures remain preserved under `metadata-filters/span-selection/`; human ratings are pending.

Before scaling this interface, evaluate short request-local aliases mapped by the host to immutable source IDs, and split dense windows into smaller role-specific tasks. Do not fix malformed model IDs automatically, increase acceptance by weakening validation, or infer a resolved proceedings date from event/relative/OCR date cues. The matched local run is terminal: one valid/four failures, including three timeouts, 220.866 seconds, $0 API and partial usage only. Both interfaces need redesign before scaling; consult PROGRESS for exact run IDs and next steps.
