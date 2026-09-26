from __future__ import annotations

from datetime import date
from functools import cached_property
from pathlib import Path

from pydantic import model_validator, Field

from wahlwerk.model import Model
from wahlwerk.state import Term
from wahlwerk.ids import BodyId

class Chamber(Model):
    """The set of mandates constituting a body at a point in time."""

    body: BodyId | None = Field(default=None, description="The identifier of the body to which the chamber belongs.")
    term: Term | None = Field(default=None, description="The term during which the chamber is active.")
    mandates: tuple[Mandate, ...] | None = Field(default=None, description="The mandates in the chamber. The single source of truth for the chamber's state.")