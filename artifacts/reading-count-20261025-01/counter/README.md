# Offline Ollama input counter

This helper counts the exact fixed-shape request prompts in the final launch manifest using Ollama tokenizer code and source-derived renderer/media-expansion behavior pinned to commit `f580b5484a58c8370c35d669555bf887783a3f68`. It does not load MLX model weights, invoke Ollama/API endpoints, or use the GPU. The per-model media preparation code decodes/resizes/patchifies on CPU, but the token count depends only on the model's image geometry; no model weights or MLX encoder are needed.

The copied Ollama source and retrieval manifests are under `../upstream/`; license texts and source/dependency digests are in `../provenance.json`. The helper reads the existing repository request manifest, model tokenizer/config blobs, and image paths. It does not copy large model assets into this artifact.

Rebuild and run from this directory (Go 1.23+ and the already-cached `golang.org/x/text v0.27.0` module required):

```sh
GOCACHE=/private/tmp/go-build-fit-cache GOTOOLCHAIN=local GOPROXY=off GOSUMDB=off GOMODCACHE=/Users/sflynn/go/pkg/mod /usr/local/go/bin/go build -o /private/tmp/globe-reading-fit-counter/count .
/private/tmp/globe-reading-fit-counter/count "/Users/sflynn/Downloads/congressional globe project/artifacts/reading-launch-20261025-01/requests.json" > /private/tmp/globe-reading-fit-counter/reproduced-counts.json
```

The stable report is `../counts.json`; it records manifest, request, renderer-prompt, and image SHA-256 references plus text/image/total input counts and requested-envelope checks. A count is source-derived, not binary-validated: the installed Ollama binary reports `vcs.modified=true`.
