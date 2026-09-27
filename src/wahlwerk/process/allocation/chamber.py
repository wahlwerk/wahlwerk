"""Forming the chamber: one mandate per seat the allocation established (e.g. Sec. 1 (1)
and 35 (7) LWG LSA: at least 83 seats, Wahlkreis seats first, then list seats)."""

from __future__ import annotations

from pydantic import Field

from wahlwerk.model import Seats
from wahlwerk.process.allocation.base import Allocation, AllocationStep
from wahlwerk.state.chamber import Chamber
from wahlwerk.state.mandate import Mandate
from wahlwerk.state.mandate_origin import MandateOrigin, MandateSource

__all__ = ["FormChamber"]


class FormChamber(AllocationStep):
    """Form the chamber: a mandate for each Wahlkreis won, then each party's list seats.

    A Wahlkreis seat is named after its unit's last two segments (``de.st.wk.001`` gives
    ``wk.001``); a list seat after its party and number (``list.afd.001``). Every mandate
    was won in the election and is filled; an Einzelbewerber's seat has no party. The
    chamber has no caucuses yet: they are formed afterwards by the members, with
    :meth:`~wahlwerk.state.chamber.Chamber.form_caucuses`.
    """

    minimum_mandates: Seats | None = Field(
        default=None,
        description="The seats the chamber has at least, by law, e.g. 83; ``None`` if the law sets none.",
    )

    @property
    def reads(self) -> frozenset[str]:
        return frozenset({"districts", "list_seats"})

    @property
    def writes(self) -> frozenset[str]:
        return frozenset({"chamber"})

    def _apply(self, allocation: Allocation) -> Allocation:
        allocation.district_wins()  # raises on a Wahlkreis still tied
        elected = MandateOrigin(source=MandateSource.ELECTION)
        mandates = [
            Mandate.model_validate(
                {"id": ".".join(d.unit.split(".")[-2:]), "party": d.party, "origin": elected}
            )
            for d in allocation.districts or ()
        ]
        for party, seats in allocation.list_seats or ():
            mandates += [
                Mandate.model_validate(
                    {"id": f"list.{party}.{n:03d}", "party": party, "origin": elected}
                )
                for n in range(1, seats + 1)
            ]
        chamber = Chamber(mandates=tuple(mandates), minimum_mandates=self.minimum_mandates)
        return allocation.with_values(chamber=chamber)
