"""Standing composition of a body. Inert data -- only events produce new state."""

from __future__ import annotations

from datetime import date
from functools import cached_property
from pathlib import Path

from pydantic import Field, model_validator

from wahlwerk import Model

from wahlwerk.ids import BodyId

class Term(Model):
    """A legislative period.
    """

    body: BodyId = Field(..., description="The institution this term is a Wahlperiode of, e.g. ``de.bund.bundestag``.")
    """The institution this term is a Wahlperiode of, e.g. ``de.bund.bundestag``."""

    start: date | None = Field(default=None, description="The first day of the term. Not the election day.")
    elected_on: date | None = Field(default=None, description="The election day of the term.")
    scheduled_end: date | None = Field(default=None, description="The scheduled end date of the term.")
    actual_end: date | None = Field(default=None, description="The actual end date of the term, if it ended early.")
    number: int | None = Field(default=None, description="The number of the term within the body.")

    @model_validator(mode="after")
    def _check_order(self) -> Term:
        if (
            self.start is not None
            and self.elected_on is not None
            and self.start < self.elected_on
        ):
            raise ValueError(
                f"{self.body}: term starts {self.start}, before the election on "
                f"{self.elected_on}"
            )
        if self.start is None:
            return self
        ends = (("scheduled_end", self.scheduled_end), ("actual_end", self.actual_end))
        for label, end in ends:
            if end is not None and end < self.start:
                raise ValueError(f"{self.body}: {label} {end} precedes start {self.start}")
        return self

    @property
    def ended(self) -> bool:
        return self.actual_end is not None

    @property
    def ended_early(self) -> bool:
        return (
            self.actual_end is not None
            and self.scheduled_end is not None
            and self.actual_end < self.scheduled_end
        )