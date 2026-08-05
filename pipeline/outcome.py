"""The one way this pipeline says "we don't know".

Every measurement here can fail to happen: a provider call exhausts its retries, a sandbox dies,
a pool lacks a reference solution. Those are not answers, and the recurring defect in this codebase
was writing them down as if they were — a falsy default that reads as "the model failed", which is
the direction that flatters our infrastructure and penalises the thing under study.

So an unknown is a value, not an absence. `Unknown` carries who is to blame and why, `Blame` has no
default, and there is no inference from free text: whoever detects the failure states the blame at
that point, because that is the only place it is actually known.

    outcome = Unknown(Blame.INFRA, "property_gen abstained after retries")
    ...
    if is_unknown(outcome):
        record_it(outcome.blame, outcome.reason)

`Blame.UNRECORDED` exists only for artifacts written before this module, where the blame genuinely
was not recorded and guessing it would be a fabrication.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any, TypeVar

T = TypeVar("T")


class Blame(str, Enum):
    """Who or what caused a measurement not to happen."""

    MODEL = "model"
    INFRA = "infra"
    UNRECORDED = "unrecorded"


@dataclass(frozen=True)
class Unknown:
    """A measurement that did not happen, with the blame fixed where it was detected."""

    blame: Blame
    reason: str

    def __bool__(self) -> bool:
        raise TypeError(
            f"Unknown({self.blame.value}: {self.reason!r}) has no truth value — this is the guard "
            "against silently reading an unknown as False. Use is_unknown() and handle it."
        )

    def to_json(self) -> dict[str, str]:
        return {"blame": self.blame.value, "reason": self.reason}

    @classmethod
    def from_json(cls, data: Mapping[str, Any]) -> "Unknown":
        return cls(Blame(data["blame"]), str(data.get("reason", "")))


Measured = T | Unknown


def is_unknown(value: Any) -> bool:
    return isinstance(value, Unknown)


def known(value: Measured[T], default: T) -> T:
    """The measured value, or `default` when it is unknown. Makes the substitution explicit."""
    return default if is_unknown(value) else value
