"""Fixed three-repeat original S5/S1/S2 observations under small-sample autonomy."""

import json
import time
from pathlib import Path
from typing import Literal

from pydantic import Field

from congressional_globe.bracket_cues import Contract
from congressional_globe.productive_ocr_host import sha256_bytes
from congressional_globe.productive_ocr_local import read_spool
from congressional_globe.scan_models import Sha256

PACKAGE = Path("artifacts/s5-scoped-consistency-20261030-01")
APPROVAL_SHA = "90818598931f4735d17e305856363edbfe82a8d93fa44a7c665e10b8b8b1dae0"
BODY_SHA = "025a19416e512063dd1c397da962d5d7c701d2ec60dc66b404fc8cf3d9fddb1b"
PROFILES = tuple(f"productive-ocr-s5-scoped-repeat-{i}-v4" for i in range(1, 4))
S1_PACKAGE = Path("artifacts/s1-consistency-20261031-01")
S1_APPROVAL_SHA = "b8e9120dbdbb0a0a4188ef87b7eca1ee3d84f07ff674d038ab25255c9157b277"
S1_BODY_SHA = "338d0cf1be8d22ae6b5bad6d90a3f274229e3472f1c38d96cc6ea16a289ebde7"
S1_PROFILES = tuple(f"productive-ocr-s1-scoped-repeat-{i}-v4" for i in range(1, 4))
S2_PACKAGE = Path("artifacts/s2-consistency-20261102-01")
S2_APPROVAL_SHA = "8ac38514f4ca1e4d7043f5b4461bee006c6334ac1907b562b5acc7f4864b4723"
S2_BODY_SHA = "df2829ff7b7bb26ca98dc847237d78424b7f9fe148d58516d7f9393fc7d495ac"
S2_PROFILES = tuple(f"productive-ocr-s2-scoped-repeat-{i}-v4" for i in range(1, 4))
D1_PACKAGE = Path("artifacts/audit-series-20261102-01/D1")
D1_APPROVAL_SHA = "38c82284f60d1ae352817acfa59f157fc2f34239a59bb6acfb408176f7f3e143"
D1_BODY_SHA = "7a6bed37b90d681d02201b37f327ab6c6aaea2f187719f141aa78fe55824d1c4"
D1_PROFILES = tuple(f"productive-ocr-d1-audit-repeat-{i}-v2" for i in range(1, 4))
D2_PACKAGE = Path("artifacts/audit-series-20261102-01/D2")
D2_APPROVAL_SHA = "c54e80ef62b01ba92586af9ee767d5166cad686bd81d4d0a48648fd0e1ab579d"
D2_BODY_SHA = "8db79f99eacadd00ed20b8f8997b2fa11d3919f69a5a02aad59d3742610b48c2"
D2_PROFILES = tuple(f"productive-ocr-d2-audit-repeat-{i}-v2" for i in range(1, 4))
COMPACT_PACKAGE = Path("artifacts/compact-audit-measurement-20261102-01")
COMPACT_APPROVAL_SHA = "47bc589e15910fb6f6174123c1dbdc5b694e3f76e295af7c810e2f669d181a10"
COMPACT_BODY_SHA = "ef80f5feb637e041fc1f24a5f4947d533b4a91fa9fdadda3e14a82fc67ded3f4"
COMPACT_PROFILES = tuple(f"productive-ocr-d1c-compact-repeat-{i}-v3" for i in range(1, 4))
LONG_PACKAGE = Path("artifacts/longer-audit-measurement-20261102-01")
LONG_APPROVAL_SHA = "c48fb3ac3efa85a61681be8ed52b1bc1e716125efcf0ec4e6036959fec49119a"
LONG_BODY_SHA = COMPACT_BODY_SHA
LONG_PROFILES = tuple(f"productive-ocr-d1l-long-repeat-{i}-v3" for i in range(1, 4))
ALL_PROFILES = (
    PROFILES
    + S1_PROFILES
    + S2_PROFILES
    + D1_PROFILES
    + D2_PROFILES
    + COMPACT_PROFILES
    + LONG_PROFILES
)


def _selection(spec):
    choices = [
        (LONG_PACKAGE, LONG_APPROVAL_SHA, LONG_BODY_SHA, LONG_PROFILES),
        (COMPACT_PACKAGE, COMPACT_APPROVAL_SHA, COMPACT_BODY_SHA, COMPACT_PROFILES),
        (D1_PACKAGE, D1_APPROVAL_SHA, D1_BODY_SHA, D1_PROFILES),
        (D2_PACKAGE, D2_APPROVAL_SHA, D2_BODY_SHA, D2_PROFILES),
        (S2_PACKAGE, S2_APPROVAL_SHA, S2_BODY_SHA, S2_PROFILES),
        (S1_PACKAGE, S1_APPROVAL_SHA, S1_BODY_SHA, S1_PROFILES),
    ]
    for choice in choices:
        if spec.contract in choice[3]:
            return choice
    return PACKAGE, APPROVAL_SHA, BODY_SHA, PROFILES


def authority(spec):
    _root, approval, body, _profiles = _selection(spec)
    return approval, body


def window(spec):
    return spec.contract.split("-")[2].upper() if spec.contract in ALL_PROFILES else "S5"


class ScopedGroup(Contract):
    contract: Literal[
        "productive-ocr-s5-scoped-group-v1",
        "productive-ocr-s1-scoped-group-v1",
        "productive-ocr-s2-scoped-group-v1",
        "productive-ocr-d1-scoped-group-v1",
        "productive-ocr-d2-scoped-group-v1",
        "productive-ocr-d1c-scoped-group-v1",
        "productive-ocr-d1l-scoped-group-v1",
    ]
    approval_sha256: Sha256
    body_sha256: Sha256
    code_sha256: Sha256
    started_at_epoch: float = Field(gt=0, allow_inf_nan=False)
    deadline_epoch: float = Field(gt=0, allow_inf_nan=False)
    calls: Literal[3]


def package(spec):
    root, _approval, _body, profiles = _selection(spec)
    return root / f"repeat-{profiles.index(spec.contract) + 1}"


def verify_group(repository, spec, packet):
    selected_root, approval, body, profiles = _selection(spec)
    root = repository / selected_root
    _verify_paths(root, package(spec).name)
    group = ScopedGroup.model_validate_json((root / "group.json").read_bytes())
    expected = (approval, body, spec.code_sha256)
    if (group.approval_sha256, group.body_sha256, group.code_sha256) != expected:
        raise ValueError("scoped group authority/input/code mismatch")
    if group.contract != f"productive-ocr-{window(spec).lower()}-scoped-group-v1":
        raise ValueError("scoped group belongs to another sample")
    _verify_group_time(group, spec)
    group_sha = sha256_bytes((root / "group.json").read_bytes())
    receipts = []
    for number in range(1, profiles.index(spec.contract) + 1):
        receipts.append(
            _verify_previous(
                root / f"repeat-{number}", spec, profiles[number - 1], group_sha, packet
            )
        )
    if len(receipts) != len(set(receipts)):
        raise ValueError("scoped repetitions reuse the same transport receipt")
    return group_sha


def _verify_group_time(group, spec):
    if group.deadline_epoch != group.started_at_epoch + 1800:
        raise ValueError("scoped group must retain1800second bound")
    if not group.started_at_epoch <= spec.started_at_epoch <= group.deadline_epoch - 600:
        raise ValueError("scoped session falls outside group budget")
    if not group.started_at_epoch <= time.time() < group.deadline_epoch:
        raise TimeoutError("scoped group deadline exceeded or clock unverified")


def _verify_previous(directory, spec, expected_profile, group_sha, packet):
    _verify_paths(directory.parent, directory.name)
    saved = json.loads((directory / "spent-slot.json").read_bytes())
    expected = (spec.approval_sha256, spec.body_sha256, spec.code_sha256)
    prior = saved["spec"]
    _verify_frozen(directory, saved, expected_profile, group_sha, packet)
    if tuple(prior[k] for k in ("approval_sha256", "body_sha256", "code_sha256")) != expected:
        raise ValueError("previous scoped slot changed input or authority")
    result = json.loads((directory / "run/result.json").read_bytes())
    _verify_previous_result(result)
    receipt = read_spool(
        directory / "run/spool", spec.body_sha256, spec.plan.model_name, spec.plan.model_digest
    )
    if receipt is None or receipt.stop_observation != "stopped":
        raise ValueError("previous scoped transport has no positive stop receipt")
    _same_receipt(result, receipt.response)
    return receipt.receipt_sha256


def _verify_paths(root, repeat):
    for path in (root, root / "group.json", root / repeat, root / repeat / "run"):
        if path.is_symlink():
            raise ValueError("scoped evidence paths cannot be symlinks")


def _verify_frozen(directory, saved, expected_profile, group_sha, packet):
    frozen = json.loads((directory / "run/frozen.json").read_bytes())
    if saved["spec"]["contract"] != expected_profile:
        raise ValueError("previous scoped slot has the wrong repetition profile")
    if saved.get("group_sha256") != group_sha or saved.get("max_output_tokens") != 1500:
        raise ValueError("previous scoped group deadline or budget changed")
    if frozen != {"config": saved, "packet": packet}:
        raise ValueError("previous scoped frozen input or configuration changed")


def _verify_previous_result(result):
    usage = result.get("usage") or {}
    if result.get("owned_stop_observation") != "stopped":
        raise ValueError("previous scoped owned stop is unknown or running")
    if result.get("status") != "completed" or result.get("finish_reason") == "length":
        raise ValueError("previous scoped transport incomplete")
    _verify_usage(usage)


def _verify_usage(usage):
    values = [usage.get("input_tokens"), usage.get("output_tokens")]
    if any(type(value) is not int or value < 0 for value in values):
        raise ValueError("previous scoped usage unknown")
    if values[1] > 1500:
        raise ValueError("previous scoped output exceeded budget")


def _same_receipt(result, response):
    for key in ("output_text", "usage", "status", "finish_reason"):
        if result.get(key) != response.get(key):
            raise ValueError("scoped result differs from durable transport receipt")


def approval_path(repository, spec):
    root, approval, _body, _profiles = _selection(spec)
    _verify_paths(repository / root, package(spec).name)
    path = repository / root / "approval.json"
    if path.is_symlink() or sha256_bytes(path.read_bytes()) != approval:
        raise ValueError("scoped small-sample authority changed")
    return path
