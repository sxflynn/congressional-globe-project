# T70 refused concurrent fake-evidence checkpoint

The synthetic success example completed, but the first crash/resume case refused with `BlockingIOError: Resource temporarily unavailable` because a full gate was concurrently using the shared request lock. This was an operator sequencing mistake; the matching gate had two lock-refusal failures and844passing tests. Its log is retained in the final evidence. The evidence driver was then run sequentially, followed by the full gate. No actual model inference occurred. See [final proof](../owned-ocr-transport-20261028-03/README.md).
