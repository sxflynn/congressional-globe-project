# Human review desk

Use the browser desk for new reviews. This page links prior answers and explains how to start it; [MASTER_PLAN.md](MASTER_PLAN.md) owns current decisions, progress and next work; the [review protocol](docs/reference/human-review-protocol.md) contains detailed agent procedures.

## OCR-repair study preparation

The human requested operationalizing the cleanup discussion. [The evaluation method](docs/reference/ocr-repair-evaluation.md) and the master now define sample preparation, independent source-image references, deterministic repair/detection, structured image audits of apparent successes, negative tests and cost measurement. HR-011 design feedback has been received and changes the default to one productive combined repair request per assigned primary target. It does not expand HR-010 or create a full transcription benchmark. Concrete new criteria/reference-reading requests must show their exact evidence, time and scope before approval; existing answered questions are not repeated. Model audit feedback is not a human grade.

## Needs your attention

**HR-013v3 · Do we need the model to write an edit list?** is ready in [the review desk](http://10.0.0.56:8501). Your v2 feedback arrived, including Request changes and the full question about edit lists. The response explains why the old design used them, shows that software can derive differences from a complete reading, and proposes a simpler full-text-first alternative. The scan/input, expected reading and actual saved-text demonstration are separated clearly; the proposed model method has not run. An optional method-direction choice concerns offline implementation only, with no model-call approval. Prior versions, your exact comment and submissions remain archived. The v1 feedback-loss issue and unrecovered original wording remain recorded separately; no Computer Use or server restart was performed.

Every scan/text example now has its own optional note box and **Save draft here** button. Enter your name at the top before saving. A draft keeps all current answers without requiring completion; **Submit review** sends your feedback to the agent inbox. Submitted notes include the exact example and must receive a recorded action/check or an explicit unresolved reason before being marked handled. Relevant concerns carry forward into later AI instructions and checks. No background model starts when you submit.

**HR-011 received and incorporated.** You requested changes: one focused image-and-OCR request should repair all supported errors in its assigned passage, including both the number and “Tlie”→“The,” and return useful proposed text. An extra image-reading pass must justify its purpose and cost. Your confirmation of “660” and all four local notes are preserved. The [revised contract draft](artifacts/ocr-productive-repair-contract-20261027-01/README.md) now carries this direction, including full text, exact changes and uncertainty in one reply; software integration and actual model fit remain to be proved; no new model run has started and no repeat review is requested. [Exact answers](docs/archive/human-review/HR-011-v2/31f55374-c6bc-4943-b50a-6b19ef2bfb05.json) · [Every-note follow-through](artifacts/hr011-feedback-20261027-01/dispositions.json).

**HR-010 received and incorporated.** Both samples need fixes. Your nine notes are preserved, including the missed “re-gard,” the importance of bracketed events, and the difficulty reading the index with repeated technical details. The saved index crop omits the preceding “Fortifications” heading shown in the OCR context; that context needs a clearer explanation. The unavailable third sample has no output for you to grade. No repeat review is requested. [Exact answers](docs/archive/human-review/HR-010-v1/3a565acf-11f7-486d-8030-f2b3b9a139fb.json) and [every-note follow-through](artifacts/hr010-feedback-20261027-01/dispositions.json) distinguish completed ingestion from the remaining repairs and display changes. The readable view now separates the index context from its selected lines, shows short original/proposed pairs, and keeps all original technical details in a closed section. Saved-note labels are shorter too. These display changes preserve your answers; the [bracket-candidate library](artifacts/bracket-cues-20261028-01/README.md) now preserves and separately labels literal bracketed cues offline. Integrating those records into repair/export and fixing the missed word remain separate work.

**HR-003 received and applied.** You approved the sample, provisional quality standards and conditional local resource limits. You requested less review; HR-009 is now answered in chat: at most three fixed anonymized outputs and ten minutes total. No repeat HR-009 browser submission is needed. No repeat of the approved questions is needed.

**HR-004 received and applied.** Both passages need wording repair even though their subjects remain clear. You identified an incomprehensible damaged word (`ra}'`) that hurt reading, and named the sample2 topics: government-document preservation/fireproof storage and the Sioux City railroad branch. Your exact free-text answers are preserved; no repeat review is requested.

HR-005-v1 and HR-008-v1 are already answered and incorporated; no repeat review is needed. HR-003 standards/resources are approved; review effort revised by HR-009; new role/date samples have not been requested.

## How evidence is presented

Each process is shown as **inputs → expected output → actual output → differences**, with concrete examples and comment boxes. Expected outputs identify whether they are agreed requirements, reviewed answers or agent-authored illustrations. Unavailable or unrun results are stated explicitly.

## Definitions while reviewing

Tap a dotted-underlined term to open a short, plain-language definition. Close it, tap outside it, or press Escape to return to the review. Opening definitions keeps your unsaved answers in place. Definitions explain the AI’s own review instructions, questions and explanations—for example, “faithful,” “paragraph boundaries,” “raw reply,” “fixed selection” and “provenance.” The original historical writing, OCR excerpts and proposed transcriptions have no vocabulary underlining. Explanatory notes around those passages still have definitions. Terms that occur only in answer choices are explained just above the choices.

## Original scan demonstration

Open [Source images](http://10.0.0.56:8501/?view=source-images) for geometry-linked scan crops: the damaged petition, an exact word/number, and two more paragraphs. Original print and unchanged OCR are displayed together. This is read-only, not another request to regrade HR-008 or an automatic correction. HR-004 is submitted; its original packet and answers remain unchanged. Future scan-assisted checks must be recorded separately from your submitted feedback.

Two new clean-reading candidate crops are also available in Source images: a quoted bill section (part1, printed page91) and connected pension debate (part3, printed page1936). These are partial source checks for the pilot, not new grading requests or accepted corpus corrections.

## Completed reviews

| Review | Your decisions and resulting work | Original answers |
| --- | --- | --- |
| HR-011-v2 · Stephen Flynn · Submitted2026-10-28 02:20:50UTC · Applied to design/plan | Needs changes: one productive combined repair request for the whole assigned target; optional extra pass needs purpose/cost justification. Human confirms660 in the shown crop. Revised contract draft complete; production integration and actual model fit remain ahead. | [Exact packet and answers](docs/archive/human-review/HR-011-v2/31f55374-c6bc-4943-b50a-6b19ef2bfb05.json) · [Four dispositions](artifacts/hr011-feedback-20261027-01/dispositions.json) · [Application receipt](docs/archive/human-review/HR-011-v2/31f55374-c6bc-4943-b50a-6b19ef2bfb05-applied.json) |
| HR-010-v1 · Stephen Flynn · Submitted2026-10-28 01:00:48UTC · Applied to plan | A/B need fixes; preserve bracketed cues; missed split word, index/context/metadata presentation and unclear unavailable status have explicit follow-up. Positive comments remain scoped to the particular examples. | [Exact packet and answers](docs/archive/human-review/HR-010-v1/3a565acf-11f7-486d-8030-f2b3b9a139fb.json) · [Nine dispositions](artifacts/hr010-feedback-20261027-01/dispositions.json) · [Application receipt](docs/archive/human-review/HR-010-v1/3a565acf-11f7-486d-8030-f2b3b9a139fb-applied.json) |
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

Saved drafts and submissions are in `artifacts/human-review/reviews.sqlite`. Enter your name before the editing form opens; it stays fixed while you write. **Save draft and change reviewer** saves the current form before unlocking the name. Entirely blank submissions are blocked. Unsaved typing can still be lost on reload. Stop the server before copying this file for backup or moving it to another machine; agents also commit exact JSON submissions/receipts when applying decisions.

## If the desk will not open

On this computer, phone or tablet, open [the review desk](http://10.0.0.56:8501) while connected to the same network. The computer running the desk must be awake, and its Wi-Fi address can change.

If a previously open tab shows an error, reopen the address in a fresh tab. Saved drafts and submitted reviews stay in the database; unsaved typing may be lost. If neither address opens, ask an agent to check the running server before restarting it. Do not delete or replace the saved-review database to fix a connection problem.

## Agent procedure

1. Follow [AGENTS.md](AGENTS.md) and the [review protocol](docs/reference/human-review-protocol.md). At startup run `uv run globe review inbox`; new submissions do not require a separate human chat message.
2. Author a versioned packet using `uv run globe review schema`; register it with `uv run globe review register docs/review-packets/PACKET.json`. Preserve source excerpts, citations, question IDs and appropriate context. Leave choices unanswered. Blind packets contain no model outputs or recommendations anywhere in their payload.
3. Export the submitted packet and exact human answers, inspect revisions and apply the latest judgment narrowly to the master plan. Commit the archive and plan, then record the applied commit reference and archive the application receipt in a second new file. Never overwrite originals, equate free-text grading with validated structured subject labels, or expand a sample judgment into a full-run approval.
4. Historical Markdown archives above remain immutable. If a human explicitly answers in chat or an old Markdown packet, preserve its exact wording and origin using the legacy archive/receipt procedure; do not manufacture a browser submission.

The master plan owns the HR register, accepted policy and progress. This file is an operator/archive pointer, not a second queue or backlog.
