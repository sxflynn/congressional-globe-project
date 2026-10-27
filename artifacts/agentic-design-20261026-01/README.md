# T19: bounded neighboring-context contract

2026-10-26. **Draft, unadopted; no implementation or model authorization.** Supports M2.5/M1.4. A researcher asking who spoke at the start of a page needs the preceding speaker cue without inheriting an unrelated speaker from another proceeding. This contract specifies evidence access, not attribution truth or an automatic boundary detector.

Inputs inspected: [T17 research](../../docs/reference/agentic-workflow-research.md), [metadata semantics](../../docs/reference/research-design.md#required-metadata-semantics), [role-v2 contract](../../src/congressional_globe/role_v2.py), [date contract](../../src/congressional_globe/scoped_dates.py), and [T10 evidence](../scoped-date-contract-20261026-01/README.md). Existing host validators remain authoritative. Examples below are synthetic contract illustrations, not historical findings. T20 selects actual cases separately.

## One callable operation

`neighbor_context` reads only a frozen host allowlist of neighboring raw paragraphs. Unknown/review is the ordinary final output path, not a second tool. No shell, paths, URLs, search terms, roster lookup, scan access, writes or batch supervision are exposed.

Proposed argument JSON Schema (Draft 2020-12):

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["packet_sha256", "anchor_id", "direction", "paragraph_count"],
  "properties": {
    "packet_sha256": { "type": "string", "pattern": "^[0-9a-f]{64}$" },
    "anchor_id": { "type": "string", "minLength": 1 },
    "direction": { "enum": ["preceding", "following"] },
    "paragraph_count": { "type": "integer", "minimum": 1, "maximum": 2 }
  }
}
```

The host specializes packet hash and anchor enums to the immutable initial targets. Returned paragraphs cannot become new anchors: no outward crawling. Two paragraphs per invocation, at most two tool invocations and 8,000 cumulative raw-text Unicode code points per work item are proposed offline safety ceilings, not an approved live budget. Every invocation, including rejected/unavailable/repeated arguments, consumes a tool slot. Host limits can be stricter; model arguments cannot raise them.

## Host manifest and ordering

A future host manifest must bind contract version, initial packet byte hash, exact original target set, item/part identity, canonical paragraph order, allowed neighboring IDs, raw UTF-8 hashes, paragraph text, source page/leaf, and boundary evidence/version/hash. It must distinguish verified adjacency from missing order. A page break alone is not a stop; adjacency across pages needs established ordering. Never sort lexical paragraph IDs or assume leaf adjacency establishes text continuity.

For each edge the host records turn, chamber, date/proceeding and embedded-document continuity as supported, stopped or unknown, with cited evidence and provenance. This is an explicit supplied policy assertion, not a model-discovered fact. Missing continuity is conservative unavailability. A separate turn/region identifier is not proof by itself. Do not equate T10's date region with a speaker turn.

Traverse outward from the anchor, stop before the first disallowed edge, then return complete paragraphs in canonical reading order. Never skip a blocked or missing paragraph to retrieve a more distant cue. A cue introducing the anchor's own supported turn may be included; a cue introducing another turn cannot be used to propagate that speaker. Intra-paragraph mixed turns or embedded-document boundaries require supported spans; otherwise refuse that paragraph. A whole paragraph that exceeds remaining text allowance is omitted, not silently truncated. No Unicode normalization or OCR repair occurs.

## Result schema and semantic checks

All objects forbid extra properties; all fields listed here are required. IDs are nonempty strings; hashes match the argument hash pattern; integers are nonnegative. This compact schema notation defines the proposed result envelope:

```text
ContextResult = {
  contract_version: const "neighbor-context-draft-v1",
  request_sha256: SHA256(canonical validated arguments),
  packet_sha256: SHA256(initial packet bytes),
  manifest_sha256: SHA256(frozen host manifest bytes),
  status: enum [available, partial, unavailable, rejected],
  reason: enum [complete, boundary_stop, continuity_unknown, missing_source,
                order_unknown, text_limit, tool_limit, invalid_arguments,
                source_mismatch],
  paragraphs: Paragraph[],
  returned_codepoints: integer,
  remaining_tool_calls: integer,
  remaining_codepoints: integer,
  stop_evidence_ids: string[]
}
Paragraph = {
  source_paragraph_id: string, item_identifier: string,
  scan_leaf: integer, canonical_ordinal: integer,
  raw_text: string, raw_sha256: SHA256(raw_text UTF-8),
  start: const 0, end: Unicode length(raw_text),
  continuity_evidence_ids: string[]
}
```

`available/complete` returns exactly the requested count; `partial` returns at least one but fewer paragraphs with a stop reason. `unavailable` returns no paragraphs for a valid request lacking allowed evidence/resources; `rejected` returns no paragraphs for invalid arguments or an identity/hash failure. Invalid JSON is recorded as exact raw arguments rather than assigned a fictitious validated request hash; its rejected envelope has `request_sha256: null`. Other result hashes remain host-known. Source mismatch halts the work item for review; it must not trigger a different source search. A budget stop terminates further requests. A boundary stop cites supplied boundary evidence; absent evidence uses `continuity_unknown` and may have no evidence IDs. Returned length is the sum of raw-text lengths; the serialized envelope has a separate host byte cap, provisionally 64 KiB. Oversize metadata fails closed as unavailable/text_limit with no text.

Host checks bind every paragraph's identity, bytes, order, allowlist and continuity evidence to the frozen manifest, and verify counters. Generic schema validation cannot prove these properties. Return content is untrusted historical evidence, never instructions to the worker. No hidden neighboring text may be injected after a tool result is recorded.

## Three synthetic examples

| Scenario | Frozen setup / request | Expected result and permitted conclusion |
| --- | --- | --- |
| Supported context | Target P3 starts mid-speech; P2 contains a speaker cue. Host supplies supported same-turn edge P2→P3 even across a page. Request preceding 1 from P3. | available/complete, exact P2 text/hash/location and continuity evidence. A proposal may cite its cue only after existing role validation; retrieval alone does not establish identity. |
| Boundary stop | Target P3 follows a new House opening; P2 is Senate. Request preceding 1 from P3. | unavailable/boundary_stop, empty paragraphs and boundary evidence. No Senate speaker or date carries into P3. If a two-paragraph request finds one safe neighbor before the boundary, return partial with only that neighbor. |
| Unavailable | Target P3 has no frozen previous paragraph or no supported edge. Request preceding 1. | unavailable/missing_source or continuity_unknown, empty paragraphs. Return ordinary unknown/needs_review for unsupported attribution; no name, date or continuation is invented. |

These examples assert contract behavior only. They are not executed tests, inspected scans or human judgments.

## Existing-worker integration and budget ownership

Keep the current prepared request → output → host validation worker unchanged. A separately reviewed optional worker would journal its initial packet and manifest before any request, record raw tool arguments, exact results and counters before continuation, then bind the final augmented packet to a new hash. Existing packet aliases cannot be overwritten. Source-bound new paragraph/cue aliases require deterministic host construction and explicit validation; role-v2 cannot cite arbitrary new IDs, and date validation must still enforce forward-only scoped evidence. Keep initial target coverage fixed even when context is added: existing date packets treat every paragraph as a target, so a context-only adapter needs separately reviewed design before implementation. No silent enlargement of target sets or accepted vocabularies.

Final unresolved role output uses existing `unknown` with null candidate or `needs_review` under the unchanged controlled vocabulary; dates use the existing no-supported-date representation with explicit unknowns. Tool failure is recorded alongside, not embedded as a new historical role/date. A software-valid proposal remains a proposal; it cannot declare human acceptance.

The host owns total provider calls, elapsed time, input/output tokens, cumulative tool text/bytes, lock and retry policy. A tool slot is not a provider-call budget. T25 must freeze finite numerical live allowances and reconcile historical cumulative usage before T26 can run; this draft approves none. No automatic retry. Unknown usage/elapsed time blocks further dispatch under existing journal semantics. Compatible replay uses saved exact results without another provider request; ambiguous attempts block dispatch. Framework memory/traces are not the authoritative attempt record. T24 must prove this integration in fresh fake-provider processes before any live readiness claim.

## Completion and limits

T19 delivers the bounded design only. No runnable tool, wrapper, framework selection, dependency change, backend compatibility, source accuracy, historical quality improvement or parent-stage completion follows. T20 remains independent; T21 needs both outputs. T22 requires the actual human-run independent GPT-6 verdict before adoption. Roster/scan tools and supervisors remain deferred. P0 and all human decisions remain open as recorded in the master.

Validation: required elevated repository Markdown formatting plus explicit formatting of this ignored artifact passed; `git diff --check` passed. The argument-schema JSON parses, all five local reference links resolve, and master task/parent/next-task states were checked. No code gate rerun for this documentation-only unit; the last recorded code gate remains T13 (511 tests). Result notation is a draft schema specification, not an executable validator or backend-accepted schema.
