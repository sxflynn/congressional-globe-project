from pathlib import Path

import pytest

from congressional_globe import productive_ocr_measurement_inputs as inputs


def test_loads_exact_s5_projection_offline() -> None:
    host, projection, registry = inputs.load_s5_inputs(Path.cwd())
    assert host["packet_sha256"] == inputs.HOST_SHA256
    assert projection.body_sha256 == inputs.REQUEST_SHA256
    assert set(registry.image_bytes) == {inputs.IMAGE_SHA256}
    assert host["payload"]["image"]["hocr_sha256"] in registry.files
    assert len(registry.files[host["payload"]["image"]["hocr_sha256"]]) > 300_000_000


def test_rejects_changed_saved_request(monkeypatch: pytest.MonkeyPatch) -> None:
    original = Path.read_bytes

    def changed(path: Path) -> bytes:
        content = original(path)
        if path.name == "request.json" and path.parent.name == "S5":
            return content + b" "
        return content

    monkeypatch.setattr(Path, "read_bytes", changed)
    with pytest.raises(ValueError, match="request body identity changed"):
        inputs.load_s5_inputs(Path.cwd())


def test_rejects_changed_registry_index_hash(monkeypatch: pytest.MonkeyPatch) -> None:
    original = inputs._json

    def changed(path: Path):
        value = original(path)
        if path.name == "registry-index.json":
            value["files"].pop("966c31d965de8d72080bd30c8e474e98a2061d3082bd8c0d7f89b10eb81436ff")
        return value

    monkeypatch.setattr(inputs, "_json", changed)
    with pytest.raises(ValueError, match="hOCR resource missing or changed"):
        inputs.load_s5_inputs(Path.cwd())
