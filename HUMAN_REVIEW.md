# Human review desk

Use the browser desk for new reviews. This page links prior answers and explains how to start it; [MASTER_PLAN.md](MASTER_PLAN.md) owns policy, progress and next work.

## Needs your attention

**HR-003 received and applied.** You approved the sample, provisional quality standards and conditional local resource limits. You requested less review or a different review plan; that follow-up remains open. No repeat of the approved questions is needed.

**Ready in the browser: HR-004 · Two real passages: topics and OCR readability.** About 5–8 minutes: read two unchanged Congressional Globe excerpts (parts 2 and 3), identify the subjects, and tell us whether OCR damage prevents understanding. No model answers are shown. Open [the desk](http://10.0.0.56:8501), select **HR-004**, and submit your answers there. You do not need to edit this file.

HR-005-v1 and HR-008-v1 are already answered and incorporated; no repeat review is needed. HR-003 standards/resources are approved; review effort needs revision; new role/date samples have not been requested.

## Definitions while reviewing

Tap a dotted-underlined term to open a short, plain-language definition. Close it, tap outside it, or press Escape to return to the review. Opening definitions keeps your unsaved answers in place. Instructions, questions and evidence use the same glossary; terms that occur only in answer choices are explained just above the choices.

## Original scan demonstration

Open [Source images](http://10.0.0.56:8501/?view=source-images) for geometry-linked scan crops: the damaged petition, an exact word/number, and two more paragraphs. Original print and unchanged OCR are displayed together. This is read-only, not another request to regrade HR-008 or an automatic correction. HR-004 remains under Pending; if you consult its scans, note that in your response so image-assisted judgments are not treated as OCR-only readability evidence.

## Completed reviews

| Review | Your decisions and resulting work | Original answers |
| --- | --- | --- |
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

## Agent procedure

1. Follow [AGENTS.md](AGENTS.md) and the master plan's browser review protocol. At startup run `uv run globe review inbox`; new submissions do not require a separate human chat message.
2. Author a versioned packet using `uv run globe review schema`; register it with `uv run globe review register docs/review-packets/PACKET.json`. Preserve source excerpts, citations, question IDs and appropriate context. Leave choices unanswered. Blind packets contain no model outputs or recommendations anywhere in their payload.
3. Export the submitted packet and exact human answers, inspect revisions and apply the latest judgment narrowly to the master plan. Commit the archive and plan, then record the applied commit reference and archive the application receipt in a second new file. Never overwrite originals, equate free-text grading with validated structured subject labels, or expand a sample judgment into a full-run approval.
4. Historical Markdown archives above remain immutable. If a human explicitly answers in chat or an old Markdown packet, preserve its exact wording and origin using the legacy archive/receipt procedure; do not manufacture a browser submission.

The master plan owns the HR register, accepted policy and progress. This file is an operator/archive pointer, not a second queue or backlog.
