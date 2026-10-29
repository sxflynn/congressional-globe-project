# T76: native-fit v2 trace contract and export boundary

T70's fit gate assumed the backend would export decodable JPEG tiles and a text-only token trace. T71 found the installed backend instead prepares normalized float32 patch rows, a grid shape and positional layout, and expands image boundary/pad tokens into the request stream. A contract built on the old assumption could accept a structure that no real preprocessing step produces. This unit replaces that assumption with a separately versioned offline contract. It does not add any evidence about the installed backend.

## What the new library does

`src/congressional_globe/productive_ocr_native_trace.py` defines a strict v2 trace that is re-checked against exact request and resource bytes:

- **Request binding.** The trace must match the frozen request projection (body, host packet, image, image bindings, diagnostics, saved proposal, model, output ceiling). A changed body or projection is rejected.
- **Rendered text.** Exact UTF-8 bytes are hash-registered, and the text token segments must tile those bytes exactly and split only on character boundaries.
- **Expanded token stream.** Segment indices must be contiguous; together the segments must equal the declared input, text and image token counts; exactly one media segment is allowed, and the media block must cover its whole segment.
- **Patch tensor.** One `float32` tensor per requested image: declared shape must agree with channels, patch size, temporal grid and merge size, element/byte counts must agree with the shape, the data bytes must be registered, every value must be finite, and the declared minimum/maximum must equal the values actually decoded from the bytes.
- **Grid and positions.** The patch grid cells times temporal must equal the media patch-token count, and the positional layout must cover the expanded stream. The layout is bound by exact byte length, entry count and width; its int32 values are not semantically interpreted, so a wrong-but-well-sized layout would not be detected yet.
- **Debug requests.** A debug request is separate bytes. It must bind a registered deterministic transform whose source is the intended study body, and it must differ from the study request.
- **Producer boundary.** A `NativeTraceProducer` protocol defines what a future exporter must supply. The export adapter accepts only the exact registered canonical bytes, re-validates them and rejects a producer whose declared identity differs from the trace's. `require_authentic_producer` always refuses: an authored fixture is not native truth, and an owned-capture claim is self-asserted rather than independently attested. `authentic_capture` is a constant false in this offline contract.

The original v1 module, T70 evidence and T71 study are untouched. The frozen 6000-input / 1500-output token ceilings and the seven-request scope are reused, not changed.

## Checks

- 43 new tests in `tests/test_productive_ocr_native_trace.py`, including authored float negatives (NaN, infinity, wrong declared range, swapped byte order, short bytes), segment/stream negatives (tiling, token totals, media span and mandatory boundary tokens, aliases, duplicate media, order, grid and shape arithmetic, positions), overflow (6000+ tokens, oversized patch tensor, 1501 output tokens), binding negatives (projection consistency, body, resources, unregistered or non-canonical trace bytes, receipt identity/registration, debug transform), gate cross-field consistency and adapter identity mismatch.
- Full `make gate` passes with 922 tests; the retained log is `gate.log.gz` (879 tests before this unit).
- `evidence-driver.py` rebuilds the tiny fixture independently and runs seven scenarios. All pass in `validation.json`; the fixture is explicitly labelled `offline_authored_fixture_only`.

## What this does not prove

No authentic native preprocessing producer or export exists. The installed build is still `0.40.8+dirty` with unproved source parity, real backend compatibility and stopping are unproved, and no trusted T55 clearance exists. Every gate therefore reports `launch_ready: false` and `exact_build_parity: false`; an owned-capture identity with a registered receipt is recorded as a declared claim (`declared_owned_capture: true`) but `authentic_capture` stays false and it is still not launch clearance. The fixtures are invented software evidence: they prove the validator rejects malformed traces, not that the real backend emits a matching one. No server, model, API, image fetch, download or new dependency was used, and no historical reading or quality claim follows.

Two primary scans remain missing (T55/R1). The next readiness step still needs a separately named bounded unit that captures real preprocessing with fresh runtime evidence, plus T55 binding of the T75 feedback helpers into the exact S1/S2 requests.

## Bounded review

An independent bounded review by an OpenCode general-purpose subagent (no Luna model available in this harness) found one material issue and eight minor ones. The material issue was that a self-authored local receipt could make `authentic_capture` true. That is fixed: `authentic_capture` is now a constant false, `declared_owned_capture` records the claim, and the refusal path always refuses. The minor issues (positions semantics, zero boundary tokens, non-canonical export bytes, projection hash drift, gate consistency, unreachable return type, imprecise media index, coverage gaps) are fixed or explicitly documented. [Dispositions](review.json).

## Files

- `fixture-trace.json`, `fixture-projection.json` — canonical authored fixture and its exact request binding.
- `patch-tensor.bin`, `positions.bin` — the 192-byte float32 tensor and 24-byte positional layout behind the fixture.
- `evidence-driver.py` — standalone regeneration script.
- `validation.json` — baseline gate, adapter result, refusal text and per-scenario outcomes.
- `gate.log.gz` — full gate log for this unit.
