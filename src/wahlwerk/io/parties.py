"""Reader for party registry files, as kept in wahlwerk-data under ``parties/``.

The engine knows the file *format*; which parties exist is data. A file looks like::

    {
      "schema": 1,
      "name": "de.bund",
      "description": "...",
      "parties": {
        "cdu": {"name": "Christlich Demokratische Union Deutschlands", "short_name": "CDU"}
      }
    }

``parties`` is keyed by the party slug, which is not repeated inside the entry; the
reader maps it onto :attr:`Party.id`.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from pydantic import Field, ValidationError

from wahlwerk.ids import DottedKey
from wahlwerk.model import Model
from wahlwerk.party.party import Party

__all__ = ["SCHEMAS", "read_parties"]

logger = logging.getLogger(__name__)

SCHEMAS = frozenset({1})
"""Schema versions of party registry files this engine reads."""


class _PartyFile(Model):
    """The envelope of a party registry file, ``schema`` already checked and removed."""

    name: DottedKey = Field(
        description="The scope the registry covers, e.g. ``de.bund``.",
    )
    description: str = Field(
        default="",
        description="Free-text description of the registry.",
    )
    parties: dict[str, dict[str, Any]] = Field(
        description="Party entries keyed by party slug.",
    )


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """``json`` keeps the last of two equal keys; a registry must not."""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate key {key!r}")
        result[key] = value
    return result


def read_parties(file_path: str | Path) -> tuple[Party, ...]:
    """Read the parties from a registry file, in file order.

    Raises ``ValueError`` naming the file for a duplicate key, an unsupported schema,
    an unknown field or an invalid party.
    """
    file_path = Path(file_path)
    try:
        raw = json.loads(
            file_path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
        )
    except ValueError as e:
        raise ValueError(f"{file_path}: {e}") from e

    if not isinstance(raw, dict):
        # Bad file content, not a bad argument: one exception type for every format error.
        raise ValueError(f"{file_path}: expected a JSON object, got {type(raw).__name__}")  # noqa: TRY004
    schema = raw.pop("schema", None)
    if schema not in SCHEMAS:
        raise ValueError(
            f"{file_path}: schema {schema!r} is not supported, "
            f"expected one of {sorted(SCHEMAS)}"
        )
    try:
        envelope = _PartyFile.model_validate(raw)
    except ValidationError as e:
        raise ValueError(f"{file_path}: {e}") from e

    parties = []
    for slug, entry in envelope.parties.items():
        try:
            parties.append(Party.model_validate({**entry, "id": slug}))
        except ValidationError as e:
            raise ValueError(f"{file_path}: party {slug!r}: {e}") from e
    logger.info("%s: read %d parties for %s", file_path, len(parties), envelope.name)
    return tuple(parties)
