# T21: fair context comparison and stop decision

2026-10-26. Offline design supporting M2.5/M5.1. **Recommendation: DEFER the current optional tool prototype; do not proceed to T22 adoption review, T23 implementation or a live comparison on this evidence.** This is a design recommendation, not a human decision, proof that tools never help, or completion of M2/M5/P0. Existing processing stays intact.

## Plain-English finding

We want the system to identify who is speaking without guessing. Nearby text can help. But the saved examples already give the AI that nearby text. Asking the AI to fetch it again would not show that it gained useful evidence. In the example where a speech crosses a page, the proposed short lookup stops at page headings before it reaches the speaker's name. In the damaged petition, the missing words are not in the text the tool is allowed to return.

These findings do not establish which approach gives better answers. They establish that the proposed test, as currently bounded, cannot demonstrate the intended benefit fairly. Building an extra AI loop now would add work before we have a suitable comparison. The simpler possibility—preparing useful surrounding text before asking the AI—remains worth considering in separately bounded metadata work. This document does not implement or adopt it.

Inputs: [T19 draft](../agentic-design-20261026-01/README.md), [T20 cases and limits](../agentic-cases-20261026-01/README.md), [exact manifest](../agentic-cases-20261026-01/manifest.json), and [T17 research](../../docs/reference/agentic-workflow-research.md). These are prior documents/evidence, not fresh framework research. No package/backend capability claim is added.

## What the comparison would ask

Does allowing the model to choose a small amount of nearby text improve supported speaker/date assignments or appropriate unknowns enough to justify extra requests, delay, review and recovery complexity, compared with automatically supplying the same permitted text? Compare evidence access, not brand names or framework features.

Use the same frozen source material, initial targets, controlled vocabulary, output contract, model/version, backend, reasoning setting, sampling settings and semantic instructions. Keep role, date and subject outputs separate. Tool instructions/envelopes necessarily differ between approaches; record their exact bytes and costs rather than claiming perfectly identical prompts. Reject a design that changes reasoning effort, targets or available evidence in only one approach and calls the result a tool benefit.

| Approach | Supplied evidence and behavior | What a difference could mean |
| --- | --- | --- |
| A: unchanged prepared request | Exact existing complete input packet and original validated output path. Reuse a saved result only if the entire historical request/configuration is compatible. No repeated historical call. | Describes prior behavior on already supplied evidence; historical different-model/task results cannot become a controlled new comparison. |
| B: automatic nearby text | Same original targets and source access policy; host computes a fixed ordered set of permitted neighboring paragraphs before one request, independent of model output. Deduplicate text already present. | More evidence or different packaging, if either actually changes. If nothing new is available, record no evidence change; do not call that an enrichment success. |
| C: model-selected nearby text | Same original targets and accessible neighboring set as B, same source/continuity/size limits. Model can request up to the T19 draft allowance, then return an existing supported proposal or explicit unknown/review. | Selection of evidence and extra interaction, with their full cost; not a framework or reasoning-setting effect. C can inspect a subset of B's permitted set, never a larger set. |

B and C must share one precomputed per-item union of allowed source paragraphs within cumulative bounds. B receives that union once in canonical order; C can choose among exactly that union with the same cumulative text limit. If the union cannot fit B's declared context/request budget, that item is not eligible for a matched comparison. Repeated C requests count against its limits even when bytes duplicate; B cannot be penalized by artificial duplicate text. Do not preselect B's context after looking at C's successful requests.

For these full historical packets, B/C have no demonstrated new permitted evidence to add. Merely moving text already in A into a later tool message measures delivery/selection overhead, not evidence acquisition. It might someday support a separate token-saving hypothesis, but T20 supplies no model-specific token measurements or approved benefit criteria for that hypothesis.

### A possible future target-focused comparison is a different experiment

A potentially informative design would give all three approaches an identical smaller initial target packet. A would use it unchanged; B would add the fixed permitted context; C would choose from that same context. That would test missing-context recovery. It is **not** an unchanged historical request: removing existing context changes the input hash and can manufacture a failure. The reduced packet needs a real production rationale, explicit context-only versus target semantics and separately frozen identities before review. Saved complete-packet results cannot be reused as its baseline. This is a design alternative, not permission to generate requests, widen T19 or select new cases.

## Apply the rules to the four existing windows

| Window / unchanged target scope | Supported or unknown outcome to inspect | Eligibility / obstacle |
| --- | --- | --- |
| `t2-4-053`: existing twenty-paragraph packet; role and date assessments remain separate | Explicit P1 Kasson cue; P2 potential continuation; P3 Holmes stops carryover. Ordinary “may” is not a date. Date fixture remains unknown throughout. | P1 is already in the full packet. A future target-focused P2 comparison could obtain P1 within one step, but continuity policy is AI-provisional and T10 date regions do not provide speaker edges. No historical role reply for this window in the inspected T20 inventory. |
| `hr008-cross-page-p5-403-404-v1`: existing complete sixteen-paragraph role packet | Assess P12/P13 continuation with preceding discourse while preserving other turns and headers as distinct. Human HR-008 supports the need for cross-page evidence; it does not grade a new named attribution to P12/P13. | Full packet already includes P7 cue/P8 continuation. A future P12/P13-focused request cannot obtain them under T19's two-paragraph/fixed-anchor rule: nearby paragraphs are page furniture. No silent header skipping or re-anchoring. |
| `house-opening-december-4-1865-v1`: existing six-paragraph date packet | P3 explicit1865-12-04 supports proposed P3–P6 date; P1/P2 unknown. Stop Senate/House speaker and date propagation. Do not invent Clerk identity. | Full packet already includes the date and boundary. Useful safety check, not a positive evidence-acquisition case. A preceding request from P3 must stop at the chamber transition. |
| `rawstatic-distractor-p2-01`: existing twelve-paragraph subject window | Reject military-affairs guess from the truncated petition; preserve petition discovery and unknown object. Human-reported “American labor” stays separate from raw supplied text. | Missing object absent from the permitted raw fragment; next paragraph starts another petition. Subject schema differs from role/date schema; do not merge their metrics or imply the neighbor tool supplies a scan or subject classifier. |

Do not split one window into extra historical cases to claim a larger sample. Potential target subsets above are explanatory alternatives, not newly frozen requests. All four are development-exposed diagnostics; none supports corpus accuracy percentages or a policy for all five parts.

## How results would be judged if a later comparison is approved

Retain one paired row for every original target/assessment, including failures and cases with no change. Preserve exact final output and supporting paragraph/cue/source hashes and offsets. Apply existing host validators first, then separately assess whether the cited words actually support the claim. A valid output format is not a correct historical answer.

Record these outcomes separately, with no weighted aggregate score invented here:

- Supported assignment newly supplied or correctly retained; relevant omission repaired or still missing.
- Unsupported speaker/author/reader link, wrong scope or date carryover; new error introduced versus already present.
- Appropriate unknown/review where evidence is absent; unsupported refusal when supplied evidence was sufficient, subject to actual review.
- Boundary respected or crossed; text fetched from the wrong source/order; forbidden or malformed argument; inaccessible cue versus model failure to request an accessible cue.
- Unchanged answer, duplicate context request, tool/resource stop, invalid final output, refusal, timeout and ambiguous attempt. Do not exclude these from the denominator or silently repair/retry them.

For every interpretation, label its provenance: actual human decision with exact scope; provisional frozen expectation; software integrity check; newly proposed AI assessment; or unresolved disagreement. T20's hand-authored date results and saved model replies are not independent gold. HR-005's Wade judgment for its specific reply/following paragraph cannot be extended to the earlier P12/P13 segment. No new human round or reinterpretation of HR-009/HR-010 is authorized by this protocol.

A future review table should hide approach/model labels where practical, use the same declared rubric and record which source context the reviewer actually inspected. Record review seconds/minutes per item, not just whether review happened. If actual human judgment is needed but unavailable, retain “unresolved”; do not substitute model self-grades or request an extra review round automatically. No numerical accuracy, latency or cost threshold is approved here.

### Catch cases that an automatic selector would miss

Do not run C only on answers labelled uncertain and then report only its successes. A confidently wrong assignment can avoid escalation. On this tiny design set, retain every original case in the comparison table, whether the routing rule selects it or not. Freeze the routing rule before outcomes; permitted deterministic signals could include missing cue coverage, source/continuity gaps or validation failure. Self-reported model confidence alone is insufficient.

For each case record selected/not selected, reason and whether accessible evidence could address its actual defect. Separately classify router miss, wrong/missing source access, tool choice failure and answer interpretation error. Report apparently successful unselected cases and unreachable-evidence cases. Any future direct test of C on a case the real router would skip is a labelled diagnostic override, charged separately, not evidence that production routing succeeded. No extra requests are authorized to populate this table now.

## Total work and stopping rules

For each approach/work item retain initial and continuation provider attempts; returned, failed, refused and ambiguous requests; raw replies; exact input/output/tool bytes and text; tool invocations; known input/output/reasoning tokens; unavailable usage; measured request/wall/host time; review minutes; and integration/recovery work. Provider-specific reasoning-token accounting may overlap output tokens: retain native fields and avoid adding the same usage twice. A null usage/time is unknown, never zero.

The accounting unit is an immutable attempt ID linked to exact request/configuration hashes and original source/target identities. Distinguish reused historical results, offline tool replay and actual new requests. Count provider calls once even if framework traces report several events. Record new cost and cumulative historical cost separately; do not sum unrelated legacy experiments into an invented common budget. Reuse must preserve the original usage unknowns, not recalculate fictitious savings. Local inference has time/resource cost even when API charge is zero.

**Actual T21 work:** zero experiment-provider requests, zero tool executions, zero downloads, zero new timing/token measurements and no human grading. A Luna delegate reviews this preparation; that assistance is not a corpus-model experiment or T22's independent verdict. T20 retains two saved cross-page role replies and two saved petition-topic records; those four records do not constitute twelve matched A/B/C outcomes. Existing code gate evidence remains T13; no implementation is being tested here.

If reopened, T25 must freeze finite total provider-attempt, per-request/total time, token/output, tool invocation/result-text/byte and human-effort limits, exact backend/model/digests, reasoning settings and stop criteria **before** T26. T19's two tool slots/8,000code-point proposal is not a provider budget. Initial and continuation requests both consume the provider allowance. No automatic retries, sample substitutions, boundary relaxation, model changes or limit extension. Unknown elapsed usage or an ambiguous attempt blocks new dispatch pending established journal reconciliation; it cannot be treated as free remaining capacity. Ollama remains sequential under its shared lock. Exact raw tool results must be journaled before a continuation can be sent; interrupted reuse must be proved in T24.

Stop the strand before implementation if there is no accessible missing evidence, no matched production-relevant initial packet, or no agreed benefit criterion. Stop a future item on identity/source mismatch, missing continuity, invalid tool access, incompatible backend/schema, budget exhaustion or ambiguity; preserve the reason and actual partial output. A normal inability to establish an answer yields unknown/review under the existing output contract, not another open-ended search.

## Decision and precise unresolved items

**Defer the current prototype.** Neighboring evidence has plausible research value, but this bounded tool/test combination does not yet establish a useful incremental capability over existing complete packets. This is a local design-fit finding, not evidence of model failure or proof that automatic context wins. No live quality/cost winner is declared.

Reopening needs a named, separately bounded design task that resolves the relevant items below; none is silently authorized by T21:

1. A production-relevant definition of initial target and context-only paragraphs, plus a declared baseline that does not hide historical context removal.
2. Exact allowed context union and continuity assertions with provenance. If cross-page headers are to be bypassed or the reach changed, an explicit T19 successor/amendment, equal B/C evidence access and independent review are required. Preserve original T19/T20 artifacts unchanged.
3. Compatible role/date/backend handling, context-only target coverage and actual tool capability; current fake-client checks do not prove live acceptance. Subject cases require their own unchanged vocabulary/validator.
4. A meaningful success/stop criterion balancing supported corrections, newly introduced mistakes, appropriate unknowns, time/cost and review effort, with applicable human judgment actually available. Do not invent an acceptable error rate.
5. Only after design fit is established: T22's actual human-run independent GPT-6 verdict, T23/T24 offline implementation/recovery evidence and T25's finite authorized comparison manifest. No framework dependency is selected now; a deterministic context path and a small existing-client loop remain alternatives for that review.

The master remains the only queue. T21 completes this protocol/recommendation scope; T22 retains its missing proceed recommendation/actual independent-review dependency, and T23–T27 remain blocked. This optional strand's deferral does not add a new pilot acceptance gate. Main metadata, durable workflow, quality and P0 decisions remain incomplete. Do not invent another ready task or spend remaining historical allowances because this strand has stopped.

## Preparation checks

[Decision/input hashes](decision.json) preserve the recommendation and exact inputs. [Luna preparation review](review.json) agrees with deferral and records incorporated comparison cautions; it does not replace independent adoption review. Validation checks input hashes, T20 copied-source hashes, local links, JSON parsing, task/parent/stage/next-action consistency and required Markdown formatting plus `git diff --check`. These are document/evidence checks, not model experiments or tested tool behavior. The last code gate remains T13 (511 tests); documentation-only T21 does not need a fresh code gate.
