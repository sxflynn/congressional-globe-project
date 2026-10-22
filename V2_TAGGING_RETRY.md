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
| `topic-mini-20261022-01` | Historical failed attempt:five HTTP401 errors, no model outputs or token usage |
| `topic-mini-20261022-02` | Updated key worked:five valid outputs,13.690seconds,estimated$0.0139935 |
| `topic-qwen-20261022-01` | Terminal:4valid/1timeout;157.041seconds |
| `topic-qwen-warm-p1-20261022-01` | Terminal:one valid same-input retry;16.205seconds;90secondtimeout |

The user replaced the expired key privately in `.env`; the five-case Mini retry completed. Do not put secrets in chat or logs. The failed Mini summary sums missing usage as zero; this is not verified billing or successful inference. Local Qwen uses the existing sequential lock and makes at most five requests, each capped at45seconds, with no automatic retries. Progress logs report completed/remaining requests, elapsed time and estimated remaining time.

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

This is encouraging evidence that the raw-text path can produce useful topic proposals. It is **not** representative accuracy, a representative paid/local quality ranking, causal evidence about OCR cleanup, or permission to scale. The broader vocabulary and prompt changed together, and the cases were already known diagnostics. No date, person, city or legislation authority assignments were established by this subject POC.

## Paired Mini and Qwen results

The updated Mini key worked: `topic-mini-20261022-02`, five calls/five valid outputs, **13.690seconds**,12,088input/1,095outputtokens, **estimated$0.0139935**. The cost uses recorded usage and the checked model rates, not an invoice. No automatic retries. Historical401responses remain preserved. Root verified identical five source windows and vocabulary/prompt/schema digests across Mini and Qwen, script snapshots,27materialized raw paragraph evidence records, and the unchanged blind human packet.

| Comparison | Mini | Qwen |
| --- | --- | --- |
| Time for this diagnostic | 13.690seconds,5calls | 173.246seconds,6calls including first timeout and warm retry |
| API cost | Estimated$0.0139935 | $0localAPI charge |
| Main topics | Voting/civilrights,petitioninfra/tax/restoration,spirits taxation,bill procedure,employee pay | Same main supported topics |
| Truncated petition “praying for protection to American…” | Adds military affairs in_scope despite acknowledging missing context; unsupported inference | Does not assign military subject from that fragment |
| Salary passage | Procedure mention_only,employee compensation substantive | Adds procedure in_scope; secondary scope remains uncertain |
| War-loss claim | Useful loose hint but OOV flagfalse | Useful loose hint and explicit OOV war-loss/property-compensation topic |

A separate Luna review compares every output with full raw text and the frozen definitions; root also inspects the outputs. These are provisional textual judgments. Mini's invented military topic is a real review finding even though its JSON and paragraph references validate. Conversely, source fragments do not justify inventing a subject to fill a vocabulary slot. Neither model is a universal winner from this sample. Different API enforcement (Mini strict schema versus local JSON-object prompting), a cold/warm local run, and one completion per case limit timing/quality conclusions. Token counts across provider implementations are not directly comparable.

Evidence: `mini-independent-review.json/.md`, `paired-comparison.json`, `mini-root-verification.json` plus the earlier Qwen/source reviews and per-run snapshots. No model calls are needed to inspect them. The review is not human gold, representative accuracy, or proof that cleanup can always be skipped.

## What happens next

1. A short-alias speaker-role POC distinguishing floor speakers, petition presenters and mentioned people; keep dates unknown unless explicit source evidence supports them. Topic classification does not establish those identities. This remains pending.
2. Human spot-checks of the truncated-petition failure and salary/procedure boundary, then fresh blinded labels and negative controls before quality/workload projections. The ten-window blind sample is unchanged and pending human labels.
3. People/city/bill authority resolution and a reviewed portable pilot remain open. Full processing stays human-launched.

Both providers' tagging attempts are terminal; do not rerun the completed commands unchanged. Use the latest `PROGRESS.md` checkpoint when continuing. The helper is a local artifact prototype, not an installed production command. Another machine must copy this evidence folder and earlier frozen source inputs. The final helper supports single-window selection,1–90secondtimeouts, authentication fail-fast and explicit unknown paid usage/cost; saved script copies preserve every earlier run configuration.
