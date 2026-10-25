The first working clean-reading results

The revised response format produced source-backed edits on both selected passages for Qwen and Gemma. Each model corrected all seven pre-recorded OCR checks, which the existing static text still contained. All four completed outputs passed the exact source, quote, image and replay checks. Root AI review found no unsupported substantive changes in these outputs; no human has graded them.

| Model | Valid outputs | Timeouts | Time for the two attempts |
| --- | ---: | ---: | ---: |
| Qwen | 2/2 | 0 | 119.5 seconds |
| Gemma | 2/2 | 0 | 122.9 seconds |
| Muse | 0/2 | 2 | 240.0 seconds |

The earlier format asked the model for character positions and yielded five rejected replies. The new format requires an exact, unique quote from the source; the host derives its position. Earlier failures remain unchanged. One interrupted earlier request and both Muse timeouts have unknown provider usage. Their worker exits and server cancellations were observed and reconciled; none was retried.

The ordinary passage now reads “and,” “Resolved,” “of” and “sufficient” where the OCR was damaged. The quoted legislation now reads “further,” “slavery,” “committed” and “cases,” while preserving the distinct jurisdiction provisions. Qwen joined more line wraps in these two examples, while static cleanup was most consistent: ten raw line-wrap patterns became zero in static text, three in Qwen text, and nine in Gemma text. These counts describe a formatting pattern, not whole-text accuracy.

This is a diagnostic on two previously exposed passages from part 1. It does not establish a general model winner, satisfy the larger 18-passage acceptance criteria, or authorize automatic corpus changes. The revised format still needs other parts, long passages and missing/wrong-image controls. Human review remains capped at three fixed examples and ten minutes; that selection is unchanged.

All 347 software tests passed. Twelve model requests were attempted across both versions, below the approved 60-call cap. Every returned response matched its offline input count; Muse returned no counts before timeout. The corpus is unchanged.
