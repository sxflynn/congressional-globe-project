# Ollama log-query correction closeout

The human requested finishing all three findings from the independent retrospective review of `ac4a671`. The original review and reproductions are unchanged in `../ollama-log-query-review-20261025-01/`.

## Delivered behavior

- The complete serialized JSON response, including metadata, cursor, newline and optional indentation, must fit `max_output_bytes`. Normal pages shed trailing events into a correctly positioned cursor. If even one event or the metadata cannot fit, a small JSON error is returned on stderr with exit2 and no stdout. Raw suppression cannot leak large parsed messages/fields past the cap. Pretty-printing is rechecked before printing; CLI indentation is limited to0–8 and error messages to128characters.
- Lines above the fixed1MiB record cap return terminal `record_too_large` instead of the same cursor indefinitely. A scan budget too small for any progress returns `scan_budget_too_small`; increase that budget deliberately. There is no silent skip of oversized evidence.
- Scan reads, context and cursor hashing use one open descriptor. The scan/context stop at the opening size. File identity/size/mtime are checked before returning; detected append/rewrite/rotation/removal during the query returns `source_changed`. Growth between queries remains supported and reported. No automatic retry loop. This is an optimistic read consistency policy, not an atomic filesystem snapshot or defense against deliberate same-metadata tampering.
- Parser version is `ollama-log-query-v2`; old cursors are rejected and require a fresh query. No model calls, uploads, server restart or source-log writes.
- The long malformed-line regression exposed an unanchored regex search with quadratic cost. Parsing now matches pairs only at the current offset, retaining the intended stop-at-first-invalid-token behavior.

## Validation

`make gate` passed397tests in2.38seconds plus Ruff formatting/lint, ty and complexity≤5. Exact full gate output is saved as `gate.log.gz`. All41focused log-query cases passed. Regression cases cover giant parsed messages/fields/malformed lines with raw disabled, whole-report metadata limits, output-cap pagination without dropped/duplicated events, oversized/no-progress records, append/rotation/rewrite/removal during scanning, rotation before context extraction, and final CLI/indented-output bounds.

A bounded real-log proof used the actual CLI twice, never a whole-log dump:

```bash
uv run globe ollama logs query --include "context canceled" --limit 3 --raw-bytes 160 --max-output-bytes 8192
```

The second call supplied the first call's cursor. Saved JSON pages are3,710/3,713bytes, both below8,192. Page1: lines38/464/558; page2:571/620/675; disjoint offsets and10matches in the initial scan. See `live-proof-summary.json` and the exact two reports. The source log was read-only throughout. Original OpenCode evidence stays unchanged.

## Scope and remaining optional refinements

All three required review corrections are complete. Compact field projection or count-only output may reduce ordinary report verbosity further; neither is needed for the corrected hard-cap contract. A busy log may cause an explicit `source_changed` error; narrow the query or retry deliberately when stable. An oversized event produces an explicit error instead of returning misleading partial evidence. Routine agents should use this CLI first, with a narrowly bounded fallback only for unsupported cases.
