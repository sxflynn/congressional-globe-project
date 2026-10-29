# Start here

Shared entry point for Codex, Claude, OpenCode and other agents. New human instructions take precedence.

## Pick up work

1. Read [MASTER_PLAN.md](MASTER_PLAN.md): destination/acceptance, stage progress, then the execution queue. It is the **only current roadmap, subtasks, progress and ownership record**.
2. Run `uv run globe review inbox` (for cache permission errors, see [setup](docs/reference/commands.md#8-operator-commands-and-current-limitations)). If answers arrived, follow the [review protocol](docs/reference/human-review-protocol.md) before dependent work. Read every submitted evidence-local note; record its action/check or precise unresolved disposition before marking the submission applied. Carry relevant unresolved feedback into dependent model instructions/checks.
3. Check `git status --short`, `git log -5 --oneline` and the last20lines of [CHANGELOG.md](CHANGELOG.md) (`tail -n 20 CHANGELOG.md`). Read older entries only when needed. Preserve other work.
4. State whether you can inspect images. Use the current immediate checkpoint and ordered blocker-closure queue in the master. Choose its first READY execution task whose dependencies and capability requirements you meet; identify its parent subtask/stage and claim it in the master's active-work table before edits. If it is owned, choose another READY task. Do not invent a new priority or rerun a completed experiment.
5. Read **only that task's linked references**. Complete its steps/checks, update task → parent subtask → stage in the master, append one compact changelog entry and commit. A finished draft/diagnostic does not complete implementation or the parent stage.

“Work in this codebase” means follow this sequence; no task selection question is needed when a READY task is available. If inputs are missing, record the precise blocker and take another eligible blocker-closure task. If progress requires a resource, scope or policy decision, complete a concrete, reviewable proposal and ask only that unresolved question. Do not replace unresolved blockers with an indefinite sequence of helper modules, contracts or repeated inventories; do not fabricate evidence.

## Always preserve

- Put requests for human decisions and recent-work walkthroughs in the human review desk, with concrete evidence and comment boxes; notify the human in chat with the desk link instead of asking a standalone approval question. Direct human preference, 2026-10-29. Use the review protocol; do not infer a decision from this delivery preference.

- Human-facing review-desk/server links must always use the current verified `10.x.x.x` LAN IP address, with the port (for example, `http://10.0.0.56:8501`). Do not give localhost or127.0.0.1 as the user-facing address. Recheck the LAN address after network changes; never invent an address. Direct human rule,2026-10-28.

- AI-written review-desk prose must use plain English and generous dotted-underlined glossary help. Define unfamiliar terms and phrases in the agent’s titles, instructions, questions, choices, labels and explanations; include variants actually displayed. Do not add glossary underlining to original historical writing, OCR excerpts or proposed transcriptions. Keep quoted passages plain even inside mixed evidence cards; annotate the surrounding AI explanation only. Explain with a concrete example when useful. Definitions must be neutral and must never hint at a grade, identify a hidden model or rewrite source text. Expand the shared glossary for existing packets; preserve immutable packet/answer bytes. Follow the [mandatory glossary authoring checks](docs/reference/human-review-protocol.md#mandatory-plain-language-and-glossary-rule).
- Raw sources, accepted ledgers, historical experiments and human answers are immutable. Model proposals are not historical truth or human approval. Keep P0—the safe repair method, routing, costs and exceptions for the intended clean layer—open until its human decision.
- The current efficacy-first OCR-repair priority and tasks live only in the master. A support task must identify the named run blocker it closes and the next executable step. Software checks, prepared inputs and fake-server results are distinct from completed Qwen samples, measured quality and runtime forecasts. Historical DONE rows and artifact “next” pointers do not override the current queue. Use the [evaluation contract](docs/reference/ocr-repair-evaluation.md) when its task links require it: audit apparent deterministic successes and unflagged text, distinguish source evidence from model feedback, and keep optional prediction scoring off the cleanup critical path.
- No new model/provider call without a named bounded task and fresh process/queue checks. Keep Ollama sequential. Do not repeat spent pilots, download models or start corpus-wide/recurring work from generic instructions.
- Use `uv run globe ollama logs query` first for Ollama logs; use bounded filters/cursors, never a whole-log dump. Never expose secrets.
- Do not touch `tmp/performance/`. Do not reset another agent's changes.
- Read [engineering rules](docs/reference/engineering.md) before implementation. Use uv/Pydantic v2, complexity≤5 and `make gate` for code. Markdown edits in Codex require elevated `npx prettier@3.9.10 --prose-wrap never --write "**/*.md"`; check `git diff --check`.
- Commit completed units with `[model: ACTUAL KNOWN MODEL]` at the end of a single-line message; use `unknown` if unavailable.

Detailed rules and commands are linked by task in the master. Do not read the archive or every reference file at startup. Superseded planning files were removed after consolidation. Historical copies under `docs/archive/` are evidence, not current instructions or separate backlogs.
