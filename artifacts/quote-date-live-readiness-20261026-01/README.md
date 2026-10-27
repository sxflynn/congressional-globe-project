# A frozen next AI check, not yet run

T36, 2026-10-26. This freezes one exact small request so a later, separately authorized run cannot quietly change the passage, instructions, model or limits. **No AI request was sent.** The request journal does not exist because nothing ran.

## The research question and the mistake being prevented

A researcher wants a passage's date to be supported by the words actually printed on the page. In the previous real check ([T32](../metadata-live-20261026-01/README.md)), the AI answered **January 2, 1900** and quoted those words correctly, but it also claimed they sat at character positions 30–55. Those positions contain “. The meeting was held Ja”. The software rejected the answer because its reference did not point at its own quoted words.

The follow-up design ([T35](../quote-date-binding-20261026-01/README.md)) stops asking the AI to count characters. The AI now supplies only the paragraph, that paragraph's exact fingerprint (hash) and the exact quoted words. Ordinary software finds the quoted words and computes their positions itself. If the words are missing, appear twice, or come from a different paragraph, the answer is refused rather than guessed or tidied.

This task freezes the first real request in that new format. It uses the **real House-opening passage already prepared for the stopped T31/T32 run**, which was never sent. It deliberately does not repeat the short made-up compatibility sentence for its own sake.

## What exactly is frozen

- **Passage:** six paragraphs from the 39th Congress opening, `house-opening-december-4-1865-v1`. The Senate adjournment lines (P1–P2) sit before the House heading and opening (P3–P6). The source fixture and its hash are the ones used by T10/T31.
- **Expected proposal, as a comparison point only:** P3's printed “Monday, December 4, 1865” supports P3–P6; P1–P2 have no supported date; nothing travels backward from the House heading into the Senate lines. This remains an AI-provisional preparation expectation, not human gold and not certified against the page image.
- **Instructions (`prepared/prompt.txt`):** the old date rules, with the character-counting step removed. It asks for `paragraph_id`, the copied `raw_sha256` and an exact quote, and explicitly says not to supply character positions. The quote must occur exactly once in the declared paragraph and must contain the date words; it may not join words from different paragraphs.
- **Output schema (`prepared/output.schema.json`):** `scoped-date-quotes-v1`. Its evidence object has exactly three required fields — `paragraph_id`, `raw_sha256`, `quote`. There are no evidence `start`/`end` fields. Date values still carry ISO `start`/`end`, which are dates, not character positions.
- **Exact wire request (`intended-api-request.json`):** model `qwen3.8:27b-mlx`, temperature 0, reasoning off, JSON-object mode, 2,000 maximum output tokens, the six paragraph aliases P1–P6, and the same prompt plus the host's quote-specific instruction and specialized schema that the runner would send.
- **Code and input identities:** every prepared file, the request digest and all nine code-file hashes are recorded in `readiness.json` and `offline-plan.json`. The offline plan re-verified the prepared manifest, the source-review hash, each packet against its frozen source, and schema equality with the selected contract before reporting success.

## Limits on this run

| Limit                    | Value                               |
| ------------------------ | ----------------------------------- |
| AI requests              | 1                                   |
| Timeout per request      | 120 seconds                         |
| Total provider time      | 120 seconds                         |
| Total dispatch wall time | 150 seconds                         |
| Output tokens            | 2,000                               |
| Logical request size     | under 16,000 bytes (measured 8,644) |
| Retries                  | 0                                   |
| Concurrency              | 1                                   |
| Local API charge         | $0                                  |

Prior usage is not mixed into this budget. T32 spent one call, 24.436 seconds, 1,283 input and 296 output tokens, and stopped. The older reading investigation's 48 attempts and 3,693.79 conservative seconds remain a separate, immutable record. None of those allowances becomes permission for this request.

## Authorization is still missing

The current chat instruction was the generic “perform work”, which per the project's startup rules selects the next ready task but does **not** authorize a model call. The earlier “Do it” authority belonged to the T31/T32 check; T32 spent it and stopped. **A new, explicit human authorization for this exact frozen request is required before dispatch.** This task also does not reuse the stopped run's journal or its unused slot.

Read-only backend facts were rechecked while freezing: Ollama 0.40.8, the same model digest `5642e974…2cf7e`, no model loaded, the shared request lock free, zero cleanup claims, and no inference POST after the T32 call at 01:09 UTC. Those facts are in `preflight.json`; a future dispatch must check them again.

## What a passing result would and would not prove

If this request were authorized and run, a host-valid result would prove only that the selected model supplied an exact, uniquely matchable quote in the declared paragraph, and that the existing date, coverage, boundary and unknown rules accepted the proposal. It would also show that this installed endpoint returns a complete JSON object on this path.

It would **not** prove native schema enforcement, general date accuracy, speaker or role extraction, Senate/House behavior on other passages, or human agreement. It would not repair or reclassify the rejected T32 reply, which stays invalid and unchanged. Every output remains a proposal inside the still-open M1/M2/P0 work.

## Files and checks

- [Frozen readiness, bounds, prior usage and stop rules](readiness.json)
- [Exact prepared inputs](prepared/manifest.json), [quote-only prompt](prepared/prompt.txt), [schema](prepared/output.schema.json), [source expectations](prepared/source-review.json)
- [Offline plan produced by the existing runner](offline-plan.json), [exact intended request](intended-api-request.json), [backend/process/lock observations](preflight.json)
- [Mechanical validation](validation.json): 24 freeze checks, including no evidence `start`/`end`, prompt forbids positions, user message equals the frozen packet, aliases P1–P6, request digest matches the plan, no run directory or journal, and unchanged T32/T35/fixture hashes

No source code, prompt from an earlier task, human answer, packet or accepted ledger was edited. No new command or workflow was adopted; the freeze uses the existing runner in its offline planning mode and the existing contract.
