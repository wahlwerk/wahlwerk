"""Steps of the internal process that forms a chamber's caucuses.

:meth:`Chamber.form_caucuses` clears the old caucuses and applies a protocol, an ordered
tuple of steps, one after the other. Each step is a frozen model, so a protocol is data:
it can be printed, compared and validated, and later read from a law.
"""

from __future__ import annotations

import warnings
from abc import abstractmethod
from typing import TYPE_CHECKING

from pydantic import Field, model_validator

from wahlwerk.ids import CaucusId, PartyId
from wahlwerk.model import Model
from wahlwerk.party.party import Party, party_id_of
from wahlwerk.state.caucus import Caucus

if TYPE_CHECKING:
    from wahlwerk.state.chamber import Chamber

__all__ = [
    "CaucusOfParties",
    "CaucusPerParty",
    "CaucusProtocol",
    "CaucusStep",
    "ProtocolWarning",
]


class ProtocolWarning(UserWarning):
    """A step applied to a chamber that does not fully fit it, e.g. a party it names has
    no seats. The step still runs; filter this category to silence or escalate it."""


class CaucusStep(Model):
    """One step of a caucus protocol: a chamber in, a chamber out.

    Callable, so ``step(chamber)`` is ``step.apply(chamber)``.
    """

    @abstractmethod
    def apply(self, chamber: Chamber) -> Chamber:
        """The chamber with this step's change to its caucuses."""

    def __call__(self, chamber: Chamber) -> Chamber:
        return self.apply(chamber)


CaucusProtocol = tuple[CaucusStep, ...]
"""An ordered protocol of caucus steps, applied first to last."""


class CaucusPerParty(CaucusStep):
    """Each party forms one caucus, with the party id as its id, from its filled seats
    that are in no caucus yet.

    Vacant seats and seats whose party is not on record stay without a caucus. New
    caucuses are ordered by the party's first seat.
    """

    def apply(self, chamber: Chamber) -> Chamber:
        taken = {mandate_id for caucus in chamber.caucuses for mandate_id in caucus.mandates}
        mandates: dict[str, list[str]] = {}
        for mandate in chamber.mandates:
            if mandate.id in taken or mandate.is_vacant or mandate.party is None:
                continue
            mandates.setdefault(mandate.party, []).append(mandate.id)
        formed = [
            Caucus.model_validate({"id": party, "mandates": frozenset(ids)})
            for party, ids in mandates.items()
        ]
        return chamber.with_caucuses((*chamber.caucuses, *formed))


class CaucusOfParties(CaucusStep):
    """The filled seats of several parties form one caucus, e.g. CDU and CSU.

    Their seats leave whatever caucus they were in, and a caucus left empty is dropped.
    The new caucus comes last. A party without filled seats raises a
    :class:`ProtocolWarning`. If at least two parties have seats, the caucus is still
    formed from those; if only one or none has, nothing changes, since one party alone
    is not a grouping.

    The caucus id is the party ids joined by ``-`` (``cdu-csu``) unless ``id`` is given.
    """

    parties: tuple[PartyId, ...] = Field(
        min_length=2,
        description="The parties whose seats form the caucus, e.g. ``('cdu', 'csu')``.",
    )
    id: CaucusId = Field(
        description="The id of the new caucus; the party ids joined by ``-`` if not given.",
    )

    @model_validator(mode="before")
    @classmethod
    def _party_ids(cls, data: object) -> object:
        """Accept :class:`Party` objects as well as ids, and default the caucus id."""
        if not isinstance(data, dict) or not isinstance(data.get("parties"), (list, tuple)):
            return data
        parties = tuple(party_id_of(p) if isinstance(p, Party) else p for p in data["parties"])
        data = {**data, "parties": parties}
        if data.get("id") is None and all(isinstance(p, str) for p in parties):
            data["id"] = "-".join(parties)
        return data

    @model_validator(mode="after")
    def _check_distinct(self) -> CaucusOfParties:
        if len(set(self.parties)) != len(self.parties):
            raise ValueError(f"parties {self.parties} name a party more than once")
        return self

    def apply(self, chamber: Chamber) -> Chamber:
        parties = set(self.parties)
        filled = [m for m in chamber.mandates if m.party in parties and not m.is_vacant]
        has_seats = {m.party for m in filled}
        present = [party for party in self.parties if party in has_seats]
        missing = [party for party in self.parties if party not in has_seats]
        if len(present) < 2:
            warnings.warn(
                f"CaucusOfParties {self.id!r}: only {present} of {list(self.parties)} "
                "have filled seats; no caucus formed",
                ProtocolWarning,
                stacklevel=2,
            )
            return chamber
        if missing:
            warnings.warn(
                f"CaucusOfParties {self.id!r}: {missing} have no filled seats; forming "
                f"{self.id!r} from {present} only",
                ProtocolWarning,
                stacklevel=2,
            )
        ids = frozenset(m.id for m in filled)
        kept = tuple(
            caucus.model_copy(update={"mandates": caucus.mandates - ids})
            for caucus in chamber.caucuses
            if caucus.mandates - ids
        )
        formed = Caucus.model_validate({"id": self.id, "mandates": ids})
        return chamber.with_caucuses((*kept, formed))
