"""A seat and how it was won.

Lives at the top level rather than in :mod:`wahlwerk.state`.
"""

from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import Field, model_validator

from wahlwerk.ids import CandidateId, LevelName, PartyId, UnitId
from wahlwerk.model import Model

__all__ = ["MandateOrigin"]

class MandateSource(Enum):
    UNRECORDED = "unrecorded"
    ELECTION = "election"
    APPOINTMENT = "appointment"
    SUCCESSION = "succession"

class MandateOrigin(Model, ):
    """How a mandate was won or assigned -- recorded on every seat."""
    source: MandateSource = MandateSource.UNRECORDED