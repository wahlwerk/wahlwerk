from __future__ import annotations

from enum import Enum
from functools import cached_property
from typing import Annotated, NewType

from pydantic import StringConstraints, model_validator

from wahlwerk.model import Model

SLUG = r"[a-z0-9]+(?:[-_][a-z0-9]+)*"
"""One segment: lowercase ASCII, inner hyphens or underscores, no leading separator."""

Slug = Annotated[str, StringConstraints(pattern=rf"^{SLUG}$")]
"""A single-segment key: ``wahlkreis``, ``zweitstimme``, ``cdu-csu``."""

DottedKey = Annotated[str, StringConstraints(pattern=rf"^{SLUG}(?:\.{SLUG})*$")]
"""A dotted path, narrowest scope last: ``de.bund.wk.001``."""


BodyId = NewType("BodyId", DottedKey)
"""Stable key of an institution, e.g. ``"de.bund.bundestag"``, ``"de.by.landtag"``."""