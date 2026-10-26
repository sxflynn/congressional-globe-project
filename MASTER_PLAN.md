# Congressional Globe: current work

Updated 2026-10-25. **This is the only current goal, task queue, ownership and progress record.** [AGENTS.md](AGENTS.md) is the short entry point. Detailed policies are split into [task-specific references](#reference-map); they contain no competing task queues. Historical snapshots and experiment notes are evidence, never instructions to restart work. New human instructions take precedence.

## Goal and current result

Build a source-preserving foundation for researching the five parts of the 39th Congress, first session: useful search, trustworthy speaker/date/topic/legislation filters and cited answers. A production research search/enrichment service is not complete. Agents build and prove bounded workflows; the human chooses and launches full workloads.

**P0 remains open:** is further image-grounded OCR cleanup worth its total cost for reading, text-to-speech, retrieval and annotation? Do not infer skip/selective/broad-cleanup policy or full-run approval from a successful diagnostic.

- Canonical snapshot: 5,412 pages / 296,995 paragraphs / 19,803 page-bounded chunks; saved export is older than later SQLite cleanup results.
- Reading comparison is **finished**:36 new calls plus 4 exact reused replies;27 new valid / 3 invalid / 6 timeouts. All 30 returned input counts match. Both models fail frozen pilot criteria: wrong chapter numeral, removed printed repetition, cross-record relocation and residual damage. [Comparison](artifacts/reading-quote-expansion-run-20261025-01/comparison.md).
- **HR-004 human readability feedback received:** both source windows need wording repair despite clear subjects; damaged words interrupt comprehension, specifically `ra}'` in part2/page1857/leaf1009. Sample2 free-text topics: preservation of State Department government documents in a fireproof building, and the Sioux City railroad branch. Sample1 supplies readability feedback, not usable topic labels. No structured-label import or blanket cleanup approval. [Exact answer](docs/archive/human-review/HR-004-v1/7d9635ca-6176-4971-b2e5-dfad247e439c.json).
- Ten exact failure/comparator fixtures are **finished**:7 valid / 3 invalid; full and portable replays match. Valid transport can still carry fidelity/mapping failures. [Fixtures and six guard requirements](artifacts/reading-failure-fixtures-20261025-01/README.md).
- M1 role protocol v2 and saved-output audit are **finished**; scoped-date contract/inference remains unimplemented. [Role evidence](artifacts/role-protocol-v2-20261025-02/README.md), [two frozen date/boundary cases](artifacts/role-date-boundary-preparation-20261025-01/preparation.json).
- Ollama log-query CLI is **finished**, including all three review corrections. [Usage and limits](docs/reference/log-query.md).
- Latest code gate: 397 tests plus Ruff, ty and complexity≤5. [Exact log](artifacts/ollama-log-query-fixes-20261025-01/gate.log.gz). The later fixture unit passed 28 existing guard tests; instruction restructuring changes no code.

## Pick up work in five steps

1. Run `uv run globe review inbox`; inspect `git status --short`, `git log -5 --oneline` and `tail -n 20 CHANGELOG.md`. Read the [review protocol](docs/reference/human-review-protocol.md) only if answers arrived or your task handles reviews. Apply actual answers before dependent work; continue independent work while reviews are pending.
2. Read the active-work table below. Do not depend on another harness's chat/session IDs. For offline/documentation work, inspect its files and ownership; investigate runtime only if the task will touch workers or recovery.
3. State image capability. Choose the first **READY** task below that you can do and that is unowned. Generic “work in this codebase” means make that choice autonomously. If blocked by missing inputs, record the exact blocker and take the next independent READY task; do not invent sources or ask the human to choose among available routine tasks.
4. Change its row to **ACTIVE** and add/update the active-work row: owner, files, bounds and checkpoint. Read only that row's input/reference links, plus [engineering rules](docs/reference/engineering.md) before implementation. Do the listed steps and checks.
5. Update the same task row to **DONE** with commit/evidence, or **BLOCKED** with its precise dependency. Update the compact result/milestone if changed; append one dated changelog entry and commit. Keep a single next action. A task can be done while its research milestone remains open.

Statuses: **READY** = actionable now; **ACTIVE** = claimed; **BLOCKED** = named dependency; **DONE** = evidence exists. A pending human review blocks only its dependent decision, not the whole project.

## Active work

| Task | Owner / paths | Bounds and checkpoint | Next action |
| --- | --- | --- | --- |
| None | Unclaimed | HR-004 revision1 application complete: plan/archive commit `658c238`, separate receipt verified. No worker or image inspection launched. | First unowned READY task is T6; HR-010 remains pending. |

Before launching model work add its actual process start time/full command, run/config hashes, budgets, journal path and checkpoint here. No owned reading worker is carried forward. Prior process observations are historical; recheck reality before any worker action.

## Ordered task queue

The first unowned READY row is the default next task. Do not create a second backlog. Supporting references specify how; only this table specifies what is next.

| ID / status | Concrete unit and steps | Inputs / references | Done when |
| --- | --- | --- | --- |
| T0 DONE | Make stateless pickup easy: shorten entry instructions, split references, expose ordered tasks/ownership, preserve decisions and historical evidence. | Explicit current human request; [exact original snapshot](docs/archive/2026-10-25-instruction-split/manifest.json) | Completed: active links/policies checked; documented entry walkthrough selects T1 from AGENTS/master alone. Original snapshots verified. [Validation receipt](artifacts/instruction-split-20261025-01/validation.json). |
| T1 DONE | Implement minimal read-only `reading status --json`: define explicit run/config input; report journal counts, prior/current budget evidence, unknown usage, review/ownership state and next action with bounded output. No “latest directory” guessing. | [Approved scope and pitfalls](docs/reference/pickup-tooling.md); `reading_run_store.py`, terminal export and [comparison](artifacts/reading-quote-expansion-run-20261025-01/comparison.json) | Done: added `reading` CLI (`status`/`verify`) reading explicit `--run-dir` only via read-only SQLite; bounded JSON with journal/budget/unknown/review/next action; tests pass; no writes/network/inference. Commit `TBD`. |
| T2 DONE | Add read-only `reading verify` for the same explicit run identity; check request/reuse/source/image/count/protocol/review bindings and conservative cross-run budgets. Reuse pure validators. | [Approved scope](docs/reference/pickup-tooling.md); `reading_launch.py`, `reading_dispatch.py`, `reading_requests.py` | Done: enhanced `globe reading verify` checks bindings/reuse/budgets/unknowns, avoids store constructor writes (read-only SQLite), no model calls; tested on expansion run. |
| T3 DONE | Evaluate a minimal **risk-only** contract for G01–G03: identifier edits, repeated-word deletions and cross-record provenance. Use exact failures and legitimate comparators; distinguish flags from source truth. Freeze proposed output/expected cases before any implementation. | [Ten cases and requirements](artifacts/reading-failure-fixtures-20261025-01/README.md); `reading_quotes.py`, `reading_contracts.py`; [research design](docs/reference/research-design.md) | Done: frozen risk-only contract (G01–G03) with flags from source truth, comparator F10 preserved for review (not auto-blocked), unresolved states for cross-record moves, no guards implemented or model runs. [Evidence](artifacts/reading-risk-contract-20261025-01/README.md). |
| T4 DONE | Define scoped-date contract and source mapping from the two frozen cases: explicit date, date-negative verb “may”, and boundary stops. Preserve role-v2 semantics; prove schema/backend compatibility before any inference. | [Frozen cases](artifacts/role-date-boundary-preparation-20261025-01/preparation.json); [role v2](artifacts/role-protocol-v2-20261025-02/README.md); `role_aliases.py`; [metadata semantics](docs/reference/research-design.md#required-metadata-semantics) | Done: frozen scoped-date contract with typed fields (date/date_kind/precision/scope/evidence/unknowns), date-negative "may" handling, boundary stops, source mapping from frozen cases; schema/backend compatibility noted, no inference calls. [Evidence](artifacts/role-date-contract-20261025-01/README.md). |
| T5 BLOCKED on HR-010; HR-004 DONE | Consume HR-010/004 answers if they appear; archive exact latest revisions, apply narrowly, commit, mark applied, export separate receipt and commit again. | [Human decisions](#human-decisions); [review protocol](docs/reference/human-review-protocol.md) | HR-004 revision1 applied in `658c238`; [separate receipt](docs/archive/human-review/HR-004-v1/7d9635ca-6176-4971-b2e5-dfad247e439c-applied.json) preserves exact hashes/answer. HR-010 still needs an actual submission. Do not fabricate answers. |
| T6 READY; reader-impact follow-up | Freeze the human-reported `ra}'` comprehension failure and surrounding important-word context as a reader-impact case. Preserve exact source/hash and original answer; inspect only the matching cached source crop if available, otherwise record the missing-image dependency. A source-supported correction stays a proposal, never a canonical edit. | [HR-004 answer](docs/archive/human-review/HR-004-v1/7d9635ca-6176-4971-b2e5-dfad247e439c.json); source `congressionalglo7392unit:1009:par_001009_000042`, raw SHA-256 `5f649d554b54ff7d78ebe97147cfb869744cf6ab46d65632fbd16d5b98bc0207`; [scan rules](docs/reference/scans.md) | Exact damaged span/context and human impact retained; printed reading either source-verified by a vision-capable agent or explicitly unresolved. No guessed repair, new model call, formal subject-label import or corpus change. |

The startup path is now AGENTS + this workboard; reference/history reading is task-specific. A structured walkthrough was checked locally, not by an independent fresh model.

Completed supporting units: log-query fixes `c1d53f6`; failure fixtures `be04156`; pickup evaluation `96f5079`. Full history is in [CHANGELOG.md](CHANGELOG.md), not more “latest next steps” paragraphs here.

## Milestone progress

| Milestone | State | Evidence needed to advance |
| --- | --- | --- |
| P0 cleanup value | OPEN; primary comparison and failure fixtures complete | Representative fidelity/reading/TTS/retrieval/annotation/cost evidence and actual human policy decision; readiness below. |
| M0 source foundation | Foundation complete; preserve | Portable identities/release packaging; immutable raw sources and provenance. |
| S0/S1 scans/vision | Bounded feasibility complete | Supporting source access only; not a scan-hunting workstream or production correction approval. [Evidence](docs/reference/scans.md). |
| M1 metadata contracts | Partial; role-v2 complete | Scoped dates, boundaries and broader reviewed role/metadata coverage; T4 is next independent unit. |
| M2 durable workflow | Partial; journals/timeout recoveries exist | Arbitrary-crash and second-harness recovery proof, no lost/duplicated compatible results. |
| M3 authorities/subjects | Partial; candidate data and diagnostics | Cited people/place/bill resolution, temporal service links, curated vocabulary and quality labels. |
| M4 retrieval | Pending production implementation | Source-preserving lexical/hybrid search with reliable metadata/boundary filters. |
| M5 benchmark | Pending | Fresh reviewed end-to-end results, negatives/abstentions and declared acceptance standards. |
| M6 portable pilot | Pending | Another client can consume the backend/export and reproduce setup/recovery with realistic cost estimates. |
| M7 full workload/release | Human decision; NOT authorized | Concrete provider/configuration/budget/recovery/release packet after pilot acceptance. |

### P0 decision readiness

**0 of 7 fully ready.** This is evidence readiness, not project percentage. Existing diagnostics remain useful partial evidence. Detailed criteria, matched raw/static/clean arms and stopping rules: [research design](docs/reference/research-design.md#p0-is-a-clean-reading-layer-worth-broad-ocr-cleanup).

| ID | State / remaining evidence |
| --- | --- |
| P0-A criteria/scope | Partial: HR-003 provisional standards/resources and HR-009 reduced review effort applied; broader tradeoffs unresolved. |
| P0-B benchmark/expectations | Partial human evidence: HR-004 supplies two readability judgments and sample2 free-text topics, with explicit damaged-word comprehension cost. Sample1 topic labels absent; no validated subject import. HR-010 grades, broader labels, complete references and fresh confirmation still absent. |
| P0-C retrieval | Small raw/static diagnostics only; fresh relevance labels and reliable combined filters missing. |
| P0-D enrichment/workload | Partial topic/role diagnostics; paired source-backed metadata coverage and safe routing/workload evidence missing. |
| P0-E grounded answers | Prior answers have mixed AI-provisional findings; matched retrieved context, claim/citation/abstention review and human-supported benchmark missing. |
| P0-F total cost | Local request time/tokens recorded; unknown timeout usage and unmeasured human-review/hardware/energy costs retained. |
| P0-G confirmation/decision | Fresh confirmation and final human cleanup-policy packet not ready; no P0 closure. |

Reading/TTS remains part of P0 scope: the primary comparison exposes fidelity/mapping failures, and no complete transcription benchmark, audio assessment or accepted quality result exists.

### Runtime and budget facts

- Primary investigation cumulative 48 attempts / 3693.79 conservative request-seconds against 60 / 7200. New expansion time 2784.91 seconds; 137,216 known input / 25,692 output tokens across 30 returned calls; six new timeout usages unknown, plus three prior unknown usages. Remaining allowance is **not** an instruction to spend it.
- Do not launch the completed 36 expansion requests, abandoned 54 v1 requests or Muse retries. Saved outputs/errors/timeouts are immutable. Exact source/count/run identities and terminal evidence: [comparison](artifacts/reading-quote-expansion-run-20261025-01/comparison.json), [terminal export](artifacts/reading-quote-expansion-run-20261025-01/terminal-export.json).
- Earlier cleanup queue/PID observations are dated evidence, not live status. `make status` reports cleanup only. Before model actions use [recovery checks](docs/reference/engineering.md#runtime-recovery--only-when-the-task-needs-workers). Offline tasks may proceed without proving global runtime idleness.
- Keep Ollama sequential. Full-corpus processing, model downloads and recurring jobs are not authorized. Review desk is intentionally an unauthenticated single-user LAN tool; do not reintroduce auth without a changed human deployment request.

## Human decisions

At startup consume new inbox answers without waiting for chat notification. These are the current decision states; [HUMAN_REVIEW.md](HUMAN_REVIEW.md) gives the human interface and archive links. Full H1–H6 rules and immutable submission/application procedure: [review protocol](docs/reference/human-review-protocol.md).

| ID | State / exact authority and scope |
| --- | --- |
| HR-001 | APPLIED: explicit petition requests count as substantive topics; not endorsement or factual verification. |
| HR-002 | APPLIED: credential access resolved; no secret stored here, no current credential request. |
| HR-003 | APPLIED: first-pilot coverage, provisional criteria and conditional local resources; no full run/P0 closure. [Exact answer](docs/archive/human-review/HR-003-v1/d02da43f-cba3-4654-be1f-b9f3c72de125.json). Proposed 60 minutes was not approved. |
| HR-009 | APPLIED: “Use the 10-minute review plan.” At most 3 fixed anonymized outputs / 10 minutes total, no substitutions or extra review round. [Exact decision](docs/archive/human-review/HR-009-v1/decision.json), [selection](docs/archive/human-review/HR-009-v1/selection.json). |
| HR-004 | APPLIED to plan: Stephen Flynn, revision1, submitted2026-10-26 02:16:06UTC. Both samples: “Some wording needs repair, but the subject is clear”; sample1 damaged words disrupt reading, exact `ra}'` impairs comprehension. Sample2 names document/fireproof preservation and Sioux City railroad branch. Sample1 topic-label question remains unanswered in substance. [Exact packet/answer](docs/archive/human-review/HR-004-v1/7d9635ca-6176-4971-b2e5-dfad247e439c.json), [application receipt](docs/archive/human-review/HR-004-v1/7d9635ca-6176-4971-b2e5-dfad247e439c-applied.json) referencing `658c238`. Preserve free text; no automatic validated labels, canonical edits or P0/full-run approval. |
| HR-010 | WAITING: already-approved HR-009 round; two actual fixed outputs, one rejected; third unavailable, no substitute. Hard 10 minutes, explicit not-reviewed option. [Packet](docs/review-packets/HR-010-v1.json), [bindings](docs/review-packets/HR-010-v1-sources.json). |
| HR-005 | APPLIED: damaged-name case is Mr. Wade; case-specific attribution only. [Exact answer](docs/archive/human-review/HR-005-v1/original.md), [receipt](docs/archive/human-review/HR-005-v1/receipt.json). |
| HR-008 | APPLIED: voting rights acceptable/B+; reject military inference and preserve petition discovery; compensation acceptable; carry supported speaker context across pages. [Exact answer](docs/archive/human-review/HR-008-v1/original.md), [receipt](docs/archive/human-review/HR-008-v1/receipt.json). |
| HR-006 / HR-007 | NOT REQUESTED: final P0 policy and pilot/full-run/release acceptance are not ready. Silence does not approve them. |

## Reference map

Read a reference when its task needs it; do not load all of them at startup. Paths and commands inside references assume repository-root working directory unless stated otherwise.

| Need | Reference |
| --- | --- |
| Implement, test, commit, recover a worker or check authorization | [Engineering](docs/reference/engineering.md) |
| Understand source identity, metadata semantics, architecture, evaluation and P0 stopping rules | [Research design](docs/reference/research-design.md) |
| Author/apply human review packets, inspect H1–H6 or archive revisions | [Human review protocol](docs/reference/human-review-protocol.md) |
| Find an existing command, setup/cache requirements or source-image operation | [Commands](docs/reference/commands.md) |
| Audit a completed experiment or locate source-bound role/reading evidence | [Evidence index](docs/reference/evidence.md) |
| Prepare/inspect scan crops or understand existing vision proof | [Scans](docs/reference/scans.md) |
| Query Ollama logs safely and understand cursor/error behavior | [Log query](docs/reference/log-query.md) |
| Implement the approved minimum status/verify scope; see deferred broader proposal | [Pickup tooling](docs/reference/pickup-tooling.md) |

## Document ownership and history

- **AGENTS:** startup and universal guardrails. **This master:** current goal, task order, ownership, milestones, readiness and human decision states. **References:** detailed policy/design/commands. **Artifacts:** exact evidence. **CHANGELOG:** dated completed history. **HUMAN_REVIEW:** human-facing desk/archive guide. Do not duplicate active status in references or create another backlog.
- Root compatibility pointers (`PROGRESS.md`, `PROJECT_GOAL.md`, `V2_*`, `RUNBOOK.md`, `HAPPY_PATH.md`, `TAG_ARM_PROMPT.md`) lead here; their archived originals are not instructions.
- [2026-10-25 split snapshot and original hashes](docs/archive/2026-10-25-instruction-split/manifest.json) preserve the previous master/entry point exactly. [Earlier consolidation archive](docs/archive/2026-10-22-pre-masterplan/manifest.json) remains unchanged. Historical “next” commands never override the current queue.
