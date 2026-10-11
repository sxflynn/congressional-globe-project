# V2 embedding model shortlist

Research checked 2026-10-11 against Ollama's model library and the model owners' documentation. This is a shortlist for the raw-OCR V2 retrieval experiment; it is not evidence of OCR-specific retrieval quality or Mac throughput. Do not download or run a model as part of this note.

## Recommendation

For the first comparison, use `qwen3-embedding:0.6b` as the efficient baseline and add `qwen3-embedding:4b` as a quality candidate, alongside `bge-m3` as a different model family. Qwen3 0.6B is a practical baseline: Ollama lists a 639 MB download and 32K context, while Qwen documents a 1024-dimensional vector and query-side task instructions. Qwen's reported multilingual MTEB results show 4B ahead of 0.6B on mean task score (69.45 vs 64.33) and retrieval (69.60 vs 64.64); these are general benchmark results, not evidence for this historical OCR corpus. With 64 GB, model-file size alone is not a reason to exclude 4B. Whether the larger model's quality advantage transfers, and whether its indexing/query time suits the workflow, must be measured on the fixed sample and actual Mac/backend. BGE-M3 is a useful contrast: 1.2 GB, 8K context, 1024 dimensions, and no required query instruction. Its multilingual and multi-granularity features are less important for this English corpus, but it offers a different retrieval model and context profile. [Ollama Qwen3 library](https://ollama.com/library/qwen3-embedding), [Qwen3 model card and MTEB table](https://github.com/QwenLM/Qwen3-Embedding), [Ollama BGE-M3 library](https://ollama.com/library/bge-m3), [BAAI BGE-M3 model card](https://huggingface.co/BAAI/bge-m3)

If installing only one model after the backend is confirmed, choose Qwen3 0.6B for an inexpensive starting point, or Qwen3 4B if the priority is testing the stronger general benchmark candidate and the user accepts additional indexing cost/time. The most informative first comparison is both Qwen sizes under the same protocol; add BGE-M3 as the cross-family comparator if capacity and time permit. The machine's 64 GB makes memory capacity less of a screening constraint, but does not prove that 4B will improve retrieval on this corpus or establish M4 throughput. Do not promote either size as the winner before the labeled sample.

## Ollama catalog options

Download sizes and context windows below are Ollama catalog values; dimensions and prompt guidance are from model-owner documentation where available. Ollama download size is not runtime memory use. Vector dimensions are part of the retrieval index identity: changing model or dimension requires re-embedding and a separate index.

| Model / pull command | Ollama download; context | Published vector dimension | Query/document convention and notes |
| --- | --: | --: | --- |
| `qwen3-embedding:0.6b` | 639 MB; 32K | 1024; custom dimensions supported | Add a task instruction to the query; leave documents unprefixed. Qwen's example: `Instruct: Given a web search query, retrieve relevant passages that answer the query\nQuery: {query}`. The task instruction can later be tailored to historical-research queries, but freeze it during model comparison. [Library](https://ollama.com/library/qwen3-embedding), [model card](https://github.com/QwenLM/Qwen3-Embedding) |
| `qwen3-embedding:4b` | 2.5 GB; 40K | 2560; custom dimensions supported | Same instruction convention. Stronger general-benchmark candidate for the paired comparison. [Library](https://ollama.com/library/qwen3-embedding), [model card](https://github.com/QwenLM/Qwen3-Embedding) |
| `qwen3-embedding:8b` | 4.7 GB; 40K | 4096; custom dimensions supported | Same instruction convention. Qwen reports strong general multilingual benchmark results, but this does not establish a benefit on this small OCR sample. [Library](https://ollama.com/library/qwen3-embedding), [model card](https://github.com/QwenLM/Qwen3-Embedding) |
| `mxbai-embed-large` (335m) | 670 MB; 512 | 1024 (model card) | Model owner recommends prefixing queries only: `Represent this sentence for searching relevant passages: {query}`. English-focused and short context make it a useful familiar retrieval baseline, though less convenient for longer windows. [Ollama library](https://ollama.com/library/mxbai-embed-large), [Mixedbread model card](https://huggingface.co/mixedbread-ai/mxbai-embed-large-v1) |
| `bge-m3` (567m) | 1.2 GB; 8K | 1024 | No query instruction required per BAAI. Supports dense, sparse, and multi-vector retrieval in its source implementation; Ollama's embedding endpoint exposes the dense embedding path. [Ollama library](https://ollama.com/library/bge-m3), [BAAI model card](https://huggingface.co/BAAI/bge-m3) |
| `embeddinggemma` (300m) | 622 MB; 2K | 768, with 512/256/128 options in Google's model card | On-device oriented, multilingual. Google's documentation defines task prefixes (such as `task: search_query` and `task: search_document`); confirm the Ollama template/API path preserves these before relying on them. [Ollama library](https://ollama.com/library/embeddinggemma), [Google model card](https://ai.google.dev/gemma/docs/embeddinggemma/model_card) |
| `all-minilm:22m` / `all-minilm:33m` | 46 MB / 67 MB; both 512 | 384 (L6) / 384 (L12) | Simple unprompted text-in/text-out embeddings. Very small and useful as a speed/quality floor, not the primary model for historical retrieval. [Ollama library](https://ollama.com/library/all-minilm) |
| `snowflake-arctic-embed:22m`, `:33m`, `:110m`, `:137m`, `:335m` | 46 / 67 / 219 / 274 / 669 MB; 512 / 512 / 512 / 2K / 512 | 384 / 384 / 768 / 768 / 1024 | Snowflake's retrieval examples prefix queries with `Represent this sentence for searching relevant passages: `, leaving documents unprefixed. If adding another baseline later, `:335m` is more informative than the tiny variants; do not add all sizes to the initial comparison. [Ollama library](https://ollama.com/library/snowflake-arctic-embed), [Snowflake model card](https://huggingface.co/Snowflake/snowflake-arctic-embed-l-v1.5) |

The query prefixes above come from each owner’s reference workflow. Ollama's library examples generally show raw `input`; do not assume that a UI or API wrapper automatically adds model-specific prefixes. Explicitly inspect and record the actual text sent for query and document embedding. Before freezing a benchmark, confirm dimensions returned by the selected Ollama-compatible backend; wrappers can change defaults or strip unsupported options.

## Download and backend check

Native Ollama commands for the Qwen size comparison and cross-family comparator, if/when the user elects to download them:

```bash
ollama pull qwen3-embedding:0.6b
ollama pull qwen3-embedding:4b
ollama pull bge-m3
```

Root subsequently inspected this machine: `/usr/local/bin/ollama` links into `/Applications/Ollama.app`, reports version **0.40.2**, and an `ollama` process listens on port 11434. Its model inventory includes `qwen3.8:27b-mlx`, with `runner: mlx`. Thus a separate MLX service should not be assumed merely from model names; the native Ollama commands above target the observed local daemon. No embedding-capable model is currently listed. After a download, verify `/api/embed`, returned dimensions and query-template behavior with a tiny request before indexing. No model pull or embedding inference was performed for this research.

## Bounded comparison plan

Use the already planned fixed V2 sample: 50 source windows, stratified at 10 per part across all five parts, with 10 frozen queries and relevance labels established before looking at ranks. Keep the same windows, query text, retrieval cutoffs, filtering, and raw/static text variants across models. Embed the same windows separately for raw OCR and the existing static-normalized text; do not normalize, repair, or rewrite text for an embedding model. Keep page/source anchors and canonical paragraph links intact.

1. First benchmark Qwen3 0.6B and 4B on the same 50 windows × 10 queries, separately for raw and static text. Add BGE-M3 as a cross-family comparator if feasible; `all-minilm:22m` is an optional compact baseline, not a substitute for the Qwen size comparison.
2. Follow each model's query-side prompt convention exactly and leave document input unprefixed unless its model card specifies otherwise. Freeze the instruction, dimensions, endpoint, runtime/model revision, text hashes, and normalization/cosine policy in the run manifest.
3. Measure retrieval separately from controlled-tag correctness and grounded-answer support. Until the full pool has relevance labels, report intended-target hit/rank rather than precision/recall. With complete labels, report per-query relevance metrics at predeclared cutoffs, failures by part/document type, and exact source-citation validity. Small-sample differences are directional only.
4. Time cold start, warm query embedding, and batch indexing on the actual Mac mini/backend with the existing Qwen 27B completion model resident in the intended workflow. The catalog and model cards do not provide a reliable throughput estimate for this hardware/backend combination; there is no measured M4 speed claim here.

Embedding outputs are disposable derived artifacts, not canonical corpus changes. Save model ID, backend/runtime, dimensions, instruction template, input layer/hash, and run version beside each vector release, and rebuild vectors when any of those change.
