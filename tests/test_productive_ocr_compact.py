"""Independent-reference round trips and adversarial offline codec inputs."""

import copy
import json
from pathlib import Path

import pytest

from congressional_globe.productive_ocr_compact import (
    MAX_SERIALIZED_BYTES,
    SIGNAL_COLUMNS,
    decode_provider,
    encode_provider,
)
from congressional_globe.productive_ocr_host import canonical_json, sha256_bytes


def _text(value):
    return canonical_json(value).decode()


def _original():
    return {
        "contract": "ocr-productive-repair-input-v2",
        "reply_contract": "ocr-productive-repair-reply-v2",
        "unit_id": "codec-fixture",
        "role": "productive_repair_and_self_check",
        "image_alias": "I1",
        "target_regions": [
            {"paragraph_alias": "P1", "crop_region": {"left": 0, "top": 0, "right": 4, "bottom": 4}}
        ],
        "context_regions": [],
        "paragraphs": [
            {
                "paragraph_alias": "P1",
                "role": "target",
                "raw_text": "By Mr. Exámple. \u2019",
                "static_text": "By Mr. Exámple. \u2019",
                "static_edits": [],
            }
        ],
        "diagnostics": {
            "status": "frozen",
            "detector_sha256": "a" * 64,
            "configuration_sha256": "b" * 64,
            "signals": [
                {
                    "signal_id": "S1",
                    "paragraph_alias": "P1",
                    "raw_start": 3,
                    "raw_end": 6,
                    "raw_quote": "Mr.",
                    "category": "other",
                    "flags": ["capitalized_candidate"],
                    "route_reason": "Synthetic reason.",
                }
            ],
            "negative_targets": [],
        },
        "saved_proposal": None,
    }


def _encoded(original=None):
    original = _original() if original is None else original
    source = _text(original)
    digest = sha256_bytes(source.encode())
    return source, digest, json.loads(encode_provider(source, digest))


def _set_path(data, path, value):
    for part in path[:-1]:
        data = data[part]
    data[path[-1]] = value


def _reject_change(path, value, original=None):
    source, digest, compact = _encoded(original)
    _set_path(compact, path, value)
    with pytest.raises(ValueError):
        decode_provider(_text(compact), source, digest)


@pytest.mark.parametrize("unit", ["S1", "S2", "S5", "D1", "D2"])
def test_five_frozen_providers_match_proposed_bytes_and_original_exactly(unit):
    root = Path("artifacts/study-input-assembly-20261029-01")
    meta = next(
        row for row in json.loads((root / "units.json").read_text()) if row["unit_id"] == unit
    )
    request = (root / unit / "request.json").read_bytes()
    assert sha256_bytes(request) == meta["request_sha256"]
    source = json.loads(request)["messages"][1]["content"]
    digest = sha256_bytes(source.encode())
    encoded = encode_provider(source, digest)
    proposed = Path("artifacts/study-capacity-screen-20261029-01") / unit / "proposed-user-v3.json"
    assert encoded == proposed.read_text()
    assert decode_provider(encoded, source, digest) == source


def test_empty_signals_have_empty_table_and_do_not_default_missing_fields():
    original = _original()
    original["diagnostics"]["signals"] = []
    original["diagnostics"]["status"] = "not_run"
    original["diagnostics"]["detector_sha256"] = None
    original["diagnostics"]["configuration_sha256"] = None
    source, digest, compact = _encoded(original)
    assert compact["diagnostics"]["signal_table"] == {
        "columns": [],
        "rows": [],
        "route_reasons": [],
    }
    assert decode_provider(_text(compact), source, digest) == source
    del compact["diagnostics"]["negative_targets"]
    with pytest.raises(ValueError):
        decode_provider(_text(compact), source, digest)


@pytest.mark.parametrize(
    "columns",
    [
        [*SIGNAL_COLUMNS, "extra"],
        list(SIGNAL_COLUMNS)[:-1],
        [SIGNAL_COLUMNS[1], *SIGNAL_COLUMNS[1:]],
        list(reversed(SIGNAL_COLUMNS)),
        [],
    ],
)
def test_noncanonical_extra_missing_duplicate_or_reordered_columns_are_rejected(columns):
    _reject_change(["diagnostics", "signal_table", "columns"], columns)


@pytest.mark.parametrize("index", [-1, 1, 128, True, False, 0.0, "0", None, {}, []])
def test_reason_indices_are_strict_in_range_integers(index):
    column = SIGNAL_COLUMNS.index("route_reason")
    _reject_change(["diagnostics", "signal_table", "rows", 0, column], index)


@pytest.mark.parametrize(
    "reasons",
    [
        [],
        ["Synthetic reason.", "Synthetic reason."],
        ["Synthetic reason.", "Unused reason."],
        ["Z", "A"],
        [""],
        [True],
        "Synthetic reason.",
    ],
)
def test_reason_dictionary_is_nonempty_strings_sorted_unique_and_fully_used(reasons):
    _reject_change(["diagnostics", "signal_table", "route_reasons"], reasons)


@pytest.mark.parametrize("change", ["short", "long", "object"])
def test_rows_have_exact_arity_and_array_shape(change):
    source, digest, compact = _encoded()
    rows = compact["diagnostics"]["signal_table"]["rows"]
    replacements = {"short": rows[0][:-1], "long": [*rows[0], "extra"], "object": {}}
    rows[0] = replacements[change]
    with pytest.raises(ValueError):
        decode_provider(_text(compact), source, digest)


@pytest.mark.parametrize(
    ("column", "value"),
    [
        ("raw_start", True),
        ("raw_end", 1.5),
        ("raw_start", -1),
        ("category", "invented"),
        ("flags", "flag"),
        ("flags", [True]),
        ("paragraph_alias", "P33"),
        ("raw_quote", " "),
        ("signal_id", ""),
    ],
)
def test_ordinary_row_cells_use_existing_strict_signal_types(column, value):
    _reject_change(["diagnostics", "signal_table", "rows", 0, SIGNAL_COLUMNS.index(column)], value)


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (["contract"], "ocr-productive-repair-input-v2"),
        (["extra"], "silently discarded?"),
        (["diagnostics", "extra"], "silently discarded?"),
        (["diagnostics", "signal_table", "extra"], "silently discarded?"),
        (["diagnostics", "signals"], []),
        (["paragraphs", 0, "extra"], "silently discarded?"),
    ],
)
def test_unknown_fields_and_wrong_contract_are_rejected(path, value):
    _reject_change(path, value)


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (["unit_id"], "another-unit"),
        (["role"], "audit_saved_proposal"),
        (["paragraphs", 0, "raw_text"], "Changed source"),
        (["paragraphs", 0, "static_text"], "Changed derived text"),
        (["paragraphs", 0, "role"], "context"),
        (["target_regions", 0, "crop_region", "right"], 5),
        (["diagnostics", "detector_sha256"], "c" * 64),
        (["diagnostics", "negative_targets"], ["P1"]),
        (["diagnostics", "signal_table", "rows"], []),
        (["paragraphs"], []),
    ],
)
def test_coherent_source_scope_and_evidence_changes_cannot_match_independent_reference(path, value):
    _reject_change(path, value)


def test_changed_original_is_rejected_against_independent_hash():
    source, digest, compact = _encoded()
    changed = json.loads(source)
    changed["paragraphs"][0]["raw_text"] = "Another reference"
    with pytest.raises(ValueError, match="independently held"):
        encode_provider(_text(changed), digest)
    with pytest.raises(ValueError, match="independently held"):
        decode_provider(_text(compact), _text(changed), digest)


def test_missing_reference_and_embedded_self_hash_do_not_authorize_decode():
    source, digest, compact = _encoded()
    with pytest.raises(ValueError, match="independently held"):
        decode_provider(_text(compact), source, "0" * 64)
    compact["source_sha256"] = digest
    with pytest.raises(ValueError):
        decode_provider(_text(compact), source, digest)


def test_unicode_order_context_and_saved_audit_bytes_are_not_normalized():
    original = _original()
    original["role"] = "audit_saved_proposal"
    original["context_regions"] = [
        {"paragraph_alias": "P2", "crop_region": {"left": 4, "top": 0, "right": 8, "bottom": 4}}
    ]
    context = copy.deepcopy(original["paragraphs"][0])
    context.update(paragraph_alias="P2", role="context", raw_text="", static_text="")
    original["paragraphs"].append(context)
    raw = original["paragraphs"][0]["raw_text"]
    original["saved_proposal"] = {
        "record_sha256": "c" * 64,
        "prior_request_sha256": "d" * 64,
        "prior_raw_reply_sha256": "e" * 64,
        "review_state": "unreviewed_model_proposal",
        "paragraphs": [
            {
                "paragraph_alias": "P1",
                "text": raw,
                "sha256": sha256_bytes(raw.encode()),
                "raw_edits": [],
            }
        ],
    }
    source, digest, compact = _encoded(original)
    assert decode_provider(_text(compact), source, digest) == source
    assert "Exámple" in source and "Exámple" not in source
    _reject_change(["saved_proposal", "prior_raw_reply_sha256"], "f" * 64, original)
    _reject_change(["saved_proposal", "paragraphs", 0, "text"], "Changed audit", original)
    _reject_change(["context_regions", 0, "crop_region", "right"], 9, original)


def test_duplicate_top_and_nested_json_keys_are_rejected_even_if_last_value_matches():
    source, digest, compact = _encoded()
    encoded = _text(compact)
    for field, value in [("unit_id", '"codec-fixture"'), ("right", "4")]:
        duplicate = encoded.replace(f'"{field}":{value}', f'"{field}":{value},"{field}":{value}', 1)
        assert duplicate != encoded
        with pytest.raises(ValueError, match="duplicate JSON"):
            decode_provider(duplicate, source, digest)
    duplicate_original = source.replace('"unit_id":', '"unit_id":"discarded","unit_id":')
    with pytest.raises(ValueError, match="duplicate JSON"):
        encode_provider(duplicate_original, digest)


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
def test_nonfinite_json_is_rejected_before_shape_validation(constant):
    source, digest, _compact = _encoded()
    with pytest.raises(ValueError, match="non-finite"):
        decode_provider('{"extra":' + constant + "}", source, digest)


def test_size_depth_and_schema_resource_overflows_are_rejected():
    source, digest, compact = _encoded()
    with pytest.raises(ValueError, match="byte limit"):
        encode_provider(" " * (MAX_SERIALIZED_BYTES + 1), digest)
    with pytest.raises(ValueError, match="byte limit"):
        decode_provider("é" * (MAX_SERIALIZED_BYTES // 2 + 1), source, digest)
    with pytest.raises(ValueError, match="nesting"):
        decode_provider("[" * 34 + "0" + "]" * 34, source, digest)
    rows = compact["diagnostics"]["signal_table"]["rows"]
    _reject_change(["diagnostics", "signal_table", "rows"], rows * 129)
    _reject_change(["paragraphs"], _original()["paragraphs"] * 33)
    _reject_change(["target_regions"], _original()["target_regions"] * 33)
    _reject_change(["paragraphs", 0, "raw_text"], "x" * 6001)


@pytest.mark.parametrize(("role", "length"), [("target", 3001), ("context", 1001)])
def test_independently_hashed_reference_cannot_raise_aggregate_source_limits(role, length):
    original = _original()
    row = original["paragraphs"][0]
    row.update(role=role, raw_text="x" * length, static_text="x" * length)
    original["paragraphs"] = [row, dict(row, paragraph_alias="P2")]
    text = _text(original)
    with pytest.raises(ValueError, match="aggregate source text"):
        encode_provider(text, sha256_bytes(text.encode()))


def test_coherent_table_omission_and_signal_mutation_fail_independent_binding():
    source, digest, compact = _encoded()
    compact["diagnostics"]["signal_table"] = {"columns": [], "rows": [], "route_reasons": []}
    with pytest.raises(ValueError, match="independently bound original"):
        decode_provider(_text(compact), source, digest)
    source, digest, compact = _encoded()
    compact["diagnostics"]["signal_table"]["rows"][0][SIGNAL_COLUMNS.index("raw_quote")] = "Ms."
    with pytest.raises(ValueError, match="independently bound original"):
        decode_provider(_text(compact), source, digest)
