"""Lots: ties of a popular vote decided by a draw that was actually held.

Where the law decides equal claims by lot (Losentscheid: Sec. 33 S. 2 and 35 (5) LWG LSA,
a tied Wahlkreis or equal remainders), the engine never draws. A step leaves a
:class:`~wahlwerk.apportionment.tie.Tie`, and a :class:`Lot` recorded with the vote
decides it: the tie it settles (where, among whom) and who won. A replay of the election
is then exact; a tie no recorded lot covers, as in most counterfactuals, still stops the
allocation.
"""

from __future__ import annotations

from pydantic import Field, model_validator

from wahlwerk.ids import OptionId, Slug, UnitId
from wahlwerk.model import Model

__all__ = ["Lot"]


class Lot(Model):
    """One draw: among ``candidates``, tied in ``section`` (in ``unit``, where the tie was
    one unit's), it gave the seats to ``winners``, one each.

    It decides a tie only when that tie is exactly the one drawn for: the same section
    and unit, the same candidates, as many seats as winners. A lot recorded for an
    election whose counterfactual never ties that way is simply not used.
    """

    section: Slug = Field(
        description="The vote the tie arose in, e.g. ``erststimme`` (a Wahlkreis) or ``zweitstimme`` (the seats).",
    )
    unit: UnitId | None = Field(
        default=None,
        description=(
            "The unit the tie was in, e.g. the Wahlkreis ``de.st.wk.017``, or the Land "
            "``de.st`` for a tie over its seats; ``None`` where the tie spans no one unit."
        ),
    )
    candidates: frozenset[OptionId] = Field(
        description="Every option with an equal claim, e.g. two Wahlkreis candidates or two parties.",
    )
    winners: frozenset[OptionId] = Field(
        description="The candidates the lot gave a seat, one each.",
    )
    source: str | None = Field(
        default=None,
        description=(
            "The record of the draw, e.g. the Niederschrift of the Kreiswahlausschuss and "
            "its date; ``None`` where not recorded."
        ),
    )

    @model_validator(mode="after")
    def _check_draw(self) -> Lot:
        where = f"lot in {self.section!r}" + (f" for {self.unit!r}" if self.unit else "")
        if not self.winners:
            raise ValueError(f"{where} names no winner")
        strangers = sorted(self.winners - self.candidates)
        if strangers:
            raise ValueError(f"{where}: winners {strangers} are not among the candidates {sorted(self.candidates)}")
        if len(self.winners) >= len(self.candidates):
            raise ValueError(
                f"{where}: {len(self.winners)} winners among {len(self.candidates)} candidates is no draw"
            )
        return self

    @property
    def seats(self) -> int:
        """How many seats the lot gave: one per winner."""
        return len(self.winners)

    def decides(self, section: str, unit: str | None, candidates: frozenset[str], seats: int) -> bool:
        """Whether this lot was drawn for the tie of ``seats`` seats among ``candidates``
        in ``section`` and ``unit``."""
        return (
            self.section == section
            and self.unit == unit
            and self.candidates == candidates
            and self.seats == seats
        )
