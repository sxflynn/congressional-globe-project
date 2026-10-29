# T71: native preprocessing path, without running the model

The investigation is complete; live readiness is still blocked. No server was launched and no model API was called. No producer is implemented: the installed app offers only part of the needed evidence, and its exact source parity is unknown. The existing run approval and all caps remain unchanged.

## What the installed files establish

The actual model manifest hash matches the saved selected model. Its metadata selects a Qwen3.8 Go renderer and Qwen3.5 parser over a Qwen3_5 vision model. The app binary and extracted arm64 build metadata identify0.40.8+dirty at revisionf580b5484a58c8370c35d669555bf887783a3f68, with modified source. The official revision below is a candidate base, not proof of exact installed behavior.

## Source findings

The [public chat handler](https://github.com/ollama/ollama/blob/f580b5484a58c8370c35d669555bf887783a3f68/server/routes.go) has a debug-render-only branch returning rendered text and image count, after scheduling/loading the runner. It does not export the full image preprocessing. The [internal tokenizer route](https://github.com/ollama/ollama/blob/f580b5484a58c8370c35d669555bf887783a3f68/mlxrunner/server.go) receives plain text and is registered after model loading. Neither was called.

The [Qwen renderer](https://github.com/ollama/ollama/blob/f580b5484a58c8370c35d669555bf887783a3f68/model/renderers/qwen35.go) has a distinct3.8 variant, thinking-block behavior and image-tag handling. A generic tokenizer chat template is insufficient evidence of that exact rendering.

The [media interface](https://github.com/ollama/ollama/blob/f580b5484a58c8370c35d669555bf887783a3f68/mlxrunner/model/media.go) separates CPU preparation from media encoding. The [image processor](https://github.com/ollama/ollama/blob/f580b5484a58c8370c35d669555bf887783a3f68/mlxrunner/model/qwen3_5/process_image.go) aligns resizing to patch/merge dimensions, scales pixels, and produces normalized float32 patch rows. The [vision preparation](https://github.com/ollama/ollama/blob/f580b5484a58c8370c35d669555bf887783a3f68/mlxrunner/model/qwen3_5/vision.go) expands image boundary/pad tokens and positional layout into the request stream. It does not naturally emit JPEG tile crops. This makes zero-response-generation capture plausible, but no authentic captured trace exists.

The [pipeline](https://github.com/ollama/ollama/blob/f580b5484a58c8370c35d669555bf887783a3f68/mlxrunner/pipeline.go) treats nonpositive num_predict as remaining-context generation capacity. Setting it to zero is not a safe dry-run method.

## Concrete next proposal

[producer-proposal-v2.json](producer-proposal-v2.json) identifies the missing exporter and a versioned native-fit representation: exact rendered text, per-segment and expanded token streams, media spans, float32 patch bytes/shapes and positional-layout data. It binds intended request bytes separately from any debug request. A JSON response schema may configure the grammar without appearing in rendered prompt text; record actual handling rather than counting invented prompt content.

T70v1's fake-server proof remains valid for its stated scope. Its decodable-image-tile contract must not be presented as an authentic native float32 trace. No v1 artifact was rewritten and no T55 clearance was supplied. T76 bounds the offline contract/exporter design; actual capture, model loading and stopping require a later explicit bounded readiness unit with fresh runtime evidence. T75 missed-error coverage is first READY.

Both HR-012 missed-error concerns remain mandatory inputs/checks for the future S1/S2 requests. Two missing images and actual backend compatibility/stopping remain unresolved. No historical accuracy, human grade, model result, full thirty-minute readiness or stage completion follows from these source observations.

## Evidence and checks

Twelve source files, four directory listings and the MIT license are pinned to the embedded revision, saved with exact HTTP receipts/hashes. Selected local config/preprocessor/tokenizer metadata are hash-checked without reading weight blobs. findings.json separates observations from inferences; validation.json records source-branch/hash/config checks and zero runtime calls. A bounded Luna source review found no material unsupported claim; its native-state/export wording clarification was applied. This is evidence/documentation work only; no repository implementation changed, so the last full code gate846 is retained.
