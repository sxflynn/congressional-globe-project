"""Closed opt-in lifecycle allowance for the fixed T116 diagnostic only."""

from typing import Literal

from pydantic import Field

from congressional_globe.productive_ocr_local import OwnedLocalPlan


class LongerAuditPlan(OwnedLocalPlan):
    diagnostic_contract: Literal["productive-ocr-d1-longer-plan-v1"]
    request_timeout_seconds: float = Field(default=300.0, ge=300, le=300)


def validate_diagnostic_plan(plan):
    """Keep ordinary plans limited to120seconds; validate the exact named subtype."""
    if type(plan) is LongerAuditPlan:
        return LongerAuditPlan.model_validate(plan)
    return OwnedLocalPlan.model_validate(plan)
