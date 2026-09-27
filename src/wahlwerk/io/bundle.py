"""Reader for normalised election bundles, as kept in wahlwerk-data.

A bundle is how wahlwerk-data stores a :class:`PopularVote`; the word names the files
on disk, never the model. Each bundle sits under :data:`ELECTIONS_DIR` at the path its key spells
out, one directory per segment: ``de.landtag.st.2026`` is
``elections/de/landtag/st/2026/`` (see :func:`resolve_election_dir`).

A bundle is a directory holding two files, by default named :data:`ELECTION_FILE` and
:data:`TALLY_FILE`, and one file per alternative hierarchy. ``election.toml`` carries the
format version, the source, the levels of the main hierarchy, and the alternative
hierarchies::

    schema = 2

    [source]
    publisher = "Statistisches Landesamt Sachsen-Anhalt"
    title = "Landtagswahl 2026: Ergebnisse"
    url = "https://example.org/ergebnisse.xlsx"
    licence = "dl-de/by-2-0"
    attribution = "Statistisches Landesamt Sachsen-Anhalt, dl-de/by-2-0"
    retrieved = 2026-09-26
    sha256 = "..."

    [levels]
    land = 2
    wahlkreis = 4
    wahlbezirk = 8
    briefwahlbezirk = 8

    [hierarchies.administrative]
    levels = ["land", "kreis", "gemeinde"]

``[levels]`` is the main hierarchy, the one the unit ids spell out: each level and the
number of dotted segments in its ids, broadest first (see :class:`Level`). Every row
must name a listed level and have its depth.

Each ``[hierarchies.<name>]`` table declares an alternative hierarchy with its own
levels, broadest first; its units are in ``<name>.csv`` in the bundle, with exactly the
columns in :data:`HIERARCHY_COLUMNS`: every unit, its level, and the unit it lies in
(blank at the broadest level). It must cover every unit the tally counts. The table is
optional.

Schema 1 has neither: its tally records no levels, and summing it needs the depth
given.

``tally.csv`` is the long vote table, one :class:`TallyRow` per line, with exactly the
columns in :data:`TALLY_COLUMNS`. A blank cell is an absent value (``None``), never an
empty string.
"""

from __future__ import annotations

import csv
import logging
import sys
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter, ValidationError

from wahlwerk.ids import DottedKey, Slug
from wahlwerk.vote.popular.hierarchy import Hierarchy, HierarchyUnit
from wahlwerk.vote.popular.popular_vote import PopularVote, Source
from wahlwerk.vote.popular.tally import Level, Tally, TallyKind, TallyRow

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

__all__ = [
    "ELECTIONS_DIR",
    "ELECTION_FILE",
    "HIERARCHY_COLUMNS",
    "SCHEMA",
    "SCHEMAS",
    "TALLY_COLUMNS",
    "TALLY_FILE",
    "read_bundle",
    "resolve_election_dir",
]

logger = logging.getLogger(__name__)

SCHEMA = 2
"""The schema version of bundles this engine writes: the current format."""

SCHEMAS = frozenset({1, SCHEMA})
"""Schema versions of bundles this engine reads."""

ELECTIONS_DIR = "elections"
"""The directory in wahlwerk-data holding every bundle."""

ELECTION_FILE = "election.toml"
"""The file in a bundle holding the schema, the source and the levels."""

TALLY_FILE = "tally.csv"
"""The file in a bundle holding the long vote table."""

TALLY_COLUMNS = (
    "unit",
    "level",
    "kind",
    "section",
    "channel",
    "party",
    "candidate",
    "option",
    "count",
)
"""The header of ``tally.csv``, in order: the fields of :class:`TallyRow`."""

HIERARCHY_COLUMNS = ("unit", "level", "parent")
"""The header of a hierarchy's file, in order: the fields of :class:`HierarchyUnit`."""


_DOTTED_KEY: TypeAdapter[str] = TypeAdapter(DottedKey)
_SLUG: TypeAdapter[str] = TypeAdapter(Slug)


def resolve_election_dir(data_dir: str | Path, key: str) -> Path:
    """The bundle directory of ``key`` in the wahlwerk-data clone at ``data_dir``.

    ``de.landtag.st.2026`` is ``<data_dir>/elections/de/landtag/st/2026``. Raises
    ``TypeError`` for a non-string key, ``ValueError`` for a malformed key (which also
    keeps a key from leaving the archive) or when no such directory exists.
    """
    data_dir = Path(data_dir)
    if not isinstance(key, str):
        raise TypeError(f"key must be a str, got {type(key).__name__}")
    try:
        _DOTTED_KEY.validate_python(key)
    except ValidationError:
        raise ValueError(
            f"key {key!r} is not a dotted key, e.g. 'de.landtag.st.2026'"
        ) from None
    dir_path = data_dir.joinpath(ELECTIONS_DIR, *key.split("."))
    if not dir_path.is_dir():
        raise ValueError(f"{dir_path}: no bundle for key {key!r}")
    return dir_path


def _require(file_path: Path) -> Path:
    if not file_path.is_file():
        raise ValueError(f"{file_path}: missing from the bundle")
    return file_path


def _parse_row(cells: list[str]) -> TallyRow:
    """Build a row from its cells; a blank cell is an absent value, never ``""``."""
    fields: dict[str, Any] = {
        column: cell for column, cell in zip(TALLY_COLUMNS, cells) if cell != ""
    }
    if "kind" not in fields:
        raise ValueError("kind is blank")
    if "count" not in fields:
        raise ValueError("count is blank")
    fields["kind"] = TallyKind(fields["kind"])
    fields["count"] = int(fields["count"])
    return TallyRow.model_validate(fields)


def _read_election(
    file_path: Path,
) -> tuple[Source, tuple[Level, ...], dict[str, tuple[str, ...]]]:
    """The source, levels and declared hierarchies of a bundle, after checking its
    schema; the schema describes the file format, so it stays here and is not part of
    the model."""
    try:
        raw = tomllib.loads(_require(file_path).read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as e:
        raise ValueError(f"{file_path}: {e}") from e

    schema = raw.pop("schema", None)
    if schema not in SCHEMAS:
        raise ValueError(
            f"{file_path}: schema {schema!r} is not supported, "
            f"expected one of {sorted(SCHEMAS)}"
        )
    source = raw.pop("source", None)
    levels = raw.pop("levels", None) if schema >= 2 else None
    hierarchies = raw.pop("hierarchies", {}) if schema >= 2 else {}
    if raw:
        raise ValueError(f"{file_path}: unknown keys {sorted(raw)}")
    # Bad file content, not a bad argument: one exception type for every format error.
    if not isinstance(source, dict):
        raise ValueError(f"{file_path}: expected a [source] table")  # noqa: TRY004
    if schema >= 2 and not isinstance(levels, dict):
        raise ValueError(f"{file_path}: expected a [levels] table")
    try:
        parsed_source = Source.model_validate(source)
    except ValidationError as e:
        raise ValueError(f"{file_path}: source: {e}") from e
    try:
        parsed_levels = tuple(
            Level.model_validate({"name": name, "depth": depth})
            for name, depth in (levels or {}).items()
        )
    except ValidationError as e:
        raise ValueError(f"{file_path}: levels: {e}") from e
    return parsed_source, parsed_levels, _declared_hierarchies(file_path, hierarchies)


def _declared_hierarchies(file_path: Path, raw: object) -> dict[str, tuple[str, ...]]:
    """Each ``[hierarchies.<name>]`` table's name and levels."""
    if not isinstance(raw, dict):
        raise ValueError(f"{file_path}: expected [hierarchies.<name>] tables")  # noqa: TRY004
    declared: dict[str, tuple[str, ...]] = {}
    for name, table in raw.items():
        where = f"{file_path}: hierarchies.{name}"
        try:
            _SLUG.validate_python(name)
        except ValidationError:
            raise ValueError(f"{where}: {name!r} is not a slug") from None
        if not isinstance(table, dict):
            raise ValueError(f"{where}: expected a table")  # noqa: TRY004
        levels = table.pop("levels", None)
        if table:
            raise ValueError(f"{where}: unknown keys {sorted(table)}")
        if not isinstance(levels, list) or not all(isinstance(lvl, str) for lvl in levels):
            raise ValueError(f"{where}: expected levels = [...], a list of level names")
        declared[name] = tuple(levels)
    return declared


def _read_hierarchy(file_path: Path, name: str, levels: tuple[str, ...]) -> Hierarchy:
    units = []
    with _require(file_path).open(encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if header is None or tuple(header) != HIERARCHY_COLUMNS:
            raise ValueError(
                f"{file_path}: header {header!r} is not {','.join(HIERARCHY_COLUMNS)}"
            )
        for cells in reader:
            line = reader.line_num
            if len(cells) != len(HIERARCHY_COLUMNS):
                raise ValueError(
                    f"{file_path}: line {line}: {len(cells)} cells, "
                    f"expected {len(HIERARCHY_COLUMNS)}"
                )
            fields = {
                column: cell for column, cell in zip(HIERARCHY_COLUMNS, cells) if cell != ""
            }
            try:
                units.append(HierarchyUnit.model_validate(fields))
            except ValidationError as e:
                raise ValueError(f"{file_path}: line {line}: {e}") from e
    try:
        return Hierarchy.model_validate({"name": name, "levels": levels, "units": tuple(units)})
    except ValidationError as e:
        raise ValueError(f"{file_path}: {e}") from e


def _read_tally(file_path: Path, levels: tuple[Level, ...]) -> Tally:
    rows = []
    with _require(file_path).open(encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if header is None or tuple(header) != TALLY_COLUMNS:
            raise ValueError(
                f"{file_path}: header {header!r} is not {','.join(TALLY_COLUMNS)}"
            )
        for cells in reader:
            line = reader.line_num
            if len(cells) != len(TALLY_COLUMNS):
                raise ValueError(
                    f"{file_path}: line {line}: {len(cells)} cells, "
                    f"expected {len(TALLY_COLUMNS)}"
                )
            try:
                rows.append(_parse_row(cells))
            except ValueError as e:  # ValidationError is a ValueError
                raise ValueError(f"{file_path}: line {line}: {e}") from e
    try:
        return Tally(rows=tuple(rows), levels=levels)
    except ValidationError as e:
        raise ValueError(f"{file_path}: {e}") from e


def read_bundle(
    dir_path: str | Path,
    election_file_name: str = ELECTION_FILE,
    tally_file_name: str = TALLY_FILE,
) -> PopularVote:
    """Read the popular vote stored in a bundle directory: its source from
    ``election_file_name``, its tally from ``tally_file_name``, in file order.

    Alternative hierarchies are read from ``<name>.csv`` beside them.

    Raises ``ValueError`` naming the file for a missing file, an unsupported schema, an
    unknown key, a missing or malformed ``[levels]`` or ``[hierarchies]`` table, a wrong
    header, a row that :class:`TallyRow` rejects, a row whose level or depth
    ``[levels]`` does not allow, two rows that count the same thing, a hierarchy that is
    not a tree, or one that does not cover every counted unit.
    """
    dir_path = Path(dir_path)
    source, levels, declared = _read_election(dir_path / election_file_name)
    tally = _read_tally(dir_path / tally_file_name, levels)
    hierarchies = tuple(
        _read_hierarchy(dir_path / f"{name}.csv", name, hierarchy_levels)
        for name, hierarchy_levels in declared.items()
    )
    logger.info(
        "%s: read %d tally rows, %d hierarchies", dir_path, len(tally), len(hierarchies)
    )
    try:
        return PopularVote(source=source, tally=tally, hierarchies=hierarchies)
    except ValidationError as e:
        raise ValueError(f"{dir_path}: {e}") from e
