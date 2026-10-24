# Holistic cleanup investigation scorecard

This is a bounded P0 design artifact, not a second roadmap. [MASTER_PLAN.md](../MASTER_PLAN.md) remains the authority for project scope, status, human checkpoints and next action.

## Decision to inform

Determine whether the five-part 39th Congress corpus should receive a broadly cleaned, separately versioned reading transcription in addition to its immutable raw OCR. The decision considers human reading, copy/quotation, text-to-speech, RAG/retrieval and historically grounded annotation together. It does not decide whether raw OCR/scans remain authoritative: they do.

The investigation can recommend one of three scoped paths:

1. Keep raw OCR plus search normalization for a stated use case.
2. Use deterministic or selective image-grounded repair for defined failure classes.
3. Produce a broad clean reading layer through a measured repeated-LLM workflow.

No outcome authorizes a corpus-wide job until the human reviews a concrete provider/configuration, cost/time estimate, recovery plan and quality evidence.

## Non-negotiable text layers

| Layer | Purpose | May it overwrite another layer? |
| --- | --- | --- |
| Scan + immutable raw OCR | Primary-source evidence, audit and re-evaluation | No |
| Clean reading transcription | Reading, copy/quotation, text-to-speech, RAG context and model input | No; it is a separately versioned derived layer |
| Annotation/enrichment | Speakers, dates, topics, legislation, boundaries and other evidence-backed assertions | No; it cites the text layer and primary-source anchors used |

Any uncertain or disputed clean reading remains explicitly uncertain/reviewable and links back to raw text and the source page/crop. A fluent model output is not evidence by itself.

## Repeated-workflow contract

The repeated work is performed by a selected LLM provider, not by an interactive Codex conversation. It may compare an installed local vision-capable model with an OpenAI API model if a later bounded run explicitly authorizes both.

For each item, persist:

- composite source identity, raw-text hash, whole-enough source context and exact scan/geometry reference when an image is used;
- prompt, schema, model/provider/runtime digest, decoding parameters and policy version;
- launch intent, raw request/reply, usage, elapsed time, cost or local-runtime measurement, validation and review result;
- proposed clean text, no-change, unknown/review or failure state; and
- compatible-resume/cache identity and any ambiguous/interrupted attempt state.

Process local requests sequentially under the shared lock. Do not silently retry, overwrite prior outputs or collapse unknown into success. Image retrieval is selective and source-anchored; it is not a bulk image archive.

## Representative POC design

Freeze a source-hashed packet before calls. It should include all five parts and deliberately cover:

- clean controls and ordinary OCR damage;
- names, numbers, dates, bill identifiers, punctuation and line-wrap cases;
- proceedings, index-like entries and longer connected passages;
- text relevant to speaker/date/topic/bill annotation and retrieval; and
- missing, irrelevant or insufficient source-evidence controls that must remain unknown/review.

Use identical packets, output limits and evaluation rules for every provider/workflow comparison. Keep any tuning set separate from a fresh confirmation packet. Earlier diagnostic cases may establish feasibility but are not held-out evidence.

## Quality scorecard

The human must approve concrete thresholds before seeing fresh results. The scorecard reports counts and examples, not a single synthetic “accuracy” number.

| Dimension | Measure | Failure examples |
| --- | --- | --- |
| Source fidelity | Correct words, names, numbers, punctuation and historical wording against scan evidence | Invented word; changed person or bill number; omitted sentence |
| Uncertainty discipline | Unsupported readings remain unknown/review with evidence reference | Model guesses from context where image/text does not support it |
| Reading and TTS | Sentence flow, audible names/numbers, punctuation and harmful spoken artifacts | Garbled OCR sent to speech; incorrect spoken name/number; broken sentence |
| Research utility | Effect on exact/lexical/vector retrieval, RAG context and structured tags | Cleanup harms recall, makes a false attribution look supported or obscures evidence |
| Workflow reliability | Validation, cache/reuse, interruption recovery and auditability | Lost attempt, hidden retry, incompatible resume or missing provenance |
| Cost and scale | Per-item throughput, local memory/runtime, API/image/review cost and cautious full-run projection | Extrapolation from easy cases only; unknown usage reported as zero |

## Required comparison report

The bounded POC report must state the exact inputs/configuration, provider/runtime identity, per-stratum results, raw outputs and failures, measured time/cost, human/independent review method, limitations and the plausible decision changed by the result. It must separately compare raw OCR, existing static cleanup and the candidate clean reading layer where applicable.

The next step after a representative primary comparison is one fresh confirmation batch. Only then prepare a human decision packet choosing raw-first, selective repair or broad cleanup with stated exceptions and reopening conditions.
