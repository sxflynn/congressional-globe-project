# Improved five-passage tagging POC

This diagnostic retries the earlier failed subject examples using the broader draft vocabulary and short paragraph aliases. It preserves original OCR and the blind ten-window human sample. It tests whether model proposals are useful enough to justify a larger reviewed pilot; it does not establish corpus accuracy or prove cleanup unnecessary.

## What is being tested

Five old windows, one from each part: voting rights and equal rights; mixed petitions; whisky taxation; bill procedure; Senate employee salaries. Models receive the whole window plus identical subject definitions. They propose controlled topics with paragraph evidence, explicit uncertainty and optional separate loose discovery hints. All tags remain proposals. The human selected this rule before calls: **an explicit petition request counts as a substantive topic**, independently of who presents it or whether Congress endorsed it.

A separate Luna reviewer wrote source-based expectations before seeing outputs. Root caught and corrected its initial confusion between petition role and subject matter; initial notes remain archived. Neither the reviewer nor Codex is a human gold labeler.

## Execution and evidence

Evidence lives under `artifacts/v2-tagging-retry-20261022/` (Git-ignored; copy it when changing machines). `preflight.json` records authorization, queue/model state and pricing reference. Per-run folders retain frozen source, vocabulary, prompt, schema and script copies, full replies/errors, usage, timing and progress events. The runner is offline unless `--live` is explicit and refuses duplicate run IDs.

| Run | State |
| --- | --- |
| `topic-offline-20261022-01` | Completed without provider requests; source/schema plumbing only |
| `topic-mini-20261022-01` | Five HTTP401 errors: saved key expired; no model outputs or token usage |
| `topic-qwen-20261022-01` | Terminal:4valid/1timeout;157.041seconds |
| `topic-qwen-warm-p1-20261022-01` | Terminal:one valid same-input retry;16.205seconds;90secondtimeout |

Mini requires a replacement `OPENAI_API_KEY` in `.env` before another attempt. Do not put the secret in chat or logs. The failed Mini summary sums missing usage as zero; this is not verified billing or successful inference. Local Qwen uses the existing sequential lock and makes at most five requests, each capped at45seconds, with no automatic retries. Progress logs report completed/remaining requests, elapsed time and estimated remaining time.

## What the raw-text results show

The local work took **173.246seconds including the failed first attempt**, with five usable outputs across six requests and **$0API charge**. Recorded usage:13,368input/2,006outputtokens; the timeout has unknown usage. Electricity, hardware and coding/review work are not included. One warm retry is not proof of the timeout cause or a reliable throughput estimate. Root verified that the retry used identical input, prompt, schema and vocabulary. No OCR cleanup was applied.

| Source passage | Qwen proposal | Independent AI review |
| --- | --- | --- |
| Part1,p589: “right of suffrage,” “right to vote,” “equal liefore the law” | Voting rights and civil rights substantive; citizenship/time-extension procedure mention-only | Supported reading of damaged OCR; the first request timed out, retry succeeded |
| Part2,p1176: savings banks ask not to be “subject to certain taxes” | Taxation substantive; harbor improvements and non-restoration petition also substantive | Supported under the human-selected petition rule; no claim Congress endorsed the petitions |
| Part3,p2437: spirits duties, illicit stills and revenue collection | Taxation; separate hint for illicit distillation/smuggling | Taxation supported; whether alcohol enforcement also needs an OOV subject is a taxonomy question |
| Part4,p3422: conflicting printed bills and explanatory joint resolution | Congressional procedure; hints for bill-print discrepancies and passage strategy | Supported; no constitutional amendment or railroad subject inferred from insufficient context |
| Part5,p4132: Senate employee salaries and Sergeant-at-Arms pay | Public compensation plus substantive congressional procedure | Compensation supported; procedure may be secondary context and needs review |

The separate reviewer read full raw windows and checked outputs, not just JSON syntax. Root audited its conclusions too: an oath mentioning the Constitution may yield an overbroad controlled mention-only mapping, but that is a scope judgment, not an invented explicit exclusion in the vocabulary. The reviewer’s first petition-role/subject confusion was corrected before calls; original notes remain available. “AI review” remains provisional, not human-certified truth. Loose hints are evidence-linked discovery aids, never hard metadata.

This is encouraging evidence that the raw-text path can produce useful topic proposals. It is **not** representative accuracy, a paid/local model comparison, causal evidence about OCR cleanup, or permission to scale. The broader vocabulary and prompt changed together, and the cases were already known diagnostics. No date, person, city or legislation authority assignments were established by this subject POC.

## What happens next

1. Replace the expired Mini key privately in `.env`; then run the same five inputs once with a new run ID for an actual comparison. The saved failed run must remain intact.
2. Have a human spot-check the salary/procedure boundary and vocabulary coverage, using the concrete examples rather than JSON validity as the acceptance standard. The ten-window blind sample is still unchanged and pending human labels.
3. Run a separate short-alias speaker-role POC distinguishing floor speakers, petition presenters and mentioned people; keep dates unknown unless explicit source evidence supports them. This remains pending.
4. Use a fresh reviewed sample before estimating quality, residual workload or corpus processing time. The full workflow stays human-launched.

Mini resume command after credential replacement (five calls, no retries; refuses an existing run ID):

```bash
UV_CACHE_DIR=/private/tmp/congressional-globe-uv-cache uv run python \
  artifacts/v2-tagging-retry-20261022/runner.py --backend openai \
  --model gpt-5.4-mini --run-id topic-mini-20261022-02 --live
```

Do not rerun Qwen unchanged to inspect these results. Read `independent-review.json/.md`, `source-expectations*.json/.md`, `root-verification.json` and per-run snapshots. The helper is a local artifact prototype, not an installed production command. Another machine must copy this evidence folder and the earlier frozen source inputs. Final helper adds single-window selection, a1–90secondtimeout option, authentication fail-fast and explicit unknown paid usage/cost; live script copies preserve the earlier behavior without rewriting it.
