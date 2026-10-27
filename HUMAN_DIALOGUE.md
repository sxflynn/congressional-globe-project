# Human dialogue notes

## 2026-10-27 — detecting and fixing damaged OCR

These are discussion notes, not a verbatim transcript, final cleanup policy, task queue or authorization for model/corpus runs. [MASTER_PLAN.md](MASTER_PLAN.md) remains the only current roadmap and ownership record. The human explicitly requested this file so ideas raised in conversation are retained. New ideas can be appended here with their decision status kept clear.

### Direction expressed by the human

- Steer the effort toward **measuring the efficacy of fixing damaged OCR**. The human wants a back-and-forth discussion before final decisions or implementation changes.
- Consequential damaged words matter even when a paragraph's general subject is understandable. Damaged names and years can be especially important to research.
- The human expressed frustration with repeatedly evaluating whether cleanup is needed. The proposed emphasis is how to repair damage effectively and what that repair process costs. This has not yet selected a final cleanup policy or closed P0.
- Prefer a workflow that uses deterministic CPU processing wherever practical, with AI as a fallback for uncertainty rather than assuming every passage needs an expensive model call.
- Explicit current authorization: take notes of this conversation. This supersedes the earlier request to avoid document changes only to the extent of recording the discussion and its bookkeeping; it does not authorize implementing the discussed pipeline.

### Sample-based investigation proposed by the human

- Draw a random sample from the whole collection, then attempt cleanup on that sample.
- Use the sample to learn whether the proposed workflow works, not simply assume it will.
- Sample unit and size are undecided: the human mentioned a whole page as one possibility.
- No sample has been drawn for this new proposal. No new model run, full-corpus scoring pass or new human review round was authorized by the discussion.

### Deterministic repairs, dictionaries and candidate detection

- Repair recognizable OCR patterns with deterministic scripts, including words split by line-ending hyphens when the evidence supports joining them.
- Use a dictionary/spell check to flag nonsense or unfamiliar words.
- Investigate suitable nineteenth-century vocabulary resources, plus names of cities and other proper names. No particular dictionary, library or authority source has been researched or selected in this discussion.
- Consider an intermediate step that proposes possible dictionary readings for a damaged word.
- When a reading is uncertain, show an image-capable model such as Qwen the original image crop, surrounding text and the problematic OCR, and ask what is actually printed.
- The human considered whether every word failing spell check, and suspicious letter/digit mixtures, should be routed to AI. Routing rules are still proposals, not agreed thresholds.

### Numbers, names and errors that pass spell check

- The assistant explained that wrong text can still be a valid word or number: a misread year can look entirely plausible, and a damaged name can become another dictionary word. These were illustrative examples, not newly observed corpus findings.
- The human responded positively and emphasized a distinction: ordinary words occupy a constrained vocabulary, while arbitrary digit sequences can all look like valid numbers.
- The human proposed treating numbers as always suspect, meaning candidates for verification rather than relying on spell check. Whether all numbers should receive image/AI inspection remains open.
- The assistant suggested separating “needs verification” from “known wrong,” and considering names and numbers separately from ordinary vocabulary. No date-range rule or numerical threshold was agreed.

### Static confidence or risk scoring proposed by the human

- Develop a deterministic algorithm, ideally using established algorithms and Python libraries, that assigns a confidence-like score to a page or another text unit.
- The human's central validation question: **does the score match reality?** Compare its predictions with actual OCR damage found in the source images.
- If useful, run the inexpensive scorer across the collection and prioritize the lowest-confidence material for cleanup.
- The human expects this CPU-based pass to be fast, potentially seconds, but that is a hypothesis; runtime has not been measured and no such performance claim is established.
- The assistant proposed initially calling it a **risk score**, reserving probability/confidence interpretations until validated or calibrated against observed errors.
- Candidate signals suggested by the assistant: unfamiliar-word proportion, damaged-character patterns and original OCR-engine word-confidence values where available. Availability, reliability, weights and any chosen library remain unverified for this proposal.
- The assistant suggested keeping local flags alongside page scores: one damaged year or name might be consequential while barely affecting a page average.
- Prioritization policy, scoring direction, thresholds and how to weight consequential errors are unresolved.

### Assistant suggestions discussed, not final decisions

- Separate detecting suspicious text from deciding what the image says. Dictionary absence does not prove an error, and dictionary presence does not prove correctness.
- Preserve raw OCR and record derived edits with their supporting source evidence; allow “uncertain” instead of forcing a correction.
- Consider asking the model to read the image before showing dictionary suggestions, to reduce the chance suggestions steer the answer. This ordering was not agreed.
- Compare flag-only AI inspection with AI inspection of all passages **within a bounded sample**, to measure what the detector misses. The human asked for an example and responded positively to the wrong-but-valid-year example; the exact comparison design is not approved.
- Consider a random sample across all five parts, plus a separately reported difficult-case set of damaged names, dates and words. The latter is an assistant suggestion, not an approved sample design.
- Inspect some unflagged or high-confidence text so missed damage can be measured. For score validation, sample across score ranges, not only the worst-scoring pages.
- Evaluate fixes against independently established readings of the source images. Model confidence, fluent text, or passing software validation alone does not establish a correct transcription. Who supplies those readings and how much review is feasible remain open; existing review limits are not expanded by these notes.

### Costs and scope questions still open

- How many candidates are flagged, which categories dominate, and how many model/image requests does that imply?
- How often are proposed repairs correct, wrong, uncertain, or unnecessary? What important damage is missed entirely?
- How much CPU time, model time, image handling, human review and hardware/energy cost would the workflow require?
- How should spelling, names, places, dates and other numbers be treated differently?
- Which sample unit, size and selection method can answer those questions within explicit bounds?
- Which existing deterministic rules, dictionaries, source confidence fields and saved evidence can be reused without rerunning spent experiments?

No answers or thresholds are invented here. The previously recorded six-paragraph date result and raw/static search results remain small engineering/diagnostic evidence, not validation of this newly discussed detector-and-repair workflow. Final cleanup policy and full-corpus processing remain separate human decisions.

### Follow-up — what the score is for

- The human clarified that the desired destination is to clean everything, so prioritizing a subset may not be the main reason to develop a score. This expresses the intended destination, not authorization to launch a full-corpus run.
- The human is questioning whether a confidence score is worthwhile and suggested its purpose may instead be **predicting accuracy before processing**. This remains exploratory, not a selected scoring method.
- Distinguish two possible targets for discussion: how damaged the input OCR is versus how reliably the proposed cleanup workflow will repair it. These are different measurements; no validated relationship or probability estimate exists yet.

### Tentative agreement — test predictive scoring alongside cleanup

- The human said “I'm kind of on board” and explicitly asked to add the proposal to this document. Record this as tentative agreement to the investigation idea, not final approval of a scoring algorithm, sample, budget or model run.
- On the eventual bounded sample: calculate the candidate score **before** cleanup, run the selected cleanup approach, then check results against the source images. Test whether the score predicts correct repairs, missed errors, newly introduced errors and need for human review.
- Use predictive scoring only if measured results show it helps forecast cleanup reliability or review workload across the intended collection. If it does not, defer further investment.
- Scoring is optional and should be tested alongside cleanup; it is not a prerequisite that delays the cleanup experiment. Exact evaluation design and independent reference readings remain to be agreed.

### Open discussion — “negative testing” and false reassurance

- The human emphasized a preference for “negative testing,” citing text the system thinks is clean but actually is not, and asked the assistant to interpret the intended meaning.
- Provisional assistant interpretation, awaiting confirmation: deliberately test failure cases and false reassurance, especially important errors left in apparently clean/high-confidence text. Distinguish missed damage from unnecessary or harmful changes to genuinely correct text. No test suite or final evaluation design has been selected by this exchange.

### Requested addition — image-grounded audit after deterministic cleanup

- The human proposed a concrete negative-testing step and explicitly requested that it be added to the list. Even when deterministic cleanup reports success or no remaining errors, give an image-capable model, ideally Qwen, the original OCR, deterministic changes, resulting text, spell-check results and other diagnostic results, together with the original page image or relevant source crop.
- Ask the model to identify mistakes or omissions and return **structured feedback**, rather than merely declaring the text clean. The purpose is to challenge apparent success and identify damage missed by rules, incorrect deterministic edits and differences from the printed source.
- The exact feedback fields, sample coverage, model capability, budget and handling of disagreement remain to be designed. Possible fields for later discussion include affected span, issue category, supporting image evidence, proposed reading and uncertainty; these are assistant suggestions, not an approved schema.
- This is a requested evaluation-design addition, not authorization to dispatch the model or audit the whole collection. A model reporting no issue does not prove the absence of errors; independent source checks are still needed to measure the auditor's own misses and false alarms. The assistant's spoken phrase “prove that nothing important was missed” should be understood as the goal to test, not an established capability or guarantee.
