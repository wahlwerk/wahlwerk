"""A seat and how it was won.

Lives at the top level rather than in :mod:`wahlwerk.state`.
"""

from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import Field, model_validator

from wahlwerk.ids import CandidateId, LevelName, PartyId, UnitId
from wahlwerk.model import Model

__all__ = ["Mandate", "MandateSource"]


class Mandate(Model):
    """One seat, and whoever holds it.

    ``person``, ``unit`` and ``level`` are optional because a seat can be real while
    those facts are not on record: a chamber reconstructed from a published seat
    distribution knows the party and nothing else, and a seat between a Vacancy and the
    Nachrücken that fills it has no holder at all.
    """

    person: CandidateId | None = Field(default=None, description="The identifier of the person holding the mandate.")
    origin: MandateOrigin = MandateOrigin.UNRECORDED