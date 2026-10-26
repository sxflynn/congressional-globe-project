# T10: executable scoped-date contract

2026-10-26, Codex GPT-6. Implements the offline contract portion of M1.3, using exactly the two frozen T4 source cases. M1 remains PARTIAL. No inference, network/image fetch, human label, accepted ledger or corpus edit. The original frozen draft, source preparation and role-v2 protocol are unchanged.

## Research behavior

Dates carry point/range endpoints, day/month/year precision, explicit/implicit/none kind, proceeding/mentioned/unknown context, method, proposal/review status, alternatives and unknowns. Every paragraph in a bounded input must have a supported date proposal or explicit unknown. A source-mapped export retains original paragraph text, hash, item, leaf, paragraph ID and half-open Unicode evidence offsets.

The source-bound fixtures preserve `t2-4-053` text exactly, with paragraph offsets mapped through its frozen alias records. Its window hash is verified as a window hash; new paragraph hashes are calculated from the exact paragraph slices, not misrepresented as historical paragraph hashes. The ordinary verb “may” supplies no date. All twenty paragraphs remain date-unknown. Regions are conservatively local to each paragraph; this fixture authorizes no continuation.

The House-opening case preserves all six frozen paragraphs and their original hashes. The exact P3 quote “Monday, December 4, 1865” supports the proposed day1865-12-04 in P3–P6. Prior Senate P1/P2 remain unknown. The host-declared Senate/House boundary and a separate forward-only check both prevent backward propagation. Continuation after P6 is unsupported. Role outputs/identity are never inferred from dates, and role-v2 host semantics remain unchanged.

## Implementation and limits

[Module](../../src/congressional_globe/scoped_dates.py) implements strict Pydantic v2 inputs/results, JSON Schema, calendar/precision/range checks, source-hash/quote/offset validation, contiguous target scope, boundary stops, full paragraph coverage, independent evidence for alternatives and source-mapped exports. The host adds source/semantic checks beyond generic JSON Schema. Supplied regions are host assertions tied to the frozen preparation SHA-256, not a new automatic boundary detector or proof of source truth. Source identity bindings are replayed from the frozen cases; no fresh full-source or scan audit was performed.

The bounded lexical support check recognizes English month/day/year, month/year and explicit four-digit years. Unsupported spellings, OCR-damaged dates, abbreviations, relative expressions and missing years must remain unknown/reviewable; catalog context cannot fill missing components. Range endpoints must each be evidenced. This is conservative contract engineering, not calibrated extraction accuracy or a production date filter. A model's fluent proposal cannot mark itself accepted or human-reviewed.

[Fixtures and mapped outputs](fixtures.json) are portable and trace to the exact preparation SHA-256. [Schema](schema.json) is generated from the implemented types. The preparation expectations and these hand-authored engineering proposals remain AI-provisional, not human gold or image-certified history. No learned quality threshold is claimed.

## Transport checks and blockers

The existing role provider specializer previously raised `KeyError: speaker_roles` for date schemas. It now recognizes the date contract, validates the input packet, specializes paragraph-reference enums without mutating the generic schema, and uses a date-specific instruction instead of a person-cue instruction. Existing role-v1 behavior and role-v2 host validation are preserved. Fake-client tests exercise the exact existing OpenAI Responses and Ollama chat construction and parse their synthetic result through the date host validator. These tests make zero service calls.

**Live backend compatibility remains BLOCKED/unproved.** Fake-client serialization and Draft2020-12 validation do not establish acceptance by a remote constrained-schema engine. Ollama's existing adapter sends `json_object` with schema instructions; it does not enforce this schema as a native grammar. OpenAI server-side acceptance of every generated constraint is untested. No backend compatibility or launch readiness is claimed, and no new inference is authorized. A later named bounded task must establish the intended backend/version and actual supported constraints before date inference, rather than treating these offline tests as a service certificate.

A separate existing incompatibility is reproduced: `specialize_schema(role_result_schema(), {})` raises `KeyError: properties` because the role-v2 schema uses `oneOf`/`allOf`, while the older role specializer expects direct item properties. It remains explicitly blocked for live role-v2 use; changing its semantics is outside this date unit. Date and role outputs were not combined into a new model protocol.

## Checks

Thirty-four new date tests cover the two exact cases, schema/host distinctions, frozen input/hash replay, ordinary-verb negative, forward/backward and chamber boundaries, local continuation, calendar/precision/range cases, conflicting alternatives, incomplete/overlapping targets, raw/evidence tampering, source-map export and fake-client request construction. Existing role-v2/provider tests also pass. [Validation manifest](validation.json) binds the files and records the separate transport limits. Full required gate output: [gate.log](gate.log).

The full gate passed: **450 tests**, Ruff format/lint, ty, complexity≤5 and required elevated Markdown formatting. All frozen input/schema/source-byte replay checks passed.
