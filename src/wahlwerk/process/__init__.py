"""Processes: applying a protocol, an ordered tuple of steps, to turn state into new state."""

from __future__ import annotations

from wahlwerk.process.caucus import (
    CaucusPerParty,
    CaucusProtocol,
    CaucusStep,
    GroupParties,
    ProtocolWarning,
)

__all__ = ["CaucusPerParty", "CaucusProtocol", "CaucusStep", "GroupParties", "ProtocolWarning"]
