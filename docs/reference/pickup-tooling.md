# Approved scope for agent pickup tooling

Read this only when your task needs it. [MASTER_PLAN.md](../../MASTER_PLAN.md) owns current tasks, ownership, progress and next actions; this file owns detailed reference material.

**Design reference.** The minimal status/verify scope was independently evaluated at the human’s request; both commands are still unimplemented. The broader original proposal is not approved wholesale. Only the master queue selects and owns implementation work.

#### Agent pickup ergonomics and offline one-command flow (GPT-6: approve minimal status/verify with changes; unimplemented)

**Human request, 2026-10-25:** a stateless agent should be able to pick up work by running a small set of commands, not by grepping an800-line plan and reconstructing conventions. The human explicitly requested GPT-6 consideration of OpenCode’s feedback in this Codex chat. The independent evaluation below approves a narrower staged scope with changes; no pickup commands are implemented yet.

**Pickup feedback (OpenCode/no-vision, 2026-10-25):** recovery was feasible because the artifacts, hashes and live record were strong. The friction was navigation and enforcement, not missing evidence:

- Current state was spread across current status, live work record, evidence ledger, capability routing and artifact READMEs; several greps were needed to identify the active unit and next action.
- The live record’s Qwen prior was stale (`786.45s`); durable stores gave `545.95s`. No command recomputed or rejected the inconsistency.
- `reading_launch.py` defaults and count-wrapper conventions had to be read from code. The first wrapper used the Go counter hash where launch readiness expected the Ollama runtime hash; only code inspection caught it.
- The counter command in the artifact README assumed `/private/tmp` and an external module cache. This harness blocked those paths, so a local adaptation was required.
- There was no one-command build/count/verify/prepare flow. The deterministic transformation itself was easy once found; the new module and tests are complete, but the surrounding workflow is still manual.

**Proposed offline flow (not implemented; for GPT-6 triage):**

- `uv run globe reading expansion build --config configs/reading-expansion/<run>.json` emits the request, reuse, counts, protocol, budget, verification and launch-intent set from one versioned config, avoiding per-run constants in Python.
- `... count` wraps the pinned Go counter with repo-local temp/cache paths and fails on runtime/counter hash mismatch.
- `... verify` recomputes budget arithmetic from durable stores and checks manifest/reuse/control identity, source hashes, context fit and offline launch preparation; it exits nonzero on mismatch.
- `... prepare-launch` calls `reading_launch.prepare` only and makes no provider call.
- `uv run globe reading status [--json]` is read-only: latest run stores, budget, pending reviews, process/port state and artifact hashes.
- `uv run globe doctor` checks Go/Ollama/Tesseract and path/cache availability without downloads or model calls.
- `uv run globe plan current` extracts the authoritative current-status/live-record/next-action blocks from this plan; it must not create a second plan or backlog.
- Thin `make reading-expansion` wrappers default to offline. `run --execute` remains a separate, explicit, gated command requiring fresh process/queue proof and a named vision-capable assessor.

**Independent GPT-6 evaluation, 2026-10-25 — approve with changes:** the feedback is well founded. Root inspected `reading_launch.py`, `reading_run_store.py`, `reading_preflight.py`, dispatch budget enforcement and the frozen expansion instructions. Hash checks, durable journaling and runtime caps already provide important safeguards, but agents must still reconstruct the right inputs and invoke them correctly. The stale budget figure, manual hash-field confusion and dated module defaults demonstrate avoidable reliability risk. This evaluation is separate from OpenCode’s preparation/implementation and was explicitly requested by the human; no automated model review was invoked.

**Approved minimum first cut (not implemented):**

1. A compact read-only `reading status --json` view selected by an explicit run/config identity. Report terminal/pending/in-flight/invalid/timeout counts, known versus unknown usage/time, cumulative prior/current budget arithmetic and provenance, pending human reviews, ownership/checkpoint age and the next action sourced from this plan. Put the highest-value state first and cap ordinary output; reference detailed evidence rather than dumping it. File/store discrepancies must be visible. Process state must be timestamped/unknown unless actually checked; a loaded model does not prove work is active or idle. Do not infer the current run by whichever directory was modified last. Include the compact current plan/action view here initially rather than add a separate Markdown-extraction command.
2. A read-only `reading verify` for that same explicit identity, reusing existing validators/materialization checks. Verify request/reuse/model/source/image/control/count/protocol/review bindings and recompute cross-run budgets from durable evidence, retaining unknown usage and conservative reservations. Exit nonzero on mismatches or unresolved safety evidence; distinguish historical integrity from fresh runtime launch readiness. Check that the runtime binary matches its recorded runtime hash and the Go helper matches its own recorded build/source hash: those are different artifacts and must not be compared to each other for equality. Show expected/actual artifact names in errors. Do not open stores via `ReadingRunStore.__init__` for status/verification: it creates directories/schema, enables WAL and can write identity. Use SQLite read-only connections and existing pure logic instead.

**Later, only when the next experiment needs it:** an explicit versioned run configuration and thin offline build/count/prepare wrappers around existing functions, with repo-local configurable scratch/cache paths, no downloads, immutable outputs and clear runtime/helper identity fields. Keep operator/harness permission failures distinct from missing dependencies. Do not edit historical artifacts or repeat the spent36-call expansion to demonstrate convenience. There is no reason to add a new execute wrapper now: reuse the existing separately opted-in transport and fresh process/queue gates. Read-only pickup must not create outputs, reconcile attempts, mark reviews applied, load models or dispatch requests.

**Defer or cut:** a broad `doctor`, separate `plan current` parser, indexing/dashboard service, scheduler and a large one-command orchestration layer. Provide scoped diagnostics inside status/verify first. Do not turn the plan into another machine-maintained backlog or pretend one successful command proves source fidelity. The log-query tool demonstrates that bounded CLI ergonomics are feasible; its output-cap/pagination corrections also argue for small contracts with adversarial tests.

**Acceptance/risk requirements:** compare a stateless pickup using the two commands with the recorded OpenCode friction; measure commands/output bytes and unresolved decisions without inventing a previous timed baseline. Prove no DB/log/source changes, no network/model calls, no inference through defaults, and no duplicate/retried work. Cover stale narrative versus store evidence, wrong runtime/helper hashes, missing files, unknown elapsed/token usage, prior-run double counting, in-flight attempts and stale runtime observations. The same explicit run identity must select status and verification. Main risks are a polished but stale summary, silent budget undercount, accidental writes through store constructors, excessive output and brittle plan parsing. All remain implementation checks, not claims already demonstrated.

**Priority and next action:** this small pickup/verification layer merits work before another provider experiment, because it protects budgets and handoff correctness. It must not replace the P0 fidelity investigation, source assessment or pending HR-010/004 grades. Next implementation unit: define the explicit read-only run/config input and bounded status/verify outputs, then build only the approved minimum. Broader wrappers remain deferred and require their own bounded justification.

**Adoption rule after evaluation:** the required human-requested independent GPT-6 evaluation is now recorded above. Its approve-with-changes verdict permits only the minimal read-only status/verify scope under the stated acceptance requirements; implementation and full project validation are still outstanding. The original broader proposal is not approved wholesale. No model-workload authorization is added, and the completed36-call expansion must not be relaunched.
