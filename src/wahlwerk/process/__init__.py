"""Processes: applying a protocol, an ordered tuple of steps, to turn state into new state.

Each kind of process is its own module, reached through this package but never
flattened into it: ``wahlwerk.process.caucus.CaucusPerParty``.
"""

from __future__ import annotations

from wahlwerk.process import allocation, caucus

__all__ = ["allocation", "caucus"]
