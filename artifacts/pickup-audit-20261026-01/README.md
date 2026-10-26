# T8 pickup-tool acceptance audit

2026-10-26, Codex GPT-6. Parent M2.2; M2 remains PARTIAL. **Verdict: reject full acceptance; safety fixes implemented.** No inference, image fetch, provider request, corpus change or human grade.

## Reproduction and fixes

The original T1/T2 implementation emitted every attempt/detail/stop report and merely asserted `bounded_output`. A synthetic timeout produced 41,165 bytes. It accepted 12 recorded seconds against a 1-second total budget, returned CLI exit 0, and omitted unknown token usage. [Exact original reproduction](before.json) records those observations. The named historical run originally returned verification success with a 12,564-byte status representation. No previous timed pickup baseline exists.

The commands now emit complete JSON with an 8,192-byte UTF-8 cap including newline; oversized reports return a compact failure and nonzero exit. Status aggregates attempts and stop reports without raw content, reports unknown token/time usage, labels prior budgets unverified and remaining allowance unknown, and points to the current master action with its SHA-256. It never recommends dispatch. Process, human-review and ownership facts are explicitly unobserved or referred to the master.

Inspection copies the database and optional WAL to private temporary scratch, checks source size/mtime stability, and opens only that copy. This includes committed WAL data while avoiding SQLite writes to original SHM/WAL sidecars. This is an offline snapshot, not a general arbitrary-crash or hostile-concurrent-writer guarantee. Temporary scratch writes are expected; original run files remain unchanged. The code never initializes `ReadingRunStore`, fetches data or calls a model.

Verification checks canonical config/task/manifest/request hashes, task-attempt status consistency, missing claimed attempts and saved terminal replies. It rejects observed call/total/per-model/per-call overruns, invalid elapsed values and unresolved in-flight/unknown-time evidence, and exits nonzero on errors or unresolved checks. Request hashes establish consistency with journal declarations, not independent model/source correctness. Existing pure request materialization and source validators are not yet integrated. The full gate also exposed an existing missing `load_draft_vocabulary` import in `cli.py`; restored that import.

## Remaining acceptance work (T11)

- Bind exact request/reuse/model/source/image/control/count/protocol/review artifacts through existing pure validators; detect missing files and stale narrative versus evidence.
- Recompute cumulative prior/current budgets from declared durable stores, deduplicate prior runs and retain conservative unknown usage reservations. Current timing is only this journal's observed lower bound, with unknowns shown separately.
- Compare the runtime binary and counter helper to their own separately recorded hashes, including missing and wrong hash cases. Do not equate their hashes or report fresh launch readiness from historical evidence.
- Read current review/ownership/checkpoint provenance with explicit availability and age, then repeat named-run acceptance and stateless pickup comparison. Current master action is hash-bound; human reviews/processes are not queried.

These gaps always appear as unresolved and prevent `ok: true`; they have not been tested as implemented capabilities. No broad wrapper, new run configuration or automation is adopted. Full historical integrity, source fidelity and fresh launch readiness remain distinct and unproved. T8 completes the audit and regression fixes, not M2.2 acceptance; the master schedules T10 then the bounded T11 follow-up.

## Validation

Nineteen portable synthetic tests cover oversized Unicode output, time overruns, config/task/request tampering, missing attempts/files, unknown token/time usage, in-flight work, negative/nonfinite timing, master action provenance, WAL-visible commits, concurrent-copy detection and unchanged original file hashes. Network and store constructors are blocked during read-only checks. Tests do not depend on ignored historical run files. [Named-run inspection](named-run.json) measures two CLI commands, output bytes, unresolved decisions and source-file hashes; no prior timed baseline is invented. Full `make gate` results are recorded in [gate log](gate.log).

Full gate passed: Ruff formatting/lint, ty, complexity≤5 and **416 tests**. Named-run status emitted1,815bytes (exit0), verification787bytes (exit1), with every original run-file hash unchanged. Its journal hash/status checks passed; observed per-call elapsed time exceeds the recorded120-second limit, and three evidence categories remain unresolved. This records historical measured time rather than changing the immutable run or declaring it launch-ready.
