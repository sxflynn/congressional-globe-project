# Bounded real-log Ollama query demonstration

Source: `/Users/sflynn/.ollama/logs/server.log`
Source SHA-256: `62d75b1f1f23712267917e56792452205df7abe1a9a0f26a83f2d501eb6e85ac`
Source size: 143,061 bytes / 986 lines
Time zone: `local` resolved to `America/New_York` (Gin timestamps are naive)
Parser: `ollama-log-query-v1`
Gate: `gate.log` (384 tests, Ruff, ty, complexity≤5; all passed)

## Cancellation events

Command:

```bash
uv run globe ollama logs query --path ~/.ollama/logs/server.log \
  --include "context canceled" --limit 3 --raw-bytes 160
```

Result: 10 matches, 3 returned, complete scan, output cap reached.
Returned lines: 38, 464, 558. All 10 matched lines are `runner.go` info events.
Report: `context-canceled.json` (3,712 bytes).

Raw comparison:

- The 3 returned source lines are 284 bytes.
- All 10 raw matching grep lines are 1,170 bytes.
- The bounded JSON report is 3,712 bytes because it adds query metadata, counts,
  source identity, hashes, field data, and a continuation cursor. The tool is an
  evidence interface, not a log compressor.

## HTTP 500 events

Command:

```bash
uv run globe ollama logs query --path ~/.ollama/logs/server.log \
  --status 500 --limit 3 --raw-bytes 160
```

Result: 10 matches, 3 returned, complete scan, output cap reached.
Returned lines: 34, 460, 554. All 10 matched Gin events are `POST` 500 responses.
Report: `status-500.json` (3,899 bytes).

Raw comparison:

- The 3 returned source lines are 353 bytes.
- All 10 raw matching Gin 500 lines are 921 bytes.

## Cursor continuation

`context-canceled-page-1.json` repeats the first cancellation query.
`context-canceled-page-2.json` uses its `next_cursor`.

Result: page 1 returned lines 38, 464, 558; page 2 returned lines 571, 620, 675.
No event was duplicated or skipped, and the second page scanned from byte 60,131
to EOF.

## Limits

This is a read-only demonstration against the current local log snapshot. It does
not inspect rotated siblings, correlate requests, infer token usage, modify the
log, call a model, or certify any external system state. The 38 malformed lines
in each report are counted rather than silently discarded.
