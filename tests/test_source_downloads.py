from __future__ import annotations

import argparse
import hashlib
import io
from pathlib import Path

import pytest

from congressional_globe import source_downloads as sources
from congressional_globe.inventory import expected_paths, resolve_source_path


def record(data: bytes) -> sources.SourceDownload:
    return sources.SourceDownload(
        item="congressionalg7391unit",
        derivative="page_numbers.json",
        size_bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        archive_sha1=hashlib.sha1(data).hexdigest(),
    )


def test_manifest_has_exactly_the_fifteen_pinned_files():
    rows = sources.load_manifest()
    assert len(rows) == 15
    assert sum(r.size_bytes for r in rows) == 2_550_914_693
    assert rows[0].url.startswith("https://archive.org/download/congressionalg7391unit/")


def test_restore_streams_verifies_and_reuses_without_network(tmp_path, monkeypatch):
    data = b'{"pages": []}'
    row = record(data)
    calls = []

    def fetch(url, timeout):
        calls.append((url, timeout))
        return io.BytesIO(data)

    monkeypatch.setattr(sources, "urlopen", fetch)
    assert sources.restore_file(tmp_path, row)["status"] == "downloaded_verified"
    assert sources.restore_file(tmp_path, row)["status"] == "verified_existing"
    assert calls == [(row.url, 60)]
    assert (tmp_path / row.filename).read_bytes() == data
    assert not list(tmp_path.glob("*.partial"))


def test_existing_mismatch_is_preserved_without_network(tmp_path, monkeypatch):
    row = record(b"correct")
    path = tmp_path / row.filename
    path.write_bytes(b"damaged")
    monkeypatch.setattr(sources, "urlopen", lambda *a, **kw: pytest.fail("unexpected network"))
    with pytest.raises(ValueError, match="mismatch"):
        sources.restore_file(tmp_path, row)
    assert path.read_bytes() == b"damaged"


@pytest.mark.parametrize("reply", [b"short", b"wrong bytes", b"too many bytes received"])
def test_invalid_remote_bytes_never_become_source(tmp_path, monkeypatch, reply):
    row = record(b"right bytes")
    monkeypatch.setattr(sources, "urlopen", lambda *a, **kw: io.BytesIO(reply))
    with pytest.raises(ValueError):
        sources.restore_file(tmp_path, row)
    assert not (tmp_path / row.filename).exists()
    assert (tmp_path / (row.filename + ".partial")).exists()


def test_interrupted_transfer_preserves_partial_and_refuses_automatic_retry(tmp_path, monkeypatch):
    row = record(b"right bytes")

    def unavailable(*args, **kwargs):
        raise TimeoutError("invented network failure")

    monkeypatch.setattr(sources, "urlopen", unavailable)
    with pytest.raises(TimeoutError):
        sources.restore_file(tmp_path, row)
    with pytest.raises(FileExistsError):
        sources.restore_file(tmp_path, row)
    assert not (tmp_path / row.filename).exists()


def test_legacy_path_falls_back_only_for_known_missing_sources(tmp_path):
    row = record(b"bytes")
    directory = tmp_path / "downloads"
    directory.mkdir()
    target = directory / row.filename
    target.write_bytes(b"bytes")
    assert expected_paths(tmp_path, row.item)[row.derivative] == target
    assert expected_paths(directory, row.item)[row.derivative] == target
    legacy = tmp_path / row.filename
    legacy.write_bytes(b"legacy")
    assert resolve_source_path(legacy) == legacy
    assert resolve_source_path(tmp_path / "other.json") == tmp_path / "other.json"


def test_verify_command_does_not_download(tmp_path, monkeypatch, capsys):
    row = record(b"bytes")
    (tmp_path / row.filename).write_bytes(b"bytes")
    monkeypatch.setattr(sources, "load_manifest", lambda: [row])
    monkeypatch.setattr(sources, "urlopen", lambda *a, **kw: pytest.fail("unexpected network"))
    sources.run_sources(argparse.Namespace(sources_action="verify", directory=tmp_path), Path("."))
    assert '"status": "verified"' in capsys.readouterr().out


def test_relocated_absolute_source_is_resolved_but_hash_is_still_required(tmp_path, monkeypatch):
    from congressional_globe import inventory
    from congressional_globe.productive_ocr_measurement_inputs import _read_verified

    checkout = tmp_path / "checkout"
    directory = checkout / "downloads"
    directory.mkdir(parents=True)
    monkeypatch.setattr(
        inventory, "__file__", str(checkout / "src/congressional_globe/inventory.py")
    )
    row = record(b"known source bytes")
    (directory / row.filename).write_bytes(b"known source bytes")
    old = tmp_path / "old-checkout" / row.filename
    assert resolve_source_path(old, relocated=True) == directory / row.filename
    assert expected_paths(old.parent, row.item)[row.derivative] == old
    assert _read_verified(old, row.sha256) == b"known source bytes"
    with pytest.raises(ValueError, match="registered resource changed"):
        _read_verified(old, "0" * 64)
