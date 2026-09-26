"""A seat and how it was won."""

from __future__ import annotations

from pydantic import Field

from wahlwerk.ids import MandateId, PartyId
from wahlwerk.model import Model
from wahlwerk.party.party import Party, party_id_of
from wahlwerk.state.mandate_origin import MandateOrigin

__all__ = ["Mandate"]


class Mandate(Model):
    """One seat in a chamber.

    ``id`` names the seat within its chamber and stays when the holder changes. ``party``
    is optional because a seat can be real while its party is not on record. Missing
    facts are modelled as absent, not faked.
    """

    id: MandateId = Field(
        description="The key of the seat, unique within its chamber, e.g. ``spd.001``.",
    )
    party: PartyId | None = Field(
        default=None,
        description="The party whose nomination won the seat, if known.",
    )
    origin: MandateOrigin = Field(
        default=MandateOrigin(),
        description="How the mandate was won or assigned.",
    )
    is_vacant: bool = Field(
        default=False,
        description="Whether the seat exists but nobody holds it; ``party`` may still be known.",
    )

    # ===========================================================
    # Constructors
    # ===========================================================
    @classmethod
    def from_party(cls, party: Party | str, id: str) -> Mandate:
        """The seat ``id`` won by ``party``, given as a :class:`Party` or its id.

        Origin is left ``UNRECORDED``: knowing the party does not say how the seat was won.
        """
        return cls.model_validate({"id": id, "party": party_id_of(party)})

    # ===========================================================
    # Properties
    # ===========================================================
    @property
    def has_party(self) -> bool:
        """Whether the party that won the seat is on record."""
        return self.party is not None
