"""A party: something that can hold an entitlement to seats."""

from __future__ import annotations

from pydantic import Field

from wahlwerk.ids import PartyId
from wahlwerk.model import Model

__all__ = ["Party", "party_id_of"]


class Party(Model):
    """A party or other grouping that can hold an entitlement to seats."""

    id: PartyId = Field(
        description="The stable key of the party, e.g. ``cdu``.",
    )
    name: str = Field(
        min_length=1,
        description="The full name of the party.",
    )
    short_name: str | None = Field(
        default=None,
        min_length=1,
        description="The short name of the party, if it has one.",
    )


def party_id_of(party: Party | str) -> str:
    """The id of a party given either as a :class:`Party` or as its id.

    Lets constructors accept both ``{"cdu": 3}`` and ``{cdu_party: 3}``. The id is not
    validated here; the model it ends up in does that.
    """
    return party.id if isinstance(party, Party) else party
