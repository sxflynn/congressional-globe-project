# A bounded first text-search slice

T42 prepares T33 under M4.1/M6.1. A researcher should be able to find Edward McPherson in the existing House-opening passage, read the original paragraph and cite its exact source. This document freezes that small implementation target. It does not ship search or establish research quality.

## Frozen inputs and coverage

Use only the six ordered raw paragraphs P1–P6 from T41's source-linked export, copied exactly into [paragraphs.json](paragraphs.json). [The manifest](manifest.json) binds the export and each paragraph to its fingerprint (SHA-256 hash). Input identity is `house-opening-december-4-1865-v1`, Internet Archive item `congressionalg7391unit`, scan leaf117. The original item, leaf, paragraph ID, raw text, fingerprint and declared region must survive export. P1–P2 are Senate close; P3–P6 are House opening. These regions were supplied in preparation; they were not independently discovered.

This is six paragraphs on one scan leaf, not all of the page or Congress. No corpus parsing, source-image fetch, index build, embeddings, provider calls, cleaned text or new historical labels are needed. The saved T41 date proposal remains available separately; it is not an approved date filter. The explicit-versus-implicit caveat remains unresolved.

## Proposed smallest implementation

Implement a pure Python library function over a validated frozen paragraph collection; no new command, service, database, UI, scheduler or replacement runner. For this first slice, matching means a case-sensitive exact substring inside one raw paragraph. It does not remove punctuation, normalize spaces, join broken words or search across paragraph edges. Empty or whitespace-only queries are rejected. Limit the query to256 Unicode codepoints, collection to these6paragraphs and returned results to1–20 matching occurrences. No new dependency is needed.

Count overlapping occurrences: advance the next search start by one Unicode codepoint after each match. Return only the first N occurrences in frozen paragraph order, then increasing position; N is the requested limit. There is no pagination, offset or cursor in this first slice. Include its half-open Unicode codepoint positions, exact matched substring (which need not be a whole word), full matching raw paragraph and citation fields: item identifier, scan leaf, source paragraph ID, raw fingerprint and exact positions. The returned raw substring must equal the query. Include a primary-source page link using the item's Internet Archive `page/n117` reference, with the exact paragraph ID and positions beside it; the URL alone is not a paragraph citation. Before URL acceptance, verify the source's scan-leaf-to-Internet-Archive-page mapping for this one item/leaf. Until that check exists, mark the page URL unverified and retain the item/leaf/paragraph/position citation; formatting-only URL checks do not prove the page mapping. This preparation has not opened the page.

Return at most one preceding and one following paragraph within the same declared region. Mark these as context, not matches, and give their own citations. For P3, P2 must not become House context. At packet ends or region changes, state context unavailable within this slice; never invent an adjacent paragraph. Never label a context paragraph a matching hit unless it independently matches.

The collection fingerprint is SHA-256 of the exact UTF-8 bytes of paragraphs.json, including record order and all fields, compared with manifest.json collection_sha256 before parsing. The manifest value is the pinned trusted value supplied with this release; do not recompute it from changed inputs and silently accept a replacement manifest. No canonical reserialization or normalization is performed. Every response states the collection fingerprint, exact coverage, match mode, total occurrence count, returned count and whether the limit omitted occurrences. A no-match response says only “No exact match in these six paragraphs”; it must not imply the person or subject is absent from Congress. Invalid input fingerprints, duplicate paragraph IDs/aliases, changed paragraph order or region assignments must fail validation before search. Freeze order and all record fields through the collection fingerprint, in addition to checking raw hashes.

Do not offer date/speaker/topic filters in this slice. Supplying unsupported filter parameters must fail explicitly rather than silently ignoring them. A later metadata-aware task must define unknown inclusion, compatible paragraph scope, filter semantics and proposal provenance before filters can ship.

## Concrete acceptance cases

[query-expectations.json](query-expectations.json) records ten literal queries and every expected raw occurrence/position. These are mechanically enumerated substring expectations from saved OCR, not human relevance judgments or image-certified transcriptions.

- `McPherson` finds P3; `mcpherson` has no case-sensitive match.
- `December 4, 1865` and `1865` find P3 with exact matching positions.
- `Senate adjourned` finds P2 and may show P1 context; P3 is excluded at the region edge.
- `House` finds multiple occurrences in P3/P4; limits must count occurrences, expose truncation and preserve stable ordering.
- `Freedmen` has no match within declared coverage.
- `Constitution` has no exact match because OCR has `Consti- tution`; that exact broken spelling finds P3. This deliberately exposes the first slice's limitation and provides a future normalization example without silently repairing text.
- `adjourned. HOUSE` has no match across the paragraph/region edge.

Implementation checks additionally require tampered hash/order/region rejection, duplicate-ID rejection, invalid query/limit rejection, unsupported-filter rejection, citation round trips, region-limited neighbors, packet-end context unavailability and portable loading from only the committed fixture. Focused tests plus the required full code gate must pass before implementation is DONE. No relevance percentage or general search-quality claim follows from these checks.

## Existing code and adoption boundary

A bounded inventory found no tracked search/retrieval module or tests in `src/` and `tests/`; the evidence index describes local lexical/vector/fusion prototypes but does not identify an installed lexical entry point. No prototype was rerun or adopted, and no broad scratch/archive search was undertaken. Implementation should first inspect a specifically identified existing helper if one is supplied, reuse it only if it meets these bounds, otherwise keep the function small and dependency-free.

The repository's [engineering rule](../../docs/reference/engineering.md#automation-and-ergonomics-review) requires an independent human-run GPT-6 verdict before adopting new scripts, commands or workflows. The library target above is a prepared proposal, not an adopted workflow. Before implementation, obtain that verdict on this concrete target and its risks, or direct human authorization overriding that gate. A bounded Luna preparation review is additional engineering feedback, not that verdict. No reviewer or model run is automatically launched to satisfy the human-run gate.

T33 remains unimplemented pending that decision. M4.1/M4 remain PLANNED and M6.1/M6 remain PLANNED. P0 stays open; this raw-only slice supplies no raw-versus-clean comparison or cleanup policy.
