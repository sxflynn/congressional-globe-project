# Engineering and recovery rules

Read this before implementation or worker recovery. [MASTER_PLAN.md](../../MASTER_PLAN.md) is the only current queue, ownership and progress record. Task-specific policies are in its reference map; read only those needed.

## Complete one unit

1. Inspect actual Git/files and durable evidence. Claim the task, owner, paths, bounds and checkpoint in the master before editing. Record the decision/proof the unit advances.
2. Implement the smallest change that satisfies the task's checks. Use uv and Pydantic v2 at external-data boundaries; stream large corpus files. Keep cyclomatic complexity≤5 and tests focused on meaningful success/failure cases.
3. Preserve source/hash/span evidence, original OCR, accepted text/ledgers, prior proposals and failed experiments. Derived work goes under `artifacts/`; disposable scratch under `tmp/`. Never touch the separate `tmp/performance/` investigation or expose ignored `.env` secrets.
4. Run the checks below. Update the master execution task, its parent work-package/subtask and the stage status in that order; keep dependencies and next eligible action synchronized. A stage closes only when its exit evidence is satisfied. Append a compact dated changelog entry and commit. Report result, checks, limits and what remains. Never leave completion evidence only in chat.

Use Luna delegates for bounded preparation/review when available, as requested by the human; name ownership and inspect their findings. If the harness cannot provide that model, do not invent delegation or model identity. AI review is not a human grade.

## Closing a run blocker

The master names the current checkpoint and owns the only ordered task list. For work supporting a blocked experiment, state the exact missing evidence/resource or unresolved decision, how this unit addresses it, and which executable action follows. A new helper, contract, schema, fake-server test or inventory is not proof that the installed backend works. Reuse completed evidence; do not repeat a spent investigation under a new task number.

End each blocker task with actual closure evidence or a concrete decision for the human: recommended option, alternatives, exact affected commands/resources/source identities, proposed call/time/fetch/token limits, costs/unknowns and the rule that needs changing. Complete reversible preparation first. If a prerequisite cannot be satisfied, explain the precise missing input and consequence; do not keep calling it “future integration.” New prerequisite work must link directly to an open gate in the master and have its own bounded exit check.

Keep software requirements separate from natural/model limits. A candidate study token ceiling is not the model's measured context capacity. Inspect whether real capture/stop code can produce and accept the required evidence; a validator that deliberately refuses every authentic-producer claim cannot be cleared by another authored fixture. Make any circular bootstrap explicit, such as requiring actual stopping evidence before allowing the only probe that could produce it. Prepare a bounded probe and its consumption/authority decision rather than bypassing the gate. No extra call, download, scope change, cap raise or gate waiver is implied.

Previously recorded human approval remains effective within its exact scope. Ask only about material changes not already covered. Retain raw results, unknown usage, independent checks, sequential Ollama ownership and the separate production/full-corpus decisions. Plain-English reports must distinguish preparation, actual timed runs, provisional findings, quality evidence and forecasts with measured versus assumed inputs.

## Validation and commits

- Code: `make gate` from repository root. It formats with Ruff/Prettier, then checks Ruff, ty, complexity≤5 and pytest. For Codex run with the permissions needed by the required Markdown formatter. Do not skip or weaken checks.
- Markdown: elevated `npx prettier@3.9.10 --prose-wrap never --write "**/*.md"`, then `git diff --check`; check affected links and archives when splitting instructions. Historical snapshots under `docs/archive/` are excluded from formatting and must retain exact bytes.
- Documentation-only edits do not need another full code gate; state which structural/content checks were done and retain the last code-gate evidence.
- Commit completed units with a single-line message ending in `[model: ACTUAL KNOWN MODEL]`, or `[model: unknown]`. Stage selected changes; never sweep secrets, scratch or another agent's work into a commit. Deliberately force-add only the evidence artifacts needed for a portable handoff.

## Runtime recovery — only when the task needs workers

A documentation/offline task does not need a full runtime investigation. Before starting, resuming, interrupting or reconciling model work:

1. Read the named run's config, attempt/task journal, stored outputs and previous checkpoint. A historical shell/session ID is not proof it is live.
2. Inspect current PID **with start time and full command**, queue claims and bounded fresh logs. On Mac use a targeted process listing from `ps -axo pid,lstart,etime,command`; filter locally instead of dumping all processes. For Ollama use `uv run globe ollama logs query` first. A loaded model, lock-file presence, inspection denial or observation timeout alone does not establish active/idle/dead state.
3. If a worker is running, do not duplicate, restart or interrupt it merely to recover context. Continue separate offline work. If observation is unavailable, record `observation_unknown` and keep useful independent work moving; do not relaunch an unknown attempt.
4. If terminal/interrupted, retain exit/cancellation evidence and reconcile durable tasks/results. Preserve unknown usage. Reuse compatible saved requests/results; changed inputs/config/code need deliberate versioning, not a hidden repeat. Do not overwrite failed runs or silently fix rejected output.
5. Before a new request, record the POC rationale, exact input/model/runtime hashes, call/time/output budget, prior cumulative consumption, no automatic retries and stopping rule. Verify no competing worker/cleanup claims. Use the actual shared lock and strictly sequential Ollama calls. Downloads, corpus-wide jobs and recurring work need explicit human authorization.
6. Record launch intent before requests, OS identity immediately after launch, incremental results/checkpoints and terminal evidence before releasing ownership. The master active-work row must let another harness recover without chat history.

The generalized arbitrary-crash/cross-harness recovery guarantee is still an M2 milestone; current journals and timeout recoveries do not certify it.

## Capability and uncertainty

State whether this harness can inspect raster images. A no-vision agent can implement contracts, audit raw text, check hashes, replay saved outputs and prepare fixtures. It cannot certify source print. A vision-capable agent can inspect a bounded hash-bound cached crop after checking ownership; this does not authorize fetching more images, re-running models or editing canonical OCR. Missing vision alone is not a project blocker.

Keep structural validity, source fidelity, provenance, uncertainty, review status and historical truth distinct. Never claim full readiness from schema passes, fluent output, a tiny winning sample or unchanged raw text returned as `needs_review`. Distinguish requirements drafted, implementation complete, checks passed, source/quality reviewed and human acceptance. Each DONE claim names which of these it proves; a design draft cannot satisfy an implementation/backend-compatibility exit check.

## Automation and ergonomics review

New scripts, commands, workflows or one-command automation proposals require an independent GPT-6 evaluation with verdict and risks recorded in the master **before adoption**. Do not automatically invoke GPT-6; the human runs that review unless explicitly instructed. The implemented Ollama log tool was an explicit human-directed exception; its retrospective findings are resolved. The existing independent pickup evaluation approves only the minimal read-only status/verify scope in [pickup-tooling.md](pickup-tooling.md); broader wrappers remain deferred.

The human explicitly ordered the2026-10-25 instruction split and clearer work-selection sequence. That order authorizes this documentation structure; it does not authorize new provider workloads or the broader automation proposal.

## Human interaction

Run the review inbox at startup. Read [the review protocol](human-review-protocol.md) before authoring/applying packets or answers. Never fabricate a submission, edit review SQLite directly, let an older revision replace a newer answer, or treat silence/AI review as approval. Reuse actual authorization, keep independent work moving and notify the human only with a concrete packet when a checkpoint needs them. The review desk intentionally has no authentication on the single-user LAN; do not add access codes unless deployment scope changes at human request.
