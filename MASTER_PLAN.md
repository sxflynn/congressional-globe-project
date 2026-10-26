# Congressional Globe: plan, progress and next work

Updated 2026-10-26. **This is the only current roadmap, subtask queue, ownership and progress record.** Start at [AGENTS.md](AGENTS.md); read detailed [references](#reference-map) only for the selected task. Historical experiment notes are evidence, not instructions to repeat work. New human instructions take precedence.

## What we are working toward

A trustworthy, portable research foundation for **all five parts of the 39th Congress, first session**. A researcher or future AI tool should find passages by words or meaning, combine supported speaker/date/topic/legislation filters, inspect surrounding context and follow precise primary-source citations. Reading, quotation and text-to-speech access must preserve uncertain/disputed wording and original OCR.

**Next acceptance point: M6, a reviewed portable backend/data pilot with explicit supported scope and measured limits.** A polished website is deferred. A full-corpus production run/release is the separate human decision M7; completing a pilot does not authorize it. [Detailed capabilities and scope](docs/reference/research-design.md#what-the-finished-foundation-must-support).

**Where we are:** source foundation complete; metadata, durable workflow, authorities and benchmark preparation partial; production retrieval, end-to-end proof and portable pilot still ahead. **1 of 7 engineering stages is fully complete.** This counts completed gates, not effort or “14% finished.” Local experiments, tools and documents can be done without completing their parent stage.

**P0 runs alongside these stages:** decide whether raw/search-normalized, targeted or broader source-grounded OCR cleanup earns its total cost for reading/TTS/retrieval/annotation. P0 is OPEN; its human decision is required before M6 acceptance. The finished primary comparison exposed fidelity failures; it did not select a winning workflow or close P0.

## Milestone progress

Read this as the sequence of **acceptance gates**. Independent preparation may overlap; the dependency column says what must be proved before a stage can close. Keep existing IDs stable.

| Stage / state | Deliverable and what closes the stage | Dependencies / human gate |
| --- | --- | --- |
| **M0 DONE — source foundation** | Immutable five-part sources, canonical raw/static baseline, source identities/geometry and verified replay/export. [Foundation proof](artifacts/runs/static-final-20261011/independent_verification.json). Preserve it. | Foundation for every later stage; portability packaging remains M6 work. |
| **M1 PARTIAL — trustworthy metadata** | Typed, source-mapped speaker/role/date/boundary assertions and unknowns; validated contracts plus reviewed real/negative cases establishing supported scope. Current: role-v2 and executable scoped-date host contracts exist; date fixtures pass offline, while live date backend compatibility and role-v2 transport remain blocked/unproved. | M0. H2/H3 for material new labels/policies; one Wade adjudication is not broad attribution accuracy. |
| **M2 PARTIAL — durable repeated workflow** | Bounded stages with exact input/result journals, reuse, failures/budgets and demonstrated interruption/second-harness recovery without lost or duplicated compatible work. Current: journals/timeout recovery and tools exist; T8 found and fixed false-success/output/read-only defects; cross-run/binding acceptance and general recovery proof remain incomplete. | M0 and the M1 contract needed by each stage. Engineering can proceed before all M1 quality questions close. |
| **M3 PARTIAL — authorities and subjects** | Cited people/place/bill/subject links, time-scoped service/affiliations and controlled vocabulary, with evidence/ambiguity preserved. Candidate extraction exists; verified linking does not. | M0 and relevant M1 schemas; M2 required before repeated provider processing. H3 for authority/vocabulary policy. |
| **M4 PLANNED — usable retrieval** | Source-preserving lexical/OCR-tolerant and semantic/hybrid queries; compatible combined metadata filters; matching spans/context/citations and explicit coverage. Existing prototypes are not a production release. | Selected M1/M3 metadata and M2 processing contract. Lexical prototyping can start earlier; trusted-filter acceptance cannot. |
| **M5 PARTIAL — benchmark preparation; end-to-end results ahead** | Frozen representative benchmark and agreed criteria; matched raw/static/clean evidence for retrieval, enrichment, grounded answers, reading/TTS and full costs; negatives/abstentions and disagreements retained. | M4 for end-to-end results; sample/criteria design and human labels can proceed now. H1/H2; no invented quality thresholds. |
| **M6 PLANNED — accepted portable pilot** | Another client can reproduce/use the declared backend/data/query release, with evidence, recovery instructions, measured estimates and all acceptance checks below. | M1–M5 exit evidence plus the P0 cleanup-policy decision. Prepare the concrete pilot before H6 human acceptance. |
| **M7 HUMAN DECISION — full run/release** | Explicitly select provider/configuration/budget and authorize the full workload; afterwards validate coverage/failures/release manifests. | Accepted M6 pilot plus H4/H6 authorization. **Not part of the seven completed-engineering-stage count; not authorized now.** |

Main route: **M0 → M1/M2/M3 → M4 → M5 → M6**. P0 uses evidence gathered through M1–M5 and feeds the M6 decision. S0/S1 scan/vision feasibility and agent ergonomics are supporting work, not extra research acceptance stages.

## What “accepted pilot” means

These are the existing release requirements made explicit, not newly invented numerical quality standards. Detailed rubrics/scope limits still need the applicable human checkpoints. M6 cannot close just because tests pass.

- [ ] **Research use:** the declared scope demonstrates exact names/quotes/numbers, OCR-tolerant and semantic discovery, and supported combined filters; returns matching spans, context and citations to primary sources.
- [ ] **Historical integrity:** raw text stays accessible; derived readings/search views map back to source hashes/spans; people/roles/dates/legislation are not inferred across unsupported boundaries; unknowns and review provenance remain visible.
- [ ] **Quality evidence:** a frozen, appropriately reviewed benchmark covers relevant alternatives, failures and unanswerable cases; source fidelity and metadata/retrieval/answer quality meet explicitly agreed criteria. Existing diagnostics are not held-out gold.
- [ ] **Reading/cleanup decision:** paired reading/TTS and downstream evidence plus total costs support the human-selected raw/targeted/broad policy, including unresolved wording and exception scope. No automatic canonical rewriting.
- [ ] **Durable execution:** interruption and another harness/process recover compatible results without loss/duplicate paid work; ambiguous outcomes and unknown usage are retained; repeated stages respect recorded budgets.
- [ ] **Portable handoff:** schemas, source/data/index manifests, query contract and required artifacts are documented; a separate consumer reproduces the pilot without undisclosed local/ignored dependencies; relevant full code gate passes.
- [ ] **Human acceptance:** H6 records acceptance of the concrete scoped pilot and remaining limits. H4/H6 separately govern M7; neither silence nor diagnostic grades authorize a full run.

## Work-package progress inside the stages

This is the stable parent/subtask map. The [execution queue](#ordered-task-queue) below selects the next bounded unit; it is not a second roadmap. **DONE requires evidence for the stated subtask only.** PLANNED means not yet an executable assignment; promote a bounded unit to READY only when its inputs, scope and completion checks are specified.

| Subtask / state | What is done or still required | Next dependency / evidence |
| --- | --- | --- |
| **M0.1 DONE** sources/baseline | 5,412 pages /296,995paragraphs /19,803page-bounded chunks; verified immutable baseline. Export predates later SQLite results. | [Foundation proof](artifacts/runs/static-final-20261011/independent_verification.json). |
| **M1.1 DONE** role-contract diagnostic | Role-v2 schema/host consistency and exact saved-reply revalidation exist. This is contract engineering, not calibrated all-corpus roles. | [Role evidence](artifacts/role-protocol-v2-20261025-02/README.md). |
| **M1.2 DONE** scoped-date preparation | Two date/boundary inputs and a draft requirements document are frozen. T4 completed this design scope only. | [Frozen cases](artifacts/role-date-boundary-preparation-20261025-01/preparation.json), [design draft](artifacts/role-date-contract-20261025-01/README.md). |
| **M1.3 PARTIAL** executable date contract | T10 implements typed scoped dates, source mappings, schema/host tests and offline adapter construction. Live backend acceptance is explicitly blocked/unproved; existing role-v2 adapter shape is incompatible. | [Contract and blockers](artifacts/scoped-date-contract-20261026-01/README.md). Before inference, establish named backend/version compatibility; fake clients are not backend proof. |
| **M1.4 PLANNED** broader metadata evidence | Review bounded supported/unsupported/unknown roles/dates and propagation/omission cases under the implemented contract. | Offline bounded evidence design can use T10; inference waits for actual backend compatibility, frozen call limits/source expectations and H2/H3 as applicable. |
| **M2.1 DONE** journal/transport slice | Raw-first persistence, exact compatible reuse, budgets and six actual timeout recoveries are recorded. Not an arbitrary-crash guarantee. | [Terminal export](artifacts/reading-quote-expansion-run-20261025-01/terminal-export.json). |
| **M2.2 PARTIAL** trustworthy pickup | Status/verify audit T8 rejects full acceptance; output caps, original-store isolation, journal hashes, time overruns and failure exits are fixed. Cross-run budgets and full evidence bindings remain unresolved. | T11 after T10. [Audit](artifacts/pickup-audit-20261026-01/README.md); [approved contract](docs/reference/pickup-tooling.md). |
| **M2.3 PLANNED** general recovery proof | Controlled interruption plus second-process/harness recovery, failure/migration cases and no silent duplicate work. | M2.1; design a bounded fixture-backed proof before any live workload. |
| **M3.1 DONE** authority candidates | A cited Wikipedia candidate dataset and subject diagnostics exist; candidate is not resolved identity. | [Evidence index](docs/reference/evidence.md); accepted vocabulary/linking remains M3.2. |
| **M3.2 PLANNED** verified links/vocabulary | Resolve bounded people/service/place/bill/topic cases, including ambiguous and missing-authority negatives. | Relevant M1 semantics and cited sources; H3 policy decisions. |
| **M4.1 PLANNED** retrieval release | Implement source-mapped lexical/semantic query contract and correctly scoped metadata filters; preserve turn/date boundaries. | M1/M3 versions and M2 repeated-work proof; prototype evidence alone does not close it. |
| **M5.1 PARTIAL** benchmark/criteria | Provisional HR-003 standards, frozen samples and HR-004 readability feedback exist; HR-010 and representative labels/criteria remain incomplete. | Human register and P0 readiness below. Do not ask answered questions again. |
| **M5.2 PLANNED** matched evaluation | Produce paired retrieval/annotation/answer/reading/TTS results, actual costs and independent confirmation. | M4 output, M5.1 criteria and P0-A–G evidence; obey finite stopping rule. |
| **M6.1 PLANNED** handoff/acceptance | Package the selected pilot, run a separate-consumer proof and prepare H6 acceptance with explicit limits. | M1–M5 + human P0 decision; finish-line checklist above. |

P0-A–G below track the cross-cutting decision evidence. T3 froze risk-only design requirements, T6/T7 resolved one human-reported word, and the primary reading comparison is terminal; none is a complete transcription benchmark or a human-selected cleanup policy.

## Pick up work in five steps

1. Read the destination, stage states and parent/subtask map above. Check `uv run globe review inbox`, `git status --short`, `git log -5 --oneline` and `tail -n 20 CHANGELOG.md`. Apply actual new answers before dependent work, using the [review protocol](docs/reference/human-review-protocol.md); keep independent work moving.
2. Check active ownership below. State image capability. Generic “work in this codebase” means choose the first unowned **READY** execution task you can perform; do not choose a new priority, restart a spent run or ask the human to select an already-actionable task. An explicit new human task takes priority.
3. Claim its task and parent subtask with owner, paths, bounds and checkpoint. Read only the task's inputs/references plus [engineering rules](docs/reference/engineering.md) before implementation. Inspect runtime only if touching workers/recovery.
4. Complete the listed steps/checks. If blocked by a concrete missing input, mark that dependency and take another independent READY row. No vision capability alone does not block offline work.
5. Update **task → parent subtask → stage** in place. A stage becomes DONE only when its exit evidence and prerequisites pass, never because one child finished. Link result/checks/limits, update the next eligible action, append one compact changelog entry and commit. Unmet human criteria stay open.

States: **READY** actionable/unclaimed; **ACTIVE** owned; **BLOCKED** named dependency; **PLANNED** future work not yet bounded; **PARTIAL** evidence exists but exit checks remain; **DONE** stated scope proven. Do not derive a project percentage by counting local task IDs or checked boxes. Unknown/missing evidence never counts as success.

## Active work

| Task / parent | Owner / paths | Bounds and checkpoint | Next action |
| --- | --- | --- | --- |
| None | Unclaimed | T10 offline contract implemented and checked; M1.3/M1 remain PARTIAL with explicit live-backend blockers. No inference or source edits. | Next READY: T11 (M2.2 evidence completion). HR-010 pending. |

Before model work add actual PID/start time/full command, run/config hashes, budgets, journal path and checkpoint here. No owned model worker is carried forward; historical process observations must be rechecked before worker actions.

## Ordered task queue

**Next default: T11.** T10 completed its offline implementation; live date backend acceptance and the existing role-v2 adapter incompatibility remain blocked, not passed. HR-010 gates only its dependent human-review conclusions. Later work packages become executable queue rows when their predecessor evidence is ready; preserve existing IDs and add new IDs rather than renumber history.

| Task / status | Parent and steps | Inputs | Done when / unlocks |
| --- | --- | --- | --- |
| **T9 DONE** explicit human priority | Project-coordination workstream supporting M2/M6: connect destination, ordered acceptance stages, honest child progress, dependencies and stateless pickup. | Current human request; existing research goals/evidence. | Stage/task IDs, dependencies, child completion and human decisions checked;127 active local links pass. Local stateless walkthrough selects T8 then T10; no independent-model trial or code change. [Validation](artifacts/roadmap-coherence-20261026-01/validation.json). |
| **T8 DONE** pickup-tool audit; acceptance rejected | **M2.2:** audit T1/T2 against bounded/read-only contract. Check actual named run and adversarial output/evidence/budget/unknown/no-write/network/next-action cases; fix reproducible defects within approved scope. | `0e745c9`, `cd960ce`; [reading_cli.py](src/congressional_globe/reading_cli.py), [tests](tests/test_reading_cli_status.py), `cli.py`; [approved scope](docs/reference/pickup-tooling.md). | [Findings and reproductions](artifacts/pickup-audit-20261026-01/README.md): hard 8KB output, private WAL snapshot, hash/status/time checks and nonzero failure exits; 19 portable adversarial tests and full gate. Full acceptance rejected: cross-run budget provenance, complete bindings and distinct runtime/helper hashes remain T11. Historical integrity/source fidelity/launch readiness are explicitly unresolved. M2.2 and M2 stay PARTIAL. |
| **T10 DONE** offline scoped-date implementation; live backend proof blocked | **M1.3:** review the frozen date draft against exact cases; implement Pydantic/schema/source-map validation, precision/kind/scope/evidence/unknown behavior and boundary-stop tests; prove schema compatibility for intended transport before calls. | [Cases](artifacts/role-date-boundary-preparation-20261025-01/preparation.json), [draft](artifacts/role-date-contract-20261025-01/README.md), [role v2](artifacts/role-protocol-v2-20261025-02/README.md), `role_aliases.py`; [metadata rules](docs/reference/research-design.md#required-metadata-semantics). | [Implemented contract/evidence](artifacts/scoped-date-contract-20261026-01/README.md): 34 new tests cover exact source-mapped positive/negative/boundary fixtures, partial dates/ranges/alternatives and fake-client serialization. Full gate passes. Live backend/schema acceptance and role-v2 adapter support remain blocked; M1.3/M1 stay PARTIAL. No inference authorized; unlocks offline bounded M1.4 design only. |
| **T11 READY** finish pickup evidence validation | **M2.2:** complete the T8 unresolved evidence checks within the approved minimal scope; retain fail-closed behavior. | [T8 audit and exact gaps](artifacts/pickup-audit-20261026-01/README.md), [approved scope](docs/reference/pickup-tooling.md), named terminal run/config and existing pure validators. | Validate request/reuse/source/image/control/count/protocol/review bindings; recompute prior/current budgets from deduplicated durable stores with conservative unknown reservations; check runtime and helper against their own hashes. Add adversarial missing/stale/mismatch/duplicate cases and full gate; named-run failures stay explicit, never imply launch readiness. No inference. |
| **T5 BLOCKED on HR-010**; HR-004 done | **M5.1 / P0-B:** consume actual HR-010 answer when submitted; archive exact latest revision, apply narrowly, commit, mark applied and export separate receipt. | [Human register](#human-decisions), [review protocol](docs/reference/human-review-protocol.md). HR-004 applied in `658c238`; [receipt](docs/archive/human-review/HR-004-v1/7d9635ca-6176-4971-b2e5-dfad247e439c-applied.json). | Exact original and receipt committed, scope/limits retained. Never fabricate a submission or reopen HR-004. Unblocks only selected-output human findings. |

### Completed execution units — scoped results, not completed stages

| Tasks / parent | Completed scope and evidence | Still not established |
| --- | --- | --- |
| T0 / M2,M6 support | Short startup and reference split `76c633b`; [validation](artifacts/instruction-split-20261025-01/validation.json). | Independent fresh-agent trial and portable M6 acceptance. |
| T1,T2 / M2.2 | Explicit-run read-only status/verify implementations `0e745c9`, `cd960ce`. | T8 rejects full acceptance and fixes safety defects; remaining evidence validation is T11. Implementation alone is not an M2 exit. |
| T3 / P0-B,M2 source integrity | [Risk-only draft](artifacts/reading-risk-contract-20261025-01/README.md) using [ten cases](artifacts/reading-failure-fixtures-20261025-01/README.md). | Automated guards/adoption, calibrated risk policy or source-truth certification. |
| T4 / M1.2 | [Scoped-date requirements draft](artifacts/role-date-contract-20261025-01/README.md), using two frozen source cases. | T10 implements the host/schema/offline adapter portion; live backend acceptance remains blocked. The frozen T4 draft stays unchanged. |
| T6,T7 / P0-B,M5.1 | [Reader-impact case](artifacts/reader-impact-20261025-01/README.md) `7cbe8a9`: `ra}'` is printed **my**; exact crop/proposal replay,40existing tests and browser proof. | Accepted corpus correction, whole-paragraph transcription, general reading/TTS improvement or P0 policy. |

Supporting completed log-query corrections: `c1d53f6`, [usage/limits](docs/reference/log-query.md). Dates, detailed results and previous task definitions remain in [CHANGELOG.md](CHANGELOG.md), evidence and Git history; do not grow another parallel backlog.

### P0 decision readiness

**0 of 7 fully ready.** These A–G requirements concern the cleanup-policy decision, not the M0–M6 engineering-stage count or a project percentage. Existing diagnostics remain useful partial evidence. Detailed criteria, matched raw/static/clean arms and stopping rules: [research design](docs/reference/research-design.md#p0-is-a-clean-reading-layer-worth-broad-ocr-cleanup).

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
