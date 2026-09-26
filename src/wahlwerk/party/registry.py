"""The parties known to one election or archive, looked up by id."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from functools import cached_property
from pathlib import Path
from types import MappingProxyType

from pydantic import Field, model_validator

from wahlwerk.io.parties import read_parties
from wahlwerk.model import Model
from wahlwerk.party.party import Party

__all__ = ["PartyRegistry"]


class PartyRegistry(Model):
    """The parties known to one election or archive.

    Passed around explicitly rather than held in a global, because party names change
    over time (Die Grünen became Bündnis 90/Die Grünen in 1993) and a registry right for
    one election can be wrong for another.
    """

    parties: tuple[Party, ...] = Field(
        default_factory=tuple,
        description="Every registered party, each id at most once.",
    )

    # ===========================================================
    # Validators
    # ===========================================================
    @model_validator(mode="after")
    def _check_unique(self) -> PartyRegistry:
        seen: set[str] = set()
        for party in self.parties:
            if party.id in seen:
                raise ValueError(f"party {party.id!r} is registered twice")
            seen.add(party.id)
        return self

    # ===========================================================
    # Properties
    # ===========================================================
    @cached_property
    def _by_id(self) -> Mapping[str, Party]:
        return MappingProxyType({party.id: party for party in self.parties})

    def __contains__(self, party_id: object) -> bool:
        return party_id in self._by_id

    def __len__(self) -> int:
        return len(self.parties)

    def __iter__(self) -> Iterator[Party]:  # type: ignore[override]
        return iter(self.parties)

    # ===========================================================
    # Constructors
    # ===========================================================
    @classmethod
    def from_json(cls, file_path: str | Path) -> PartyRegistry:
        """Load a registry file as kept in wahlwerk-data, e.g. ``parties/de/de.bund.json``.

        The format is read by :func:`wahlwerk.io.parties.read_parties`.
        """
        return cls(parties=read_parties(Path(file_path)))

    # ===========================================================
    # Accessors
    # ===========================================================
    
    def __getitem__(self, party_id: str) -> Party:
        try:
            return self._by_id[party_id]
        except KeyError:
            raise KeyError(f"no party {party_id!r} in registry") from None

    def get(self, party_id: str, default: Party | None = None) -> Party | None:
        """The party with this id, or ``default``. Never raises, unlike ``registry[id]``."""
        return self._by_id.get(party_id, default)

    
