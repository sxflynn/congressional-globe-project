"""Three fixed S5 observations under the human's small-sample autonomy instruction."""

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


class ScopedGroup(Contract):
    contract: Literal["productive-ocr-s5-scoped-group-v1"]
    approval_sha256: Sha256
    body_sha256: Sha256
    code_sha256: Sha256
    started_at_epoch: float = Field(gt=0, allow_inf_nan=False)
    deadline_epoch: float = Field(gt=0, allow_inf_nan=False)
    calls: Literal[3]


def package(spec):
    return PACKAGE / f"repeat-{PROFILES.index(spec.contract) + 1}"


def verify_group(repository, spec, packet):
    root = repository / PACKAGE
    _verify_paths(root, package(spec).name)
    group = ScopedGroup.model_validate_json((root / "group.json").read_bytes())
    expected = (APPROVAL_SHA, BODY_SHA, spec.code_sha256)
    if (group.approval_sha256, group.body_sha256, group.code_sha256) != expected:
        raise ValueError("scoped group authority/input/code mismatch")
    _verify_group_time(group, spec)
    group_sha = sha256_bytes((root / "group.json").read_bytes())
    receipts = []
    for number in range(1, PROFILES.index(spec.contract) + 1):
        receipts.append(
            _verify_previous(root / f"repeat-{number}", spec, number, group_sha, packet)
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


def _verify_previous(directory, spec, number, group_sha, packet):
    _verify_paths(directory.parent, directory.name)
    saved = json.loads((directory / "spent-slot.json").read_bytes())
    expected = (spec.approval_sha256, spec.body_sha256, spec.code_sha256)
    prior = saved["spec"]
    _verify_frozen(directory, saved, number, group_sha, packet)
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


def _verify_frozen(directory, saved, number, group_sha, packet):
    frozen = json.loads((directory / "run/frozen.json").read_bytes())
    if saved["spec"]["contract"] != PROFILES[number - 1]:
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
    _verify_paths(repository / PACKAGE, package(spec).name)
    path = repository / PACKAGE / "approval.json"
    if sha256_bytes(path.read_bytes()) != APPROVAL_SHA:
        raise ValueError("scoped small-sample authority changed")
    return path
