# Quote-v2 expansion preparation (2026-10-25-01)

Status: **offline preparation only**. This directory freezes 36 new quote-v2 requests, the exact four reusable completed requests, the source assessment and the aggregate budget. No model/provider inference call was made while preparing it. Nothing here authorizes a launch; a fresh process/queue/runtime check is still required immediately before any dispatch.

## What is frozen

- `requests.json`: the 36 new calls. Per Qwen/Gemma model: 16 remaining primary passages plus one missing-image and one unrelated-image control. The top-level `reused_requests` list is exact provenance only and is not counted in `request_count`.
- `reused-requests.json`: the four completed quote-v2 requests reused by exact request/source/image/model identity, with prior attempt IDs and timing. They are not rerun and do not consume new calls.
- `counts.json` and `counts-raw.json`: source-derived token counts from the pinned offline Go counter. All 36 requests fit `16384` context plus `4096` output. Maximum total input is 10014 tokens; minimum headroom is 2274 tokens.
- `assessment-protocol.json`: assessment frozen before any new expansion output. It preserves the 70 raw-span anchors, control rules, HR-003/HR-009 policy and the no-substitution limit.
- `budget.json`: 12 prior attempts, 36 new calls, 48 cumulative of 60. Conservative prior time is 908.88 seconds. The run caps are 120 seconds/call, 6291 seconds total and 1854 seconds/model; the single per-model cap uses Qwen's smaller remaining allowance.
- `launch-intent.json`: offline `reading_launch.prepare`/`launch(execute=False)` proof for the same 36 requests and reduced caps. It does not authorize execution; a fresh process/queue/runtime observation and a vision-capable assessment owner are still required.
- `verification.json`: local checks for request count, model exclusion, reuse identity, control behaviour, materialization, count/manifest hashes and launch preparation.

## Identity

- New request manifest SHA-256: `f5b7a8e325c91ded2a61290324b8b2ed1124b4b66c02384840866169b72fcf61`
- Counts wrapper SHA-256: `72676f2108b697ab87f7066b92cb548e20d43164eaf0072503c9524e819ce073`
- Offline launch intent SHA-256: `de9a6a4d7848a7ef6d4ee258d64c22abeeb5d763058e478f1a729734fde4cd73`
- Counter binary SHA-256: `ff49c60184318cff8f52b2c7014803f412f3b6a36e9fab925f11cc6796c08f41`
- `counts.json.runtime_binary_sha256` is the installed Ollama binary (`e5c7c0ffa50d23d0f0e59cbf325f689b0010ee5563be89b73b05f08844e19e6b`) for launch-guard parity; `counter_binary_sha256` records the offline Go counter. Neither source parity is proven; the installed binary reports `vcs.modified=true`.
- Reused requests are the two already completed passages per model (`reading-d1964b2fd88da0df3db2`, `reading-3077c2e0a49061bbcf29`) from `artifacts/reading-quote-run-20261025-01`.

## Rebuild and recount

```sh
uv run python -m congressional_globe.reading_quote_expansion \
  --launch artifacts/reading-launch-20261025-01/requests.json \
  --completed artifacts/reading-quote-20261025-01/requests.json \
  --prompt artifacts/reading-quote-20261025-01/prompt.txt \
  --schema artifacts/reading-quote-20261025-01/reply.schema.json \
  --output artifacts/reading-quote-expansion-20261025-01/requests.json

GOCACHE="${TMPDIR:-/tmp}/go-build-reading-cache" GOTOOLCHAIN=local GOPROXY=off GOSUMDB=off \
  go build -o /tmp/globe-reading-fit-counter/count artifacts/reading-count-20261025-01/counter
/tmp/globe-reading-fit-counter/count artifacts/reading-quote-expansion-20261025-01/requests.json > /tmp/quote-expansion-counts.json
```

`requests.json` is written only if absent or byte-identical; it refuses a different replacement.

Offline launch preparation (no provider call):

```sh
uv run python -m congressional_globe.reading_launch \
  --output artifacts/reading-quote-expansion-20261025-01/run \
  --manifest artifacts/reading-quote-expansion-20261025-01/requests.json \
  --counts artifacts/reading-quote-expansion-20261025-01/counts.json \
  --protocol artifacts/reading-quote-expansion-20261025-01/assessment-protocol.json \
  --max-calls 36 --total-seconds 6291 --per-model-seconds 1854
```

Adding `--execute --process-proof PATH` is reserved for a fresh, independently verified process/queue observation and a bounded provider launch; do not use it merely to test the path.

## Limits

- Muse remains excluded after two observed 120-second quote-v2 timeouts. This is resource-failure evidence, not a general quality conclusion. No retry or substitute case was created.
- HR-009 selection is unchanged. This expansion can make the Gemma `reading-e05d33cb21bb773191dc` and Qwen `reading-50a8872c9b2dda1a90bf` cases available; the Muse `reading-637a8b4b8fe245aa6d6b` case remains unavailable and must not be replaced.
- At 120 seconds/call, Qwen's 18 new calls alone exceed its remaining 1854.05-second allowance. The dispatch cap must stop the run; all 18 calls are not guaranteed under worst-case duration. Observed quote-v2 durations are about 60 seconds/call.
- This remains a bounded pilot, not P0 closure, full-corpus adoption or full-run authorization. The open value of further OCR cleanup (P0) is unchanged.
