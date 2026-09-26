"""The pydantic base every data type in wahlwerk inherits from.

Three settings, each load-bearing:

``frozen=True``
    State is inert. Only events produce new state, and a model that could be mutated
    in place would make an :class:`~wahlwerk.events.base.BodyState` history a lie.
    It also makes models hashable, which is what lets a
    :class:`~wahlwerk.ballots.TallyKey` be a dictionary key.

``extra="forbid"``
    A misspelled field in a source file or a fixture is a hard error, not a silently
    dropped column. Election data arrives from sixteen Landeswahlleiter with sixteen
    sets of column names; this is the tripwire.

``validate_default=True``
    Defaults are checked like everything else, so an invariant cannot be dodged by
    leaving a field out.

Note what pydantic does *not* freeze: a ``dict`` or ``list`` field is still mutable in
place. Fields therefore use ``tuple`` and ``frozenset`` wherever the value is meant to
be part of the model's identity.

Numeric validation is deliberate throughout: vote counts are
:data:`~pydantic.NonNegativeInt`, shares are exact :class:`~fractions.Fraction` bounded
to ``[0, 1]`` -- never ``float``. See :mod:`wahlwerk.apportionment.base` for why.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

__all__ = ["Count", "Model", "Seats", "Share", "SlotModel"]

Count = Annotated[int, Field(ge=0)]
"""An absolute number of votes. Never negative."""

Seats = Annotated[int, Field(ge=0)]
"""An absolute number of seats. Never negative."""

class Model(BaseModel):
    """Frozen, validated, no unknown fields."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_default=True,
        use_attribute_docstrings=True,
    )