# Tool-using processing: research and recommendation

Research date: 2026-10-26. T17 is documentation research supporting M1.4/M2.4/M6, requested by the stakeholder. This is a recommendation for discussion, not framework adoption, implementation or permission for inference. The existing prepared prompt → structured output workflow stays intact. Task ownership and any future work belong solely to [MASTER_PLAN.md](../../MASTER_PLAN.md#ordered-task-queue).

**Recommendation:** a bounded tool-using path is worth evaluating for passages where additional evidence could change the answer. Keep ordinary processing on the current path. LangGraph is the stronger candidate for explicit branching and durable workflow state across local Qwen and OpenAI providers; OpenAI Agents SDK is a credible alternative for a compact agent/tool loop. A small loop using existing provider APIs remains an important lower-complexity comparator. No documentation establishes that any of these improves this collection’s historical accuracy or pays for its integration cost.

## What a researcher would gain

Suppose a passage starts mid-speech. A researcher asking who spoke might receive unknown or a wrong attribution if the model only sees that page. A tool-using model could request preceding context, inspect the returned speaker cue and cite the specific passage that supports its answer. It must stop at intervening turns, chambers and proceedings; requesting more text is not permission to propagate attribution indefinitely. Existing cross-page attribution evidence is more relevant than another unrelated sample.

Suppose a clear name is absent from the member roster. A lookup tool could return no match with the roster’s version and coverage, while preserving the original name. It must not manufacture a member match or silently expand the authority list. The McPherson passage already frozen in the project is a candidate for testing this behavior; his absence from a specified roster has not been established.

For the presidential-message example, the agent might request surrounding paragraphs to locate the message boundaries and distinguish issuing authority, reader and later debate. If the text only says “was read,” more reasoning cannot supply a named reader without evidence. The exact presidential passage remains unlocated; this is a proposed use case, not a demonstrated result.

## Three capabilities that should not be confused

| Capability | What changes | Does it require an agent SDK? |
| --- | --- | --- |
| More reasoning within one request | The model spends more effort on the same supplied evidence. | No. Supported controls depend on the exact model and runtime. |
| Tool use across requests | The model requests a roster lookup, neighboring context or available source image, receives results and continues. | No. An SDK can manage this loop; it does not create the model’s underlying capability. |
| Production supervision | Software routes cases, enforces budgets, saves work, pauses for problems and presents review items. | No. Many steps should remain deterministic even if an agent handles selected decisions. |

The current role adapter explicitly requests reasoning effort `none` for both transports; the reading request builder sets `think=False`. Those are source-code observations, not proof that every historical model invocation had identical behavior. Ollama documents model-specific thinking controls separately from tool calling. Therefore, increased reasoning in an otherwise unchanged request is a distinct alternative, with its own latency/token cost. No settings were changed. [Thinking controls](https://docs.ollama.com/capabilities/thinking), [tool calling](https://docs.ollama.com/capabilities/tool-calling).

## Framework comparison

| Option | Documented capability | Project-fit judgment and tradeoff |
| --- | --- | --- |
| Existing APIs plus a small bounded loop | Ollama documents multi-turn tool requests and results; OpenAI exposes function tools. | Lowest new dependency burden for a few read-only tools. We would own loop state, validation, termination and recovery. Useful comparator before adopting a framework. |
| OpenAI Agents SDK | Agent definitions, tools, orchestration, run state and tracing; non-OpenAI providers use SDK-specific adapters. | Good candidate for a compact tool-using worker, particularly an OpenAI-oriented path. A local Qwen endpoint is a compatibility question to prove, not a guarantee from an OpenAI-compatible URL. OpenAI-hosted tools/features do not automatically transfer to local models. |
| LangGraph | Mixes deterministic steps and model-driven decisions; supports checkpointed state and pause/resume. LangChain has a ChatOllama integration. | Best candidate if branching, source requests and human-review pauses become substantial. More state/checkpointer integration than a tiny loop; avoid creating two competing records of completed work. LangChain is not required by LangGraph itself. |
| Qwen-Agent | Qwen-focused tool templates/parsers and custom tools with compatible model endpoints. | Relevant Qwen-specific fallback if tool-call parsing is the hard problem. Less compelling as the first common orchestration layer for this mixed-provider project; do not stack it with other runtimes by default. |

Sources: [OpenAI Agents SDK](https://developers.openai.com/api/docs/guides/agents/sdk), [models/providers](https://developers.openai.com/api/docs/guides/agents/models), [OpenAI tools](https://developers.openai.com/api/docs/guides/tools), [LangGraph overview](https://docs.langchain.com/oss/python/langgraph/overview), [persistence](https://docs.langchain.com/oss/python/langgraph/persistence), [ChatOllama](https://docs.langchain.com/oss/python/integrations/chat/ollama), [Qwen-Agent](https://qwen.readthedocs.io/en/latest/framework/qwen_agent.html). These establish available framework patterns, not this repository’s end-to-end compatibility. No package was installed or version selected.

The repository currently depends on the OpenAI client and Pydantic, with custom provider adapters, source validators, request journals and the shared Ollama lock; it does not declare any of these agent frameworks. Directly inspected: `pyproject.toml`, `role_provider.py`, `reading_requests.py`, `reading_dispatch.py`, and the existing recovery findings linked from the master. The role-v2 specializer defect remains T13; adopting an SDK would not repair it automatically.

## How it could fit without replacing existing processing

Proposed flow: prepared request → existing worker → host validation → accepted proposal or unresolved case. An optional evidence-gathering worker could handle selected unresolved cases and return the same validated proposal/unknown form. Evidence requests might include bounded neighboring paragraphs, versioned roster lookup and a hash-checked cached scan where the exact model supports images. Missing evidence must remain explicit. These tools would require implementation and tests; this report does not claim they already exist as an agent API.

Routing must consider deterministic coverage/validation signals and sampled apparently successful outputs, not merely model confidence. A confidently wrong first answer can otherwise bypass escalation. An agent should choose among bounded evidence requests and whether to return unknown/review. Host code should retain ownership of source access bounds, retries, call/time/token budgets, sequential execution and publication. The first design needs no shell, corpus writes, unrestricted web browsing, prompt changes or self-directed spending. A separate batch supervisor is a different proposal from this passage-level worker.

Keep exact tool arguments/results, source hashes/spans, model/configuration, raw replies, attempts, elapsed/usage unknowns and the final validator outcome. Framework traces or conversational memory do not replace the source ledger or human decisions. OpenAI documents built-in tracing, enabled by default in its usual SDK path: a local-only design must deliberately configure trace export and retention. [Integrations and observability](https://developers.openai.com/api/docs/guides/agents/integrations-observability).

LangGraph checkpointing also does not make a paid or local model call exactly once. Its documentation says an unfinished task may execute again on resume; side effects need idempotency or existing-result checks. Preserve our journal’s ambiguous-attempt handling and exact request reuse at the provider boundary rather than assuming checkpoint recovery settles whether a request ran. This integration is still M2.4 work. [Functional API replay and idempotency](https://docs.langchain.com/oss/python/langgraph/functional-api#idempotency).

## Is the extra work worthwhile?

Likely useful when the missing ingredient is accessible evidence: previous-page speaker cues, ambiguous roster candidates, or embedded-document boundaries. Less promising for print that is genuinely unreadable, missing authority coverage, or policy questions requiring human judgment. More steps can introduce incorrect tool choices and plausible unsupported answers as well as fix omissions. Documentation cannot establish the balance for this corpus.

Extra calls, reasoning tokens, loaded context, image support, local model switching and review effort all count. Illustrative arithmetic only: with1,000initial calls, escalating20%of cases for two additional model calls produces1,400calls before retries or separate triage. This is not a measured estimate. For N initial calls, escalation fraction f and mean a additional calls, the count is approximately N × (1 + f × a); per-call time/context may also change. We have no defensible speedup, cost saving or accuracy improvement estimate yet.

A decision should compare the unchanged baseline with deterministic context/roster enrichment and then bounded model-selected tool use. Use the same existing passages, evidence access and declared reasoning settings where possible. If thinking settings are changed too, report that as a separate variable; do not credit an SDK for extra reasoning or evidence. A human-confirmed answer and a provisional interpretation must remain distinguishable.

Proposed decision measures: supported speaker/author/reader assignments and omissions, wrong confident links, appropriate unknowns, evidence boundaries, tool argument validity, actual calls/time/tokens, recovery duplication and human review minutes. Check ordinary cases and cases the router would fail to escalate as well as obvious exceptions. Reuse existing evidence and saved results when compatible; changed inputs need new identities. Do not repeat spent pilots to produce another framework demonstration.

**Suggested next decision:** discuss whether the optional evidence-gathering path addresses a material production blocker. If proceeding, prepare a minimal tool contract and offline fake-provider comparison before choosing a dependency. A later finite live comparison needs a named task with exact cases/model digests/runtime compatibility, source expectations, tool/result/turn/output/time limits, sequential lock, cumulative budget and stopping rule. A turn limit alone is not a total resource budget. Numerical limits and quality criteria have not been approved here. Repository engineering rules also require an independent GPT-6 evaluation before adoption of a new workflow; this research is not that independent verdict. No new experiment is an automatic prerequisite to the full run merely because an SDK exists.

Documentation/link checks complete this research unit only. The last code gate remains T16’s505passing tests; no code changed, and no new accuracy or production-readiness claim follows. M1/M2/M6 retain their existing states; T13 remains the next generic READY implementation task.
