"""A Wahlperiode of a body."""

from __future__ import annotations

from datetime import date

from pydantic import Field, model_validator

from wahlwerk.ids import BodyId
from wahlwerk.model import Model

__all__ = ["Term"]


class Term(Model):
    """A legislative period (Wahlperiode) of one body."""

    body: BodyId | None = Field(
        default=None,
        description="The institution this term is a Wahlperiode of, e.g. ``de.bund.bundestag``, if known.",
    )
    number: int | None = Field(
        default=None,
        ge=1,
        description="The number of the term within the body, counted from 1.",
    )
    elected_on: date | None = Field(
        default=None,
        description="The election day of the term.",
    )
    start: date | None = Field(
        default=None,
        description="The first day of the term. Not the election day.",
    )
    scheduled_end: date | None = Field(
        default=None,
        description="The day the term is scheduled to end.",
    )
    actual_end: date | None = Field(
        default=None,
        description="The day the term actually ended, once it has.",
    )

    @model_validator(mode="after")
    def _check_order(self) -> Term:
        who = self.body or "term"
        if (
            self.start is not None
            and self.elected_on is not None
            and self.start < self.elected_on
        ):
            raise ValueError(
                f"{who}: term starts {self.start}, before the election on "
                f"{self.elected_on}"
            )
        if self.start is None:
            return self
        ends = (("scheduled_end", self.scheduled_end), ("actual_end", self.actual_end))
        for label, end in ends:
            if end is not None and end < self.start:
                raise ValueError(f"{who}: {label} {end} precedes start {self.start}")
        return self

    @property
    def is_ended(self) -> bool:
        """Whether the term has ended."""
        return self.actual_end is not None

    @property
    def is_ended_early(self) -> bool:
        """Whether the term ended before its scheduled end, e.g. by Auflösung."""
        return (
            self.actual_end is not None
            and self.scheduled_end is not None
            and self.actual_end < self.scheduled_end
        )
