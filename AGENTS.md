# Agent entry point

**Read [MASTER_PLAN.md](MASTER_PLAN.md) before doing project work.** It is the single authoritative source for the project goal, scope, architecture, ordered milestones, current progress, evidence, operator commands and engineering rules. New human instructions take precedence.

**Any stateless Codex, OpenCode or other agent starts with the master's “Stateless startup and mid-flight recovery” procedure and shared live work record.** Also read [HUMAN_REVIEW.md](HUMAN_REVIEW.md) for new human responses and pending questions before choosing work. Do not depend on chat history or another harness's terminal IDs. Inspect actual processes and durable results, record ownership/checkpoints, and keep P0—the still-open value of further OCR cleanup—part of the active plan.

- Maintain `HUMAN_REVIEW.md` as the human-facing desk: concrete decisions, source samples/demos and blank response areas. Preserve human-authored answers; never fill or overwrite them. Read new responses at startup, apply them within scope, and sync the master HR register and agent follow-up. This companion is not a second plan.
- Follow the master's H1–H6 human checkpoints and shared HR register. Explicitly tag the human with a concrete packet when a decision or sample grade is needed; record actual requests/answers and blocking scope. Never treat AI review or silence as human approval. Reuse existing authorization and keep independent work moving instead of asking permission for routine tasks.
- Advance its current milestone and next decision; check actual files, Git and run state before acting.
- Update its current status, milestone/evidence tables and next action after each unit and before handoff. Do not create another plan, progress file or competing backlog.
- `PROGRESS.md`, `PROJECT_GOAL.md`, `V2_*`, `RUNBOOK.md`, `HAPPY_PATH.md` and `TAG_ARM_PROMPT.md` are compatibility pointers. Their archived originals are historical evidence, not current instructions or commands to execute.
- Preserve immutable sources, accepted ledgers and prior experiments. Keep bounded POCs separate from human-launched full workloads. Use Luna delegates for bounded preparation/review when available, following the master plan.
- Use uv and Pydantic v2; preserve source evidence and uncertainty. Keep Ollama sequential, inspect existing workers/queues and never expose secrets.
- Follow the master's validation/formatting rules, including `make gate` before code handoff, complexity≤5, and elevated `npx prettier@3.9.10 --prose-wrap never --write "**/*.md"` for Markdown edits when using Codex.
- Commit completed units with a single-line message and no agent attribution. Do not touch the separate investigation in `tmp/performance/`.

`README.md` is a short human tutorial, not a second project plan. The original documents are preserved under `docs/archive/2026-10-22-pre-masterplan/`; their original hashes are in its `manifest.json`.
