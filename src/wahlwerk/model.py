"""The pydantic base every data type in wahlwerk inherits from.

Three settings, each load-bearing:

``frozen=True``
    State is inert. Only events produce new state, and a model that could be mutated
    in place would make a history of states a lie. It also makes models hashable, which
    is what lets them be dictionary keys in a tally.

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

Numeric validation is deliberate throughout: vote and seat counts are non-negative
``int``, shares are exact :class:`~fractions.Fraction` bounded to ``[0, 1]``, never
``float``. Apportionment methods are only reproducible against official results under
exact rational arithmetic.
"""

from __future__ import annotations

from fractions import Fraction
from typing import TYPE_CHECKING, Annotated, Any

from pydantic import BaseModel, ConfigDict, Field

__all__ = ["Count", "Model", "Seats", "Share"]

Count = Annotated[int, Field(ge=0)]
"""An absolute number of votes. Never negative."""

Seats = Annotated[int, Field(ge=0)]
"""An absolute number of seats. Never negative."""

Share = Annotated[Fraction, Field(ge=0, le=1)]
"""An exact proportion in ``[0, 1]``. Never ``float``."""


class Model(BaseModel):
    """Frozen, validated, no unknown fields."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_default=True,
    )

    if TYPE_CHECKING:
        # For editors only: Pylance (pyright) documents a constructor call with the
        # nearest ``__init__`` docstring up the class tree, which would be pydantic's
        # generic "Create a new model by parsing and validating input data ...". This
        # blank one stops that search. Pyright never falls back to the class docstring
        # at a call, so a call shows the signature (the fields) alone; hovering the class
        # name anywhere else shows its docstring. Not defined at runtime.
        def __init__(self, /, **data: Any) -> None:
            """ """
