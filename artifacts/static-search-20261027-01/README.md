# Find joined words while citing unchanged raw OCR

T44 extends the existing T33 search library over only the six frozen T43 raw/static pairs. A researcher can now search `Constitution` in the saved deterministic static text and inspect the original supporting OCR `Consti- tution`. The displayed spelling and the original quote are explicitly different fields. No new AI cleanup, model request, source fetch or canonical correction was made.

The raw library remains unchanged. The new [static library](../../src/congressional_globe/static_search.py) requires the exact paired-input byte fingerprint frozen by T43; it validates raw/static paragraph hashes, edit order/nonoverlap, exact expected raw slices and deterministic replay. It does not accept a caller's changed manifest as a new identity. Only P3 has edits: the two existing word joins. Collection reads, query lengths and occurrence limits retain the existing bounds.

## What a result means

Each result names the saved-static layer and collection fingerprint. A hit includes the full static paragraph, static fingerprint, exact matched static substring and static Unicode positions, plus the unchanged raw paragraph, raw supporting substring, raw fingerprint and raw citation positions. All intervals are half-open Unicode codepoint positions. Unchanged characters map one-to-one; characters supplied by a saved replacement map to its whole raw supporting interval. A match crossing edits uses the contiguous raw envelope. `exact_copy` versus `includes_saved_edit` makes the distinction explicit, including partial matches within a joined word.

For example, `Constitution` matches static positions89–101 but cites raw positions89–103 containing `Consti- tution`. `McPherson` remains an exact-copy match; its static position shifts four characters earlier because the two preceding joins each remove two characters. Reusing static positions as raw citation positions would point at the wrong words, so the library returns both separately.

Neighbor context stays raw and separately marked; the declared Senate/House boundary and packet edges still stop it. Matching is case-sensitive, overlapping and first-N, with total/returned counts and truncation. No-match wording states only the six-paragraph static coverage. The proposed page URL remains explicitly **unverified**; item/leaf/paragraph/hash/position citations are retained, and no page-link mapping or printed-word accuracy is certified here.

## Use from Python

```python
from pathlib import Path
from congressional_globe.static_search import load_static_collection

collection = load_static_collection(
    Path("artifacts/raw-clean-readiness-20261027-01/pairs.json")
)
result = collection.search("Constitution", limit=5)
print(result.model_dump_json(indent=2))
```

Only the committed pairs and project library are needed. [Saved actual raw/static outputs](examples.json) include joined words, later unchanged words, a match crossing an edit, and Senate context. The12frozen query outcomes from T43 now run through the explicit static path with raw support rather than only a scratch substring calculation. `Constitution` is0raw/1static; `members` is2raw/3static. These are mechanical matching outcomes, not relevance or cleanup-quality grades.

## Evidence and limits

Thirty added focused cases cover12fixed query outcomes; raw citation round trips; partial/cross-edit support; coordinate shifts after edits; region/packet context; truncation; raw/static identity separation; changed order/region/duplicate/hash/text rejection; malformed edits and replay; unsupported filters; fixture-only loading; read limits and Unicode coordinates. [Full gate output](gate.log) records all required project checks. Its exact terminal output is preserved in [a compressed archive](gate.raw.log.gz); the readable log removes terminal color and trailing spaces. [Validation fingerprints](validation.json) bind the code, fixture, examples and gate. [Bounded Luna review](review.json) is software feedback, not human historical approval.

No provider time/tokens were added. Offline effort, human review time and hardware/energy costs remain unmeasured. The static edits are prior work, not free new cleanup. This implements a bounded raw/static retrieval comparison path only. There is no compatible AI-clean arm in the named T43 inventory, no representative relevance benchmark, accepted date/speaker filters, semantic search, reading/TTS/audio result, annotation/answer comparison or P0 policy decision. M4.1/M4 and M5.2/M5 remain PARTIAL; portable pilot acceptance remains ahead.
