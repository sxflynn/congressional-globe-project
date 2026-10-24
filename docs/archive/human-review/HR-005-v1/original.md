# Human review desk

Read requests here, write in **Your response**, save, then tell the agent “I answered the review.” The agent must incorporate your answers into [MASTER_PLAN.md](MASTER_PLAN.md), archive your original wording, and clear the completed set from this desk. The master plan owns policy, progress and next work.

## Needs your attention

**[HR-005-v1: one speaker-attribution judgment](#hr-005-v1--can-context-resolve-a-damaged-speaker-name)** is ready below (about 2 minutes). HR-008 remains completed. HR-003 standards and HR-004 blind grading have not yet been presented.

## HR-005-v1 — can context resolve a damaged speaker name?

**Prepared/notified:** 2026-10-23; H2/H3, M1. One new output-informed calibration question, not a blind benchmark or full-run approval. Your previous topic grades and cross-page requirement remain applied.

**Source:** Part 5, printed pages 4131–4132, scan leaves 403–404, IA item [congressionalglo7395unit](https://archive.org/details/congressionalglo7395unit). These are exact OCR excerpts; the item link is not a verified direct image-page link. Full ordered context and source anchors are saved in the linked packet below.

**What we tested:** Mini and local Qwen read the previous page and the next page together. Both connected the continued passage to the earlier **Mr. WADE** and kept **Mr. SUMNER** as a separate interruption. The unresolved question is the damaged name after Sumner, not whether page breaks can continue a speech.

**Earlier named turn, previous page — exact opening excerpt:**

> Mr. WADE. I am not able to say what the aggregate of the proposed increase is. I do not know how much it will amount to. I have never summed it up. This proposition adds to all these employes about twenty-five per, cent,

**Previous page ending — exact excerpt:**

> yes at least twenty-five per cent. I do not think there is anything extravagant in this proposi- tion for the equalization of these salaries. The

**Next page body opening — exact excerpt:**

> House came to a conclusion on the subject as to what they supposed their employes ought to have, and I believe they passed a resolution giving their employes the salaries which this amendment proposes to give'the corresponding officers of t

**Later interruption — full paragraph:**

> Mr. SUMNER. Yv"ho isthat?

**Reply with damaged name — exact opening excerpt:**

> Mr. Yv'ADE. I am speaking of the Sergeant- at-Arms ; and I will speak of some other gen- tlemen here, not particularly under him, that we have to deal with daily, who, I think, are entitled to our commendation for their con- stant, faithful attendance to their duties. I know of no reason why. if salaries are to be enhanced, there is anyth

**Both model proposals:** treat that last reply and its following paragraph as **Mr. Wade speaking**, using the surrounding exchange to interpret `Yv'ADE`. The original OCR stays unchanged. These are person-link proposals, not verified authority records.

**Agent recommendation:** keep this as a proposed match requiring review until we establish an evidence rule for damaged names. The conservative pre-run expectation requested uncertainty, but this is a plausible contextual identification, not an established historical mistake. We need your research standard here.

**Your question:** For this specific reply, is the evidence sufficient to include it when filtering for Mr. Wade, or should it remain uncertain until stronger evidence (such as the scan or a verified roster) is checked? This does not approve automatically resolving every misspelled name.

### Your response — HR-005-v1

- **Treatment:** Yes, the AI was correct, it is Mr. Wade, yes.
- **Reason or condition:** No reason, it was just correct in this instance.
- **Name/date, optional:** Stephen 10/24/2026

### Agent follow-up — HR-005-v1

Awaiting your answer. Offline engineering can continue; calling this damaged-name normalization accepted waits for your judgment. All proposals remain separate from canonical OCR. No validated human-label import or corpus processing has occurred.

[Full frozen packet and source expectations](artifacts/role-alias-preparation-20261023-02/source-review.json) · [Mini results](artifacts/role-comparison-20261023-02/mini/summary.json) · [Qwen results](artifacts/role-comparison-20261023-02/qwen/summary.json) · [Paired source review and cost/timing](artifacts/role-comparison-20261023-02/comparison-review.json).

The other test asked models to recognize an unnamed speaker. Both abstained meaningfully, but their responses failed different output-contract checks. Those are engineering issues for the agent to fix; you do not need to review JSON formatting.

## Completed reviews

| Review | Your decisions and resulting work | Original answers |
| --- | --- | --- |
| HR-008-v1 · SF · 10/22/26 · Applied | S1: voting rights acceptable, B+; explore finer topics. S2: reject military inference, favor caution; explore source-image crops and protect petition discovery. S3: compensation acceptable, procedure incidental here. Carry speaker context across pages. | [Full questions and your unchanged answers](docs/archive/human-review/HR-008-v1/original.md) · [Processing receipt](docs/archive/human-review/HR-008-v1/receipt.json) |

These were diagnostic sample judgments, not approval of a full run or a decision to skip OCR cleanup. No need to answer them again. New evidence or a materially different question gets a new packet/version.

## How agents close a review

1. Read the actual answers when the human reports completion; leave genuinely unanswered required questions open.
2. Archive the exact answered packet before editing this desk. Preserve questions, source excerpts, model proposals, sample IDs, original answers and reviewer/date; record its hash and original path. Archive snapshots are immutable and excluded from formatting.
3. Apply each answer narrowly in the master plan: accepted judgments, conditions, unresolved policy, backlog, affected next POC and human-request state. Distinguish an implemented change from a planned experiment. Preserve human-reported image readings separately from verified OCR patches.
4. Add an agent processing receipt, verify the archive hash and all decisions, then replace the completed packet here with a short linked receipt. Keep this desk focused on active requests; optional blank demo feedback is not an unanswered required grade.
5. Format the edited documents, commit the completed unit and briefly tell the human what was adopted and what comes next. Never erase original answers, invent missing responses, or treat sample feedback as broader authorization.

## Template for future agent requests

**Template only—no human response requested until an agent creates a concrete item with a real HR ID.** Keep the active queue small. After the human confirms completion, archive the exact answered packet, apply its decisions to the master plan, and replace it here with a compact completed receipt.

### Agent prepares

- **ID / version / master-plan gate / related milestone:**
- **Plain-language title and specific question:**
- **Why this decision matters; recommendation and alternatives:**
- **Evidence or demo:** exact source excerpts, context/citations and proposed output; identify whether source-only blind grading or output-informed calibration. Include expected/observed behavior and safe demo steps. No hidden model call in a supposedly read-only demo.
- **Scope, cost/time and review effort:**
- **What waits; what work continues:**
- **If a run is being requested:** exact command, provider/configuration, request/runtime/spending limits, recovery/stop behavior and known risks. Ordinary sample grades are not full-run approval.
- **Delivery:** when/how the human was notified; current state remains in the master HR register.

### Your response

- **Decision or grades:** _Write here._
- **Corrections, conditions or uncertainty:** _Write here._
- **Date/name, optional:** _Write here._

### Agent applies and reports back

- **Actual answer and provenance:** preserve the original human response; do not overwrite it with a summary.
- **What changed / effective policy scope / unresolved items:**
- **Master-plan HR/readiness updates and evidence links:**
- **Next check or reopening condition:**
