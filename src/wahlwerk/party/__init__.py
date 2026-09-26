"""Parties and the registry that looks them up by id."""

from __future__ import annotations

from wahlwerk.party.party import Party, party_id_of
from wahlwerk.party.registry import PartyRegistry

__all__ = ["Party", "PartyRegistry", "party_id_of"]
