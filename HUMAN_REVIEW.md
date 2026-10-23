# Human review desk

**This is your place to read what the agents need from you and write your answers.** Agents prepare decisions, samples and demos here. You can respond in the **Your response** areas, save this file, then tell the next agent “continue working.” You can also answer in chat; the agent must preserve your actual answer here with its source.

[MASTER_PLAN.md](MASTER_PLAN.md) owns the roadmap, progress and decision register. This file holds the readable questions, evidence and your original responses—not a second project plan. No coding or JSON editing is required. Empty answers, example text and unchecked choices are not approval. Never put API keys or other secrets here.

## Start here

| Item | What to do | Time |
| --- | --- | --- |
| [HR-008: grade three topic-tag examples](#hr-008-grade-three-topic-tag-examples) | Read each passage and proposal; write acceptable, incorrect or unsure, plus any rule you want us to follow | About 5–10 minutes |
| [Demo: what the small tagging run produced](#demo-01--saved-topic-tagging-results) | Optional: see what worked, what failed, and what it cost | About 2 minutes |
| [Future request format](#template-for-future-agent-requests) | For agents to use when a new decision, sample packet or demo is ready | No response needed |

The standards/cost scorecard (HR-003), fresh blind source grading (HR-004), and speaker/date calibration (HR-005) are **not being requested here yet**. Agents must prepare those concrete packets first. Grading these three examples does not approve a full run, set a corpus-wide accuracy target, or decide whether OCR cleanup can be skipped.

## HR-008: grade three topic-tag examples

### Agent's request

- **Request version:** HR-008-v1, prepared 2026-10-22; H2 calibration checkpoint. Request state and delivery are recorded in the master plan.
- **Why we need you:** we have source-based AI reviews, but we need to learn whether these outcomes match your research expectations.
- **What you are grading:** the usefulness and evidence for a topic assignment. A _substantive_ topic is something the passage actually addresses; a _passing mention_ does not qualify it for that substantive-topic filter. Your existing rule that explicit petition requests count as substantive remains in effect; we are not asking it again.
- **What this is not:** a blind test. You can see model outputs and the agent's recommendations. These are old diagnostic cases, not a representative accuracy benchmark or the untouched ten-window blind sample.
- **What waits:** calling these judgments human-calibrated, or adopting a new policy from them.
- **What can continue:** offline preparation and already authorized bounded diagnostics. You do not need to supervise every model request or label the whole corpus.

For each sample, write **acceptable**, **incorrect**, or **unsure / need more context**, then a short reason. For a model disagreement, say which behavior you prefer or whether both are reasonable. You can leave an item unanswered; an agent must keep it pending.

### Sample S1 — finding voting rights despite damaged OCR

**Source:** Part 1, printed page 589, scan leaf 707, IA item [congressionalg7391unit](https://archive.org/details/congressionalg7391unit). Paragraph `par_000707_000027` in diagnostic window `rawstatic-distractor-p1-01`. The link opens the item; it is not a verified direct image-page link.

**Original OCR, unchanged:**

> The right to vote is the right of self-protec- tion, through the possession of a share in the Government. Without this a man's rights lie at the 'mercy of other men Avho have every self- ish incentive to rob and oppress him. This is the great central idea of a republican Govern- ment. The absence of this is the source of all despotism. I would ask, what white man would consider himself safe without the right to vote, especially if the Government was exercised exclusively by a hostile race?

**What the models proposed:** Mini and Qwen both treated **voting rights** as a substantive subject. They also proposed civil rights based on other paragraphs in the full window; this question concerns only voting rights in the excerpt above.

**Agent's recommendation:** this is a useful supported match even though words such as `self-protec- tion` and `Govern- ment` are broken. That recommendation is an AI assessment, not your answer.

**Question:** Would you want this passage returned when you filter for voting rights? Is that tag acceptable from this evidence?

#### Your response — S1

- **Grade:** _Write here._
- **Reason or correction:** _Write here._
- **More context needed, if any:** _Write here, or leave blank._

### Sample S2 — a model guessed from a truncated petition

**Source:** Part 2, printed page 1176, scan leaf 328, IA item [congressionalglo7392unit](https://archive.org/details/congressionalglo7392unit). Paragraph `par_000328_000032` in `rawstatic-distractor-p2-01`. The next paragraph starts a different petition; the cited paragraph stops at “American.” The missing object is not established by this excerpt.

**Original OCR, unchanged:**

> By Mr. MOORHEAD: Tlie petition of GCO citizens of Pennsylvania, praying for protection to American

**Mini's proposal:** **military affairs — substantive**. Its explanation said the request was in a postwar context and acknowledged that the text was truncated.

**Qwen's behavior:** it did not assign military affairs from this fragment. It identified a separate Army reference elsewhere in the window as mention-only context for a property-loss petition.

**Agent's recommendation:** reject Mini's military assignment for this fragment and retain uncertainty. The missing words could change what “protection” means; the date/context alone does not supply them.

**Question:** Do you agree that this should stay unclassified/uncertain for military affairs unless more evidence is obtained? How should the system behave when the text is incomplete like this?

#### Your response — S2

- **Grade of Mini's assignment:** _Write acceptable, incorrect or unsure._
- **Preferred behavior or rule:** _Write here._
- **More context needed, if any:** _Write here, or leave blank._

### Sample S3 — is legislative procedure a real second topic?

**Source:** Part 5, printed page 4132, scan leaf 404, IA item [congressionalglo7395unit](https://archive.org/details/congressionalglo7395unit). Paragraphs `par_000404_000003` and `par_000404_000004` in `rawstatic-distractor-p5-01`. The first is reproduced in full; the second quotation is its neighbor's opening excerpt.

**Original OCR, unchanged:**

> House came to a conclusion on the subject as to what they supposed their employes ought to have, and I believe they passed a resolution giving their employes the salaries which this amendment proposes to give'the corresponding officers of the Senate. It is said, however, that what they undertook to do they were not au- thorized to do, and that it may be stricken out ; butthat will make no diflerence finally, if Congress should come to the conclusion that the increase was not unreasonable and that it was judicious to distribute it among their em- ployes. I suppose if it was illegal when they fixed it, if it was so adjudged by us, we could make it legal, and it would not alter the pro- portion, and would not change the propriety of this bill.

**Neighboring context, exact excerpt:**

> I will say, however, that the special com- mittee that was raised with directions to equal- ize the salaries of the Senate emploj'es with those of the House, equalized upon the hy- pothesis that what the House had done was or would be made legal, and that it would stand as the judgment of the House that their sala- ries ought to be enhanced to that amount.

**What both models agreed on:** public employee compensation is a substantive topic. They also used the later Sergeant-at-Arms pay discussion in the full window as evidence.

**Where they differed:**

- **Mini:** congressional procedure is only a passing mention; the substantive issue is salaries.
- **Qwen:** congressional procedure is also substantive, because the passage discusses committee action, a House resolution and whether salary changes are legal.

**Agent's assessment:** the words support both procedural context and pay policy. Whether procedure deserves its own substantive filter match is a research-usefulness boundary, not something JSON validation can settle.

**Question:** If you filter for congressional procedure, should this passage be included? Prefer **substantive**, **passing mention**, **depends on a more specific rule**, or **need more context**, and explain briefly.

#### Your response — S3

- **Preferred treatment:** _Write here._
- **Reason or rule:** _Write here._
- **Is the compensation tag acceptable?** _Write here._

### Your overall guidance — HR-008

- **Anything the system should do differently:** _Write here, or leave blank._
- **Any sample you want to revisit:** _Write here, or leave blank._
- **Name/initials and date, if you want them recorded:** _Optional; write here._

### Agent follow-up — HR-008

**Not yet applied.** Human response areas are unfilled when this packet is created. The next agent must read actual responses, preserve unanswered items, record the answer source/time/version, update HR-008 in the master register, and state the adopted scope or remaining uncertainty here. Do not write a human answer, infer one from this request, or mark the whole packet approved because one sample was graded.

**Supporting evidence:** [saved Mini inputs](artifacts/v2-tagging-retry-20261022/runs/topic-mini-20261022-02/frozen-inputs.json), [Mini results](artifacts/v2-tagging-retry-20261022/runs/topic-mini-20261022-02/results.jsonl), [Qwen first run](artifacts/v2-tagging-retry-20261022/runs/topic-qwen-20261022-01/results.jsonl), [Qwen first-passage retry](artifacts/v2-tagging-retry-20261022/runs/topic-qwen-warm-p1-20261022-01/results.jsonl), and [independent paired review](artifacts/v2-tagging-retry-20261022/paired-comparison.json). These local ignored files need copying on another machine. The excerpts above are included here so you can read the request without opening JSON or running a model.

## Demo 01 — saved topic-tagging results

**Type:** read-only walkthrough of a completed diagnostic; no model calls, server or new spending. Not a demo of a finished search service or web application.

| What happened | Observed result |
| --- | --- |
| Same five raw passages were given to Mini and Qwen | Both found useful main subjects; the samples above show successes and differences |
| Mini processed the five passages | 13.690 seconds; estimated $0.0139935 (about 1.4 cents); five valid outputs |
| Qwen processed them locally | 173.246 seconds including a timeout and one successful retry; $0 API charge; usage for the timeout unknown |
| We checked source references and reviewed meaning separately | Valid JSON did not prevent Mini's unsupported military tag |

Read Samples S1–S3 to walk through actual source → model proposal → review question. No command needs to be run. These tiny timings and judgments do not establish full-corpus quality or cost, and comparing them does not decide P0.

### Your optional demo feedback

- **What was clear or confusing:** _Write here, or leave blank._
- **What you want the next demo to show:** _Write here, or leave blank._

## Template for future agent requests

**Template only—no human response requested until an agent creates a concrete item with a real HR ID.** Keep the active queue small; put answered items below active ones without deleting original human responses.

### Agent prepares

- **ID / version / master-plan gate / related milestone:**
- **Plain-language title and specific question:**
- **Why this decision matters; recommendation and alternatives:**
- **Evidence or demo:** exact source excerpts, context/citations and proposed output; identify whether source-only blind grading or output-informed calibration. Include expected/observed behavior and safe demo steps. No hidden model call in a supposedly read-only demo.
- **Scope, cost/time and review effort:**
- **What waits; what work continues:**
- **If a run is being requested:** exact command, provider/configuration, request/runtime/spending limits, recovery/stop behavior and known risks. Ordinary sample grades are not full-run approval.
- **Delivery:** when/how the human was notified; current state remains in the master HR register.

### Your response

- **Decision or grades:** _Write here._
- **Corrections, conditions or uncertainty:** _Write here._
- **Date/name, optional:** _Write here._

### Agent applies and reports back

- **Actual answer and provenance:** preserve the original human response; do not overwrite it with a summary.
- **What changed / effective policy scope / unresolved items:**
- **Master-plan HR/readiness updates and evidence links:**
- **Next check or reopening condition:**
