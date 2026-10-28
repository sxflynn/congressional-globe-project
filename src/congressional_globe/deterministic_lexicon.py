"""Pinned local lookup resources; dictionary membership is never source truth."""

import hashlib
from dataclasses import dataclass, field
from typing import Literal

from pydantic import Field

from congressional_globe.bracket_cues import Contract
from congressional_globe.scan_models import Sha256


class LexiconSpec(Contract):
    label: str = Field(min_length=1, max_length=256)
    purpose: Literal["words", "names", "places"]
    sha256: Sha256
    provenance: str = Field(min_length=1)
    limitations: str = Field(min_length=1)


class LexiconIdentity(Contract):
    spec: LexiconSpec
    lookup_rule: Literal["nonblank-lines-strip-casefold-v1"] = "nonblank-lines-strip-casefold-v1"
    forms_count: int = Field(ge=0)


@dataclass(frozen=True)
class Lexicon:
    spec: LexiconSpec
    data: bytes = field(repr=False)
    forms: frozenset[str] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        spec = LexiconSpec.model_validate(self.spec)
        if not isinstance(self.data, bytes) or len(self.data) > 8 * 1024 * 1024:
            raise ValueError("lexicon must be bytes within 8MiB")
        if hashlib.sha256(self.data).hexdigest() != spec.sha256:
            raise ValueError("lexicon byte fingerprint mismatch")
        forms = frozenset(
            line.strip().casefold()
            for line in self.data.decode("utf-8").splitlines()
            if line.strip()
        )
        object.__setattr__(self, "spec", spec)
        object.__setattr__(self, "forms", forms)

    def identity(self) -> LexiconIdentity:
        return LexiconIdentity(spec=self.spec, forms_count=len(self.forms))


def lookup(lexicon: Lexicon | None, text: str) -> Literal["known", "unfamiliar", "not_assessed"]:
    if lexicon is None:
        return "not_assessed"
    return "known" if text.casefold() in lexicon.forms else "unfamiliar"
