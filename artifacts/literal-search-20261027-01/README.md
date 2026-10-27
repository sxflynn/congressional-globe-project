# Search that preserves the original six paragraphs

T33, 2026-10-27. The human explicitly instructed “ok. build it” after the prepared T42 proposal and its adoption gate were explained. That direct instruction authorizes this bounded implementation; it is not an invented independent review verdict or permission for model requests.

A researcher can now find `McPherson` in the existing House-opening OCR, read the full original paragraph, and obtain its exact source paragraph, fingerprint and character positions. One preceding/following paragraph is available within the same declared region. House context stops before the preceding Senate lines. These region assignments were supplied in the frozen input; search does not discover historical boundaries independently.

The [library](../../src/congressional_globe/literal_search.py) loads only the exact six-paragraph collection frozen by T42. It checks its pinned SHA-256 fingerprint before parsing, validates each raw paragraph fingerprint, and rejects reordered, edited or substituted bytes. A caller-supplied replacement manifest cannot change that pinned identity. Input reads stop at16,001bytes and reject files above16,000bytes. Queries are1–256 Unicode codepoints with non-whitespace content; returned occurrence limits are1–20. Unsupported filters fail explicitly.

Matches are case-sensitive exact raw substrings, including overlaps, in paragraph/position order. Results report total occurrences, returned count and truncation; there is no pagination. Citations include item, scan leaf, paragraph ID, raw fingerprint and half-open Unicode positions. Context is marked separately with its own citation and full-paragraph positions. Raw text is preserved. Proposed Internet Archive page URLs are explicitly **unverified**: this unit has not confirmed leaf-to-page mapping. Item/leaf/paragraph/position citations remain available; a formatted URL is not proof of that mapping.

## Use from Python

```python
from pathlib import Path
from congressional_globe.literal_search import load_collection

collection = load_collection(
    Path("artifacts/search-slice-design-20261027-01/paragraphs.json")
)
result = collection.search("McPherson", limit=5)
print(result.model_dump_json(indent=2))
```

This uses only the committed fixture and installed project code; no other local source corpus, manifest, database, model or network is needed. [Saved actual outputs](examples.json) show `McPherson`, `Senate adjourned`, `House` with truncation, and the contrast between no exact match for `Constitution` and a match for the original `Consti- tution`. That contrast exposes an OCR search limitation; it does not silently repair the source or establish a cleanup policy.

## Checks and remaining scope

Thirty-four focused tests check the ten frozen queries and their exact positions, citations, stable counts/truncation, declared-region and packet-end context, invalid query/limit/filter handling, changed hash/order/region/duplicate input rejection, read bounds, portable fixture-only loading, immutability and overlapping/Unicode positions. [Full gate output](gate.log) records the required formatting, lint, type, complexity and suite results. [Bounded Luna review](review.json) found no concrete issue; that is code feedback, not a historical grade.

The result is one working literal-search library over six paragraphs, not an all-corpus search service. There are no date/speaker/topic filters, OCR normalization, semantic search, new command/UI, accepted metadata or human relevance grades. The T41 date proposal and its explicit/implicit caveat remain separate. M4.1/M4 are PARTIAL; M6.1/M6 still require the portable pilot and independent consumer proof, and P0 stays open. The next raw/clean comparison requires its own finite matched-input scope; this implementation does not rerun prior experiments.
