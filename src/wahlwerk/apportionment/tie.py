"""Ties: seats a rule leaves undecided, as a result rather than an error.

Where the law decides equal claims by lot (Losentscheid, e.g. Sec. 33 (2) and 35 (5)
LWG LSA), the engine does not draw. It returns a :class:`Tie` naming the claimants and
how many seats they share, so the outcome never depends on sort order. A lot that was
actually drawn is applied as data (:meth:`Apportionment.with_lot
<wahlwerk.apportionment.result.Apportionment.with_lot>`), which makes a replay exact.
"""

from __future__ import annotations

from pydantic import Field, model_validator

from wahlwerk.model import Model

__all__ = ["Tie"]


class Tie(Model):
    """``seats`` seats that the rule gives to ``seats`` of the ``candidates``, but not
    which: their claims are exactly equal.

    Each candidate can win at most one of the tied seats. A tie always has more
    candidates than seats; otherwise every candidate would simply win one.
    """

    candidates: frozenset[str] = Field(
        description="The keys with exactly equal claims, e.g. party ids.",
    )
    seats: int = Field(
        ge=1,
        description="How many seats go to candidates, one each, by lot.",
    )

    @model_validator(mode="after")
    def _check_more_candidates(self) -> Tie:
        if len(self.candidates) <= self.seats:
            raise ValueError(
                f"tie over {self.seats} seats needs more candidates than seats, "
                f"got {sorted(self.candidates)}"
            )
        return self
