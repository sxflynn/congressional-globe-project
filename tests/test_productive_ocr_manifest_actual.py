"""Manifest part limits retain the exact installed model identity."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import time
from pathlib import Path

import pytest

from congressional_globe.productive_ocr_local import (
    MAX_MODEL_PARTS,
    PINNED_MODEL_MANIFEST_SHA256,
    PINNED_MODEL_PARTS,
    _parse_model_manifest,
)

ACTUAL_MANIFEST = (
    Path(__file__).parents[1]
    / "artifacts/ocr-live-readiness-20261028-01/installed-model-manifest.json"
)


def test_exact_saved_manifest_uses_pinned_layer_bound() -> None:
    raw = ACTUAL_MANIFEST.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == PINNED_MODEL_MANIFEST_SHA256
    manifest = _parse_model_manifest(raw)
    assert len(manifest.layers) == PINNED_MODEL_PARTS == 1209


def test_modified_oversized_manifest_does_not_inherit_pinned_bound() -> None:
    document = json.loads(ACTUAL_MANIFEST.read_bytes())
    document["layers"].append(document["layers"][-1])
    changed = json.dumps(document, separators=(",", ":")).encode()
    assert hashlib.sha256(changed).hexdigest() != PINNED_MODEL_MANIFEST_SHA256
    with pytest.raises(ValueError, match="too many layers"):
        _parse_model_manifest(changed)


def test_other_manifest_keeps_original_part_limit() -> None:
    assert MAX_MODEL_PARTS == 64
    document = json.loads(ACTUAL_MANIFEST.read_bytes())
    document["layers"] = document["layers"][:MAX_MODEL_PARTS]
    ordinary = json.dumps(document, separators=(",", ":")).encode()
    assert len(_parse_model_manifest(ordinary).layers) == MAX_MODEL_PARTS


def test_slow_resource_hash_deadline_prevents_local_start(tmp_path, monkeypatch) -> None:
    from congressional_globe import productive_ocr_local as local_module

    spec = importlib.util.spec_from_file_location(
        "productive_ocr_local_fixtures", Path(__file__).with_name("test_productive_ocr_local.py")
    )
    assert spec is not None and spec.loader is not None
    fixtures = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixtures)
    monkeypatch.setattr(fixtures, "_port", lambda: 54321)
    plan, spool = fixtures._fixture(tmp_path)
    plan = plan.model_copy(update={"session_deadline_epoch": time.time() + 1.2})
    original_hash = local_module._sha_file

    def slow_hash(path: Path, deadline: float | None = None) -> str:
        assert deadline is not None
        while time.monotonic() < deadline:
            time.sleep(0.01)
        return original_hash(path, deadline)

    monkeypatch.setattr(local_module, "_sha_file", slow_hash)
    with pytest.raises(TimeoutError, match="deadline expired"):
        local_module.OwnedLocalClient(plan, spool).start(fixtures._body())
    assert not spool.exists()
