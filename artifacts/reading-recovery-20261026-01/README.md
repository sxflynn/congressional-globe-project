# T12: interruption and independent-process recovery

2026-10-26, Codex GPT-6. Parent M2.3. This is a bounded engineering proof of the existing reading journal/dispatcher, using synthetic inputs and fake local transports only. No model/API/network/image request, historical run mutation, corpus edit or human grade. It does not authorize processing.

## Findings and fixes

[Before-fix reproduction](before.json), against the preceding implementation, demonstrated three defects with synthetic data:

- A direct claim accepted a request body that differed from the task's frozen request hash.
- Reconciliation filled unknown request time from wall-clock time since the original claim, including potential downtime. This was an estimate rather than measured request time.
- Opening an incompatible legacy run added its missing elapsed-time column before rejecting the configuration.

[An additional working-version reproduction](missing-table-before.json) showed that a missing task table was silently recreated empty, despite the retained one-task identity manifest. Existing journals now require all known journal tables; missing task/attempt tables are rejected byte-for-byte unchanged instead of recreated.

The journal now checks an optional frozen request hash inside the atomic claim transaction, before changing task state. Existing tasks lacking request hashes remain legacy-compatible; dispatcher manifest checks still apply independently. Initialization checks supported schema version and existing run identity before WAL setup or migration, rejects incomplete/unrecognized identity schemas, and closes its connection on initialization failure. The current unversioned layout (`user_version=0`) and its known missing-elapsed-column migration are supported; unknown version markers are rejected without guessing.

Terminal status changes preserve elapsed time exactly as recorded. A missing elapsed value remains null during completion/reconciliation. The invalid-reply path now explicitly persists its actually measured duration before becoming terminal. No historical elapsed values are rewritten. Unknown time blocks new dispatch unless a separate supported budget-reconciliation path establishes safety; this unit does not silently spend an inspection report's conservative allowance.

One T8 assertion previously prohibited the word “dispatch” anywhere in plan provenance. It falsely failed when an ownership description mentioned journal/dispatch code. The test now rejects the original unsafe `dispatch_next_pending` recommendation specifically; the safety behavior remains covered.

## Frozen inputs and process proof

[Fixture JSON](fixture/fixture.json) freezes two exact requests, synthetic source/image hashes, tasks/config, mock readiness/runtime evidence and exact fake replies. Its two tiny image payloads are deliberately synthetic byte fixtures, not scanned-page images. Model tag/digest fields are only host-contract test identities; no model is loaded. Worker runtime timestamps are synthetic gate inputs refreshed in each child, never observations of a real runtime.

[Final implementation proof trace](final-proof.json) records six first-process SIGKILL checkpoints and separate-process pickup, plus two explicit recovery/reconciliation scenarios:

| Forced stop after committed operation | What a fresh process proves |
| --- | --- |
| Claim | Exact request and in-flight row survive; no fake transport was reached; automatic resume blocks. |
| Raw reply/usage persistence | Exact bytes and usage survive; automatic resume blocks; offline validation can finish the saved reply without resending. |
| Completion | Completed result is reused; only the second pending task reaches fake transport; another pickup sends nothing. |
| Transport error | Exact error and ambiguous in-flight outcome survive; automatic resume blocks without a second send. |
| Invalid reply completion | Rejected bytes, unknown usage and measured time survive; the rejected task is never rerun; only pending work proceeds. |
| HTTP failure completion | Failure bytes, unknown usage and measured time survive; the failed task is never rerun; only pending work proceeds. |

Every killed process is owned by the test, acknowledged its committed checkpoint/PID, and is killed through its own subprocess handle. All children have hard checkpoint, observation and completion timeouts and cleanup in a `finally` block. Optional targeted OS start-time/command inspection is recorded as unknown when the harness denies it; this does not masquerade as a live worker observation. No unrelated process is inspected or interrupted. The fixture SHA-256 stays unchanged across pickup; completed attempt rows stay identical, while only the genuinely pending task may add a new row. Fake transport log identities prove no duplicate mock sends.

After a crash following raw-reply persistence, another process runs the existing host validators and completes the saved result offline. Missing elapsed time stays unknown and blocks further dispatch; after a claim-only crash, explicit synthetic reconciliation preserves both unknown time and usage. These are deliberate safety holds, not evidence that an unknown request failed or never reached a provider.

## Compatibility checks and limits

Seventeen new cases cover the six kill points, saved-reply recovery, unknown-preserving reconciliation, incompatible config/task/request rejection, direct claim hash enforcement, compatible legacy migration, incompatible migration refusal and future-version refusal and missing-table refusal. Compatible migration preserves every preexisting row field and unknown usage; unsupported/incompatible opens preserve the original database bytes. Existing store/dispatcher/pickup tests also pass.

The proof is a fresh Python-process pickup using the same tested library, not an independent agent/harness implementation. It covers the named committed points, not arbitrary instruction boundaries, filesystem corruption, power loss, host restart, provider billing guarantees or all future metadata processing stages. `SIGKILL` tests exercise committed SQLite WAL recovery; they are not a hardware durability certification. Test-only peer/helpers are not adopted as a new operator command or launch workflow.

M2.3's bounded reading recovery proof is complete. M2 remains PARTIAL: conservative unknown-budget reconciliation and journal adoption by the intended metadata stages are not integrated end to end. M1's known role-v2 adapter incompatibility is the next bounded offline task (T13); live backend acceptance and P0/H6 decisions remain open. Full project gate: [gate.log](gate.log); code/fixture identities and check results: [validation.json](validation.json).

Full gate passed: **497 tests**, Ruff formatting/lint, ty, complexity≤5 and required elevated Markdown formatting. The [initial proof](proof.json) is retained unchanged; the final proof additionally binds the exact final implementation hashes and includes the same eight successful scenarios after the missing-table guard.
