"""How a mandate was won or assigned."""

from __future__ import annotations

from enum import Enum

from pydantic import Field

from wahlwerk.model import Model

__all__ = ["MandateOrigin", "MandateSource"]


class MandateSource(Enum):
    """The route by which a seat came to be held.

    ``UNRECORDED`` exists because missing facts are modelled as absent, not faked.
    """

    UNRECORDED = "unrecorded"
    ELECTION = "election"
    APPOINTMENT = "appointment"
    SUCCESSION = "succession"


class MandateOrigin(Model):
    """How a mandate was won or assigned, recorded on every seat."""

    source: MandateSource = Field(
        default=MandateSource.UNRECORDED,
        description="The route by which the seat came to be held.",
    )
