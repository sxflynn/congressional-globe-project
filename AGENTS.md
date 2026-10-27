# Start here

Shared entry point for Codex, Claude, OpenCode and other agents. New human instructions take precedence.

## Pick up work

1. Read [MASTER_PLAN.md](MASTER_PLAN.md): destination/acceptance, stage progress, then the execution queue. It is the **only current roadmap, subtasks, progress and ownership record**.
2. Run `uv run globe review inbox` (for cache permission errors, see [setup](docs/reference/commands.md#8-operator-commands-and-current-limitations)). If answers arrived, follow the [review protocol](docs/reference/human-review-protocol.md) before dependent work.
3. Check `git status --short`, `git log -5 --oneline` and the last20lines of [CHANGELOG.md](CHANGELOG.md) (`tail -n 20 CHANGELOG.md`). Read older entries only when needed. Preserve other work.
4. State whether you can inspect images. Choose the first READY execution task whose dependencies and capability requirements you meet; identify its parent subtask/stage and claim it in the master's active-work table before edits. If it is owned, choose another READY task. Do not invent a new priority or rerun a completed experiment.
5. Read **only that task's linked references**. Complete its steps/checks, update task → parent subtask → stage in the master, append one compact changelog entry and commit. A finished draft/diagnostic does not complete implementation or the parent stage.

“Work in this codebase” means follow this sequence; no task selection question is needed when a READY task is available. If inputs are missing, record the precise blocker and take another READY task; do not fabricate evidence.

## Always preserve

- Human-facing review text must use plain English and generous dotted-underlined glossary help. Define unfamiliar technical/research terms, abbreviations, historical vocabulary and phrases in titles, instructions, questions, choices and evidence labels; include variants actually displayed. Explain with a concrete example when useful. Definitions must be neutral and must never hint at a grade, identify a hidden model or rewrite source text. Expand the shared glossary for existing packets; preserve immutable packet/answer bytes. Follow the [mandatory glossary authoring checks](docs/reference/human-review-protocol.md#mandatory-plain-language-and-glossary-rule).
- Raw sources, accepted ledgers, historical experiments and human answers are immutable. Model proposals are not historical truth or human approval. Keep P0—the value of further OCR cleanup—open until its human decision.
- No new model/provider call without a named bounded task and fresh process/queue checks. Keep Ollama sequential. Do not repeat spent pilots, download models or start corpus-wide/recurring work from generic instructions.
- Use `uv run globe ollama logs query` first for Ollama logs; use bounded filters/cursors, never a whole-log dump. Never expose secrets.
- Do not touch `tmp/performance/`. Do not reset another agent's changes.
- Read [engineering rules](docs/reference/engineering.md) before implementation. Use uv/Pydantic v2, complexity≤5 and `make gate` for code. Markdown edits in Codex require elevated `npx prettier@3.9.10 --prose-wrap never --write "**/*.md"`; check `git diff --check`.
- Commit completed units with `[model: ACTUAL KNOWN MODEL]` at the end of a single-line message; use `unknown` if unavailable.

Detailed rules and commands are linked by task in the master. Do not read the archive or every reference file at startup. Compatibility pointers (`PROGRESS.md`, `V2_*`, etc.) are not instructions or separate backlogs.
