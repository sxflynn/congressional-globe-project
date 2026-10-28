# Human review desk

Use the browser desk for new reviews. This page links prior answers and explains how to start it; [MASTER_PLAN.md](MASTER_PLAN.md) owns current decisions, progress and next work; the [review protocol](docs/reference/human-review-protocol.md) contains detailed agent procedures.

## OCR-repair study preparation

The human requested operationalizing the cleanup discussion. [The evaluation method](docs/reference/ocr-repair-evaluation.md) and the master now define sample preparation, independent source-image references, deterministic repair/detection, structured image audits of apparent successes, negative tests and cost measurement. HR-011 is now registered at your explicit request to review the proposed process; it is design feedback, not grading of historical passages or an expansion of HR-010. Concrete new criteria/reference-reading requests must show their exact evidence, time and scope before approval; existing answered questions are not repeated. Model audit feedback is not a human grade.

## Needs your attention

Every scan/text example now has its own optional note box and **Save draft here** button. Enter your name at the top before saving. A draft keeps all current answers without requiring completion; **Submit review** sends your feedback to the agent inbox. Submitted notes include the exact example and must receive a recorded action/check or an explicit unresolved reason before being marked handled. Relevant concerns carry forward into later AI instructions and checks. No background model starts when you submit.

**Ready: HR-011 · Small OCR studies: image, raw text, inputs and possible outputs (v2).** Open [the desk](http://10.0.0.56:8501), choose **HR-011 · v2**, and follow the numbered walkthrough: original page image, enlarged count, unchanged raw OCR, possible AI inputs and clearly marked example outputs. Dotted-underlined terms open definitions; OCR and proposed readings stay plain. Read at your own pace; optional notes and an existing independent technical evaluation can be left blank. Earlier packet/answer bytes remain preserved. Design feedback does not supply T51’s independent verdict or authorize a model run.

**Ready: HR-010 · Short source check of selected reading proposals.** Open [the desk](http://10.0.0.56:8501), choose **HR-010**, and compare the two fixed anonymized results with their scans. One full proposed reading and one rejected reply are shown; the unavailable third selection is retained without substitution. This is the already-approved review round, at most10minutes total. Stop sooner and use **Not reviewed — time limit reached** for unfinished samples. No broader approval is requested.

**HR-003 received and applied.** You approved the sample, provisional quality standards and conditional local resource limits. You requested less review; HR-009 is now answered in chat: at most three fixed anonymized outputs and ten minutes total. No repeat HR-009 browser submission is needed. No repeat of the approved questions is needed.

**HR-004 received and applied.** Both passages need wording repair even though their subjects remain clear. You identified an incomprehensible damaged word (`ra}'`) that hurt reading, and named the sample2 topics: government-document preservation/fireproof storage and the Sioux City railroad branch. Your exact free-text answers are preserved; no repeat review is requested.

HR-005-v1 and HR-008-v1 are already answered and incorporated; no repeat review is needed. HR-003 standards/resources are approved; review effort revised by HR-009; new role/date samples have not been requested.

## Definitions while reviewing

Tap a dotted-underlined term to open a short, plain-language definition. Close it, tap outside it, or press Escape to return to the review. Opening definitions keeps your unsaved answers in place. Definitions explain the AI’s own review instructions, questions and explanations—for example, “faithful,” “paragraph boundaries,” “raw reply,” “fixed selection” and “provenance.” The original historical writing, OCR excerpts and proposed transcriptions have no vocabulary underlining. Explanatory notes around those passages still have definitions. Terms that occur only in answer choices are explained just above the choices.

## Original scan demonstration

Open [Source images](http://10.0.0.56:8501/?view=source-images) for geometry-linked scan crops: the damaged petition, an exact word/number, and two more paragraphs. Original print and unchanged OCR are displayed together. This is read-only, not another request to regrade HR-008 or an automatic correction. HR-004 is submitted; its original packet and answers remain unchanged. Future scan-assisted checks must be recorded separately from your submitted feedback.

Two new clean-reading candidate crops are also available in Source images: a quoted bill section (part1, printed page91) and connected pension debate (part3, printed page1936). These are partial source checks for the pilot, not new grading requests or accepted corpus corrections.

## Completed reviews

| Review | Your decisions and resulting work | Original answers |
| --- | --- | --- |
| HR-004-v1 · Stephen Flynn · Submitted2026-10-26 02:16:06UTC · Applied | Both subjects clear but wording needs repair; damaged words disrupt comprehension. Sample2 free-text topics retained; sample1 supplied readability feedback rather than topic labels. | [Exact packet and answer](docs/archive/human-review/HR-004-v1/7d9635ca-6176-4971-b2e5-dfad247e439c.json) · [Application receipt](docs/archive/human-review/HR-004-v1/7d9635ca-6176-4971-b2e5-dfad247e439c-applied.json) |
| HR-003-v1 · Stephen Flynn · 10/24/2026 · Applied | First-pilot coverage, provisional quality and conditional local resources approved; less/different human review requested, revised effort still open. | [Exact packet and answers](docs/archive/human-review/HR-003-v1/d02da43f-cba3-4654-be1f-b9f3c72de125.json) · [Application receipt](docs/archive/human-review/HR-003-v1/d02da43f-cba3-4654-be1f-b9f3c72de125-applied.json) |
| DEMO-001-v1 · Stephen Flynn · Practice acknowledged | Practice submission preserved and acknowledged; no historical labels or policy changes. | [Exact answer](docs/archive/human-review/DEMO-001-v1/968f885a-c4ae-4ea3-8f56-59203d63ff97.json) · [Applied receipt](docs/archive/human-review/DEMO-001-v1/968f885a-c4ae-4ea3-8f56-59203d63ff97-applied.json) |
| HR-005-v1 · Stephen · 10/24/2026 · Applied | You confirmed the damaged-name reply is Mr. Wade in this specific context. Recorded as a human-reviewed attribution success; no blanket damaged-name rule or OCR rewrite. | [Full questions and your unchanged answer](docs/archive/human-review/HR-005-v1/original.md) · [Processing receipt and source-linked decision](docs/archive/human-review/HR-005-v1/receipt.json) |
| HR-008-v1 · SF · 10/22/26 · Applied | S1: voting rights acceptable, B+; explore finer topics. S2: reject military inference, favor caution; explore source-image crops and protect petition discovery. S3: compensation acceptable, procedure incidental here. Carry speaker context across pages. | [Full questions and your unchanged answers](docs/archive/human-review/HR-008-v1/original.md) · [Processing receipt](docs/archive/human-review/HR-008-v1/receipt.json) |

These were diagnostic sample judgments, not approval of a full run or a decision to skip OCR cleanup. No need to answer them again. New evidence or a materially different question gets a new packet/version.

## Use the browser desk

From this project folder, run:

```bash
make review
```

Open [the review desk](http://10.0.0.56:8501). Enter your name, review the evidence, and choose **Save draft** or **Submit review**. Submitted reviews wait for an agent to apply them; you do not need to edit Markdown or announce completion in chat. Agents check the inbox at their next work turn. This is not an always-running background agent.

Try `make review-demo` for an invented practice example. Practice answers are not historical labels or project decisions. The app supports system light/dark preference and phone screens. Open the LAN address above from a device on the same network —no login or access code is needed. The IP may change with your network.

Saved drafts and submissions are in `artifacts/human-review/reviews.sqlite`. Unsaved typing can be lost on reload. Stop the server before copying this file for backup or moving it to another machine; agents also commit exact JSON submissions/receipts when applying decisions.

## If the desk will not open

On this computer, open [the local desk](http://127.0.0.1:8501). On your phone or tablet, use [the Wi-Fi address](http://10.0.0.56:8501) while connected to the same network. The computer running the desk must be awake, and its Wi-Fi address can change.

If a previously open tab shows an error, reopen the address in a fresh tab. Saved drafts and submitted reviews stay in the database; unsaved typing may be lost. If neither address opens, ask an agent to check the running server before restarting it. Do not delete or replace the saved-review database to fix a connection problem.

## Agent procedure

1. Follow [AGENTS.md](AGENTS.md) and the [review protocol](docs/reference/human-review-protocol.md). At startup run `uv run globe review inbox`; new submissions do not require a separate human chat message.
2. Author a versioned packet using `uv run globe review schema`; register it with `uv run globe review register docs/review-packets/PACKET.json`. Preserve source excerpts, citations, question IDs and appropriate context. Leave choices unanswered. Blind packets contain no model outputs or recommendations anywhere in their payload.
3. Export the submitted packet and exact human answers, inspect revisions and apply the latest judgment narrowly to the master plan. Commit the archive and plan, then record the applied commit reference and archive the application receipt in a second new file. Never overwrite originals, equate free-text grading with validated structured subject labels, or expand a sample judgment into a full-run approval.
4. Historical Markdown archives above remain immutable. If a human explicitly answers in chat or an old Markdown packet, preserve its exact wording and origin using the legacy archive/receipt procedure; do not manufacture a browser submission.

The master plan owns the HR register, accepted policy and progress. This file is an operator/archive pointer, not a second queue or backlog.
