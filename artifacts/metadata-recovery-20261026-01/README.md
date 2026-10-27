# A small speaker/date job can now recover safely

T30, 2026-10-26. This extends the existing runner connected in [T29](../metadata-runner-20261026-01/README.md). It does not create a new agent workflow or make any real AI requests.

## What changed in plain English

Before asking for an answer, the program saves exactly which passage and instructions it is about to use. When an answer returns, it saves that answer before checking it. If the program stops just after the answer is saved, the next process can check that saved answer without asking the same question again.

If the program stops after it might have sent a question but before an answer is saved, it does not guess what happened. It stops further requests. It also stops if it cannot account for the time or reported usage, or if an answer was rejected. Restarting cannot quietly give the job a fresh allowance or skip past the rejection.

We deliberately killed test processes before a question was claimed, just after the claim, after a simulated send with no saved answer, after saving an answer, and after finishing its checks. Separate new processes then tried to continue. Recoverable completed work was reused; uncertain work remained blocked. These were test replies using existing source passages, not new AI answers or human historical judgments.

## What is preserved and checked

- The exact pretransport caller request: selected provider/model/settings, source packet, prompt, output schema and contract. The code that renders the provider-specific request is also included in the frozen code identity. Actual native wire/schema acceptance still requires T31/T32 evidence.
- The complete response envelope, raw provider text, reported usage and measured request time, committed before parsing. The parsed result is separately saved with its own hash.
- Source-linked proposals/unknowns from the existing validators. Recovered invalid answers retain their raw reply and keep later items stopped.
- Per-run cumulative attempts, known request seconds and input/output token counts. Unknown usage/time remains unknown and blocks new dispatch. Paid-capacity checks reserve the next bounded request as well as counting known prior cost. Output-limit violations stop further dispatch. Related earlier experiments still require the explicit cumulative accounting in the real-job manifest; this is not an automatic cross-run budget merger.

Request, response and terminal-result hashes are checked on reopening and reading. This catches accidental or one-field alterations, including lowered usage in the final saved result. It is not tamper-proof storage against someone deliberately replacing both data and matching hashes. Invalid cached-token figures cannot produce a negative cost estimate. Missing/legacy journal tables, an unsupported schema version, incompatible configuration or changed inputs/code are rejected rather than silently migrated.

Existing historical journals are not modified. New runs use role journal schema3. Changes are confined to the existing role runner/journal/input code and tests; the existing shared Ollama transport lock remains intact. No reconciliation or automatic retry command was introduced. A missing answer still requires real terminal-worker evidence and deliberate reconciliation before a different authorized run can be considered.

## Evidence and limits

[Process proof](proof.json) retains observed process exit codes, actual synthetic-send counts, saved-checkpoint hashes and final statuses/accounting copied from the final full test run. Five controlled SIGKILL points are covered. [Review record](review.json) records the bounded Luna review and the concrete integrity fixes it prompted. This is preparation/code review, not human historical grading or a new-workflow adoption verdict.

Fifteen added recovery cases cover fresh-process reuse and blocked ambiguity, preserved unknown usage/time, elapsed budget after restart, request/response/terminal-result alteration, unchanged legacy database bytes, immutable checkpoint APIs, invalid cached usage, and the stop after a recovered invalid answer. The full required project checks pass **535 tests**: [final log](gate-final.log). Original colored logs are retained compressed; readable logs only strip terminal coloring and trailing spaces. [Validation](validation.json) binds the final implementation/tests and proof files.

These checks prove the declared small metadata runner path using injected test callers and the same library in new processes. They do not prove real model accuracy, backend schema support, arbitrary hardware/storage durability, or independent-agent recovery. They do not spend or renew a provider allowance, import human labels, change OCR, or settle whether broad cleanup is worthwhile.

The next ready task is T31: prepare a concrete, finite real-job/compatibility manifest. Actual service/model identity, available allowance and fresh worker checks must be explicit before a real request. Main M1/M2 stages remain PARTIAL until their wider evidence exists.
