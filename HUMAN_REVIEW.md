# Human review desk

Read requests here, write in **Your response**, save, then tell the agent “I answered the review.” The agent must incorporate your answers into [MASTER_PLAN.md](MASTER_PLAN.md), archive your original wording, and clear the completed set from this desk. The master plan owns policy, progress and next work.

## Needs your attention

**Nothing currently awaiting your response.** HR-005-v1 and HR-008-v1 are answered and incorporated. HR-003 standards, HR-004 blind grading, and any new role/date calibration set have not yet been presented.

## Completed reviews

| Review | Your decisions and resulting work | Original answers |
| --- | --- | --- |
| HR-005-v1 · Stephen · 10/24/2026 · Applied | You confirmed the damaged-name reply is Mr. Wade in this specific context. Recorded as a human-reviewed attribution success; no blanket damaged-name rule or OCR rewrite. | [Full questions and your unchanged answer](docs/archive/human-review/HR-005-v1/original.md) · [Processing receipt and source-linked decision](docs/archive/human-review/HR-005-v1/receipt.json) |
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
