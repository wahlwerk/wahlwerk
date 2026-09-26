"""Identifiers: lowercase ASCII strings, never objects.

Every id is a ``NewType`` over a pattern-constrained string, so a malformed key fails
validation where it is written and a type checker refuses a ``CandidateId`` where a
``BodyId`` belongs.
"""

from __future__ import annotations

from typing import Annotated, NewType

from pydantic import StringConstraints

__all__ = [
    "BodyId",
    "CandidateId",
    "CaucusId",
    "DottedKey",
    "LevelName",
    "MandateId",
    "PartyId",
    "Slug",
    "UnitId",
]

SLUG = r"[a-z0-9]+(?:[-_][a-z0-9]+)*"
"""One segment: lowercase ASCII, inner hyphens or underscores, no leading separator."""

SINGLE = StringConstraints(pattern=rf"^{SLUG}$")
"""The constraint behind :data:`Slug` and single-segment id types."""

Slug = Annotated[str, SINGLE]
"""A single-segment key: ``wahlkreis``, ``zweitstimme``, ``cdu-csu``."""

DOTTED = StringConstraints(pattern=rf"^{SLUG}(?:\.{SLUG})*$")
"""The constraint behind :data:`DottedKey` and dotted id types."""

DottedKey = Annotated[str, DOTTED]
"""A dotted path, narrowest scope last: ``de.bund.wk.001``."""

# NewType needs a real class as its base, so each id is a NewType over ``str``
# wrapped in the constraint itself (``SINGLE`` or ``DOTTED``). Never wrap it in
# ``Slug`` or ``DottedKey``: pydantic silently ignores an Annotated alias used as
# metadata, and the pattern is not checked.

_BodyId = NewType("_BodyId", str)
BodyId = Annotated[_BodyId, DOTTED]
"""Stable key of an institution, e.g. ``"de.bund.bundestag"``, ``"de.by.landtag"``."""

_CandidateId = NewType("_CandidateId", str)
CandidateId = Annotated[_CandidateId, DOTTED]
"""Stable key of a person who stands for or holds a mandate."""

_PartyId = NewType("_PartyId", str)
PartyId = Annotated[_PartyId, SINGLE]
"""Stable key of a party, e.g. ``"cdu"``."""

_CaucusId = NewType("_CaucusId", str)
CaucusId = Annotated[_CaucusId, SINGLE]
"""Key of a caucus, unique within its chamber, e.g. ``"cdu-csu"``."""

_MandateId = NewType("_MandateId", str)
MandateId = Annotated[_MandateId, DOTTED]
"""Key of a seat, unique within its chamber, e.g. ``"spd.001"``; later from how the seat
was won (``"wk.001"``). Identifies the seat, not its holder, so it survives Nachrücken."""

_UnitId = NewType("_UnitId", str)
UnitId = Annotated[_UnitId, DOTTED]
"""Key of a unit votes are counted in, e.g. ``"de.st.wk.001"``."""

_LevelName = NewType("_LevelName", str)
LevelName = Annotated[_LevelName, SINGLE]
"""Kind of unit, e.g. ``"wahlkreis"``, ``"kreis"``, ``"land"``."""
