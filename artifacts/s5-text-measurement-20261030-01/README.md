# T90: one actual S5 response with the simpler format

The human explicitly approved one additional S5 test after the recommendation of a120-second execution limit and no retry. One real request was sent to the existing installed Qwen model. The new fixed slot is spent; the old failed attempt and its slot remain unchanged.

## Inputs → expected → actual

Original OCR:

> The Committee on- Appropriations recom- mended non-concurrence.

Actual software proposal supplied alongside the same registered scan:

> The Committee on- Appropriations recommended non-concurrence.

Expected reading, recorded before dispatch:

> The Committee on Appropriations recommended non-concurrence.

Actual model text:

> The Committee on Appropriations recommended non-concurrence.

The expected and actual text match exactly. The parent image-capable agent inspected the same hash-bound cached crop: the target sentence matches, the genuine non-concurrence hyphen remains and adjacent context is not added. This is one previously exposed development example, not a blind human reference or general accuracy measure. Original historical text and accepted ledgers are unchanged.

## Actual format mismatch

The actual reply declared complete coverage and supplied `reason: "No further action required."`. The host validator requires `reason: null` for complete readings. However, the exact provider schema permits a string or null without that joint condition, and the prompt does not forbid a completion comment. The actual reply passes its advertised JSON schema and fails the additional host rule. This is an inconsistent software request/validation requirement, not evidence of a wrong transcription.

The original `run/result.json` remains **invalid**, with no accepted clean export. A separately labelled offline diagnostic changes only reason to null and passes the remaining host checks. It does not replace, re-export or accept the actual result. The next named task T99 aligns the existing prompt/schema/validator rules offline; it authorizes no further call.

## Actual measurements and stopping

- Start-through-response/normal owned-stop elapsed: **28.0343918749seconds**.
- Backend-reported usage: **1,322input /59output tokens**; authentic native fit remains unknown.
- Exactly **1new physical call**, **0retries**, **0fetches/downloads**. Cumulative S5 development calls:2.
- Earlier call:53.3356seconds,1,391reported input/762output tokens. Prompt/schema/output workload differ; this is no controlled speedup or corpus forecast.
- Actual CLI26578 (uv26576), server/PGID26638 and child26658 exited. Durable receipt says stopped and a fresh exact-PID process check finds none. Shared Ollama service untouched.
- Fixed scope: same original S5 image/raw/sample and installed executable/model;1,500output,120s shared startup/resource/load/request/normal-stop budget,600s whole session. Timeout cleanup retains its separate stopping reserve. Native-fit exception is restricted to this approved diagnostic.

## Implementation and validation

The existing measurement runner now has an explicit additional text-format profile with fixed approval/body identities, a separate package/spent slot and the same source/hash/raw-first journal/recovery/owned-stop mechanisms. V1 inputs/approval/body/slot behavior remain intact. The current-code host rebind does not alter the approved provider body. Caller-selected recovery specifications must match the frozen attempt. Recovery for this profile requires `--recover --spec artifacts/s5-text-measurement-20261030-01/run/spec.json`; omitting the spec intentionally selects historical v1 recovery. Recovery cannot dispatch.

`make gate` passes all formatters, Ruff, ty, complexity≤5 and **1,079tests**, including8new bounded authorization/source/deadline/slot/recovery/outcome controls. Bounded Luna review covers lifecycle/authority/source/recovery and the terminal diagnosis; no model calls or source-quality labels were delegated. Operator process/queue/bounded Ollama-log/nonloading model-state/shared-lock checks preceded dispatch. Exact runtime and source evidence, raw HTTP/request/response, journal and stop receipt are retained. Private server HOME keys/cache are deliberately excluded from the portable evidence.

HR-013v7 presents actual inputs, expected reading, actual model text, format difference and measurements with five evidence comment boxes plus an overall comment. Original/model passages remain plain; surrounding explanations have glossary help. An isolated AppTest/render check has no exceptions and verifies six comment boxes/source protection. No Computer Use or browser/device interaction was performed. V6 is preserved but superseded to correct a review-page crop URL; the actual request and inspected image were always the verified original S5 image.

This run establishes an actual expected-text observation and a specific request/validator mismatch. It does not establish host-valid clean output, general efficacy, full native readiness, a quality policy or corpus-run authority.
