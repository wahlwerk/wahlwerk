"""Reader for normalised election bundles, as kept in wahlwerk-data.

A bundle is how wahlwerk-data stores a :class:`PopularVote`; the word names the files
on disk, never the model. Each bundle sits under :data:`ELECTIONS_DIR` at the path its key spells
out, one directory per segment: ``de.landtag.st.2026`` is
``elections/de/landtag/st/2026/`` (see :func:`resolve_election_dir`).

A bundle is a directory holding, by default, :data:`ELECTION_FILE`, :data:`TALLY_FILE`,
:data:`OPTIONS_FILE` and one file per hierarchy. ``election.toml`` carries the format
version, the source, the hierarchies and any kinds beside the built-in ones::

    schema = 4

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

    [hierarchies.electoral]
    levels = ["land", "wahlkreis"]

    [hierarchies.administrative]
    levels = ["land", "kreis", "gemeinde"]

    [kinds.blank]
    counts = "votes"

    [[lots]]
    section = "erststimme"
    unit = "de.st.wk.017"
    candidates = ["de.st.wk.017.mueller", "de.st.wk.017.schulz"]
    winners = ["de.st.wk.017.schulz"]
    source = "Niederschrift des Kreiswahlausschusses vom 10. September 2026"

From schema 4 (decision 0009) a unit id names only its unit
(``de.st.gem.15081026.wbz.000001``), and every grouping of units is a hierarchy, the
electoral one included: a law names the hierarchy it counts along, by default
``electoral``, so Wahlkreise drawn by another law version are another hierarchy, not
other ids. ``options.csv`` (:data:`OPTIONS_COLUMNS`) lists every option the tally counts
votes for and the party it stands for, blank for none.

In schemas 2 and 3, ``[levels]`` is the electoral hierarchy, spelled in the unit ids:
each level and the number of dotted segments in its ids, broadest first (see
:class:`Level`). Every row must name a listed level and have its depth.

Each ``[hierarchies.<name>]`` table declares an alternative hierarchy with its own
levels, broadest first; its units are in ``<name>.csv`` in the bundle, with exactly the
columns in :data:`HIERARCHY_COLUMNS`: every unit, its level, and the unit it lies in
(blank at the broadest level). It must cover every unit the tally counts. The table is
optional.

Each ``[kinds.<name>]`` table declares a kind the tally counts beside the built-in ones
(``votes``, ``invalid``, ``eligible``, ``voters``): whether its rows count ``votes`` or
``people``, and with ``has_option = true`` that they name an option (see :class:`Kind`).
The tables are optional; a row of a kind neither built in nor declared is rejected.

Each ``[[lots]]`` table records a tie decided by a lot actually drawn (see :class:`Lot`):
the section, the unit (blank for none), every candidate, the winners and, optionally, the
record of the draw. Lots are optional and rare.

Schema 1 has neither: its tally records no levels, and summing it needs the depth
given. Schemas 1 and 2 name what a vote counts for in three columns, ``party``,
``candidate`` and ``option`` (:data:`LEGACY_TALLY_COLUMNS`); schema 3 in one, ``option``,
with the option's ``party`` beside it on every row (:data:`SCHEMA_3_TALLY_COLUMNS`). An
older row is read as schema 3 reads it: its option is the answer if it names one, else
the candidate, else the party. The parties the rows of schemas 1 to 3 name become the
tally's options; an option named with two parties is rejected.

``tally.csv`` is the long vote table, one :class:`TallyRow` per line, with exactly the
columns of its schema, from schema 4 :data:`TALLY_COLUMNS`. A blank cell is an absent value (``None``), never an
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
from wahlwerk.vote.popular.lot import Lot
from wahlwerk.vote.popular.popular_vote import PopularVote, Source
from wahlwerk.vote.popular.tally import Kind, Level, Option, Tally, TallyKind, TallyRow

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

__all__ = [
    "ELECTIONS_DIR",
    "ELECTION_FILE",
    "HIERARCHY_COLUMNS",
    "LEGACY_TALLY_COLUMNS",
    "OPTIONS_COLUMNS",
    "OPTIONS_FILE",
    "SCHEMA",
    "SCHEMAS",
    "SCHEMA_3_TALLY_COLUMNS",
    "TALLY_COLUMNS",
    "TALLY_FILE",
    "read_bundle",
    "resolve_election_dir",
]

logger = logging.getLogger(__name__)

SCHEMA = 4
"""The schema version of bundles this engine writes: the current format."""

SCHEMAS = frozenset({1, 2, 3, SCHEMA})
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
    "option",
    "count",
)
"""The header of ``tally.csv``, in order: the fields of :class:`TallyRow`."""

SCHEMA_3_TALLY_COLUMNS = (
    "unit",
    "level",
    "kind",
    "section",
    "channel",
    "option",
    "party",
    "count",
)
"""The header of ``tally.csv`` in schema 3, each option's party on every row; read into
the rows and the tally's options."""

OPTIONS_FILE = "options.csv"
"""The file in a schema 4 bundle listing every option and the party it stands for."""

OPTIONS_COLUMNS = ("option", "party")
"""The header of ``options.csv``, in order: the fields of :class:`Option`."""

LEGACY_TALLY_COLUMNS = (
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
"""The header of ``tally.csv`` in schemas 1 and 2, read and converted to the current rows."""

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


def _parse_row(
    cells: list[str], columns: tuple[str, ...] = TALLY_COLUMNS
) -> tuple[TallyRow, str | None]:
    """Build a row from its cells, and the party it names in schemas 1 to 3 (``None``
    from schema 4); a blank cell is an absent value, never ``""``."""
    fields: dict[str, Any] = {
        column: cell for column, cell in zip(columns, cells) if cell != ""
    }
    if columns == LEGACY_TALLY_COLUMNS:
        # The option is the answer, else the candidate, else the party; the party stays.
        answer, candidate = fields.pop("option", None), fields.pop("candidate", None)
        option = answer or candidate or fields.get("party")
        if option is not None:
            fields["option"] = option
    if "kind" not in fields:
        raise ValueError("kind is blank")
    if "count" not in fields:
        raise ValueError("count is blank")
    fields["count"] = int(fields["count"])
    party = fields.pop("party", None)
    return TallyRow.model_validate(fields), party


def _read_election(
    file_path: Path,
) -> tuple[int, Source, tuple[Level, ...], dict[str, tuple[str, ...]], tuple[Kind, ...], tuple[Lot, ...]]:
    """The source, levels, declared hierarchies, kinds and lots of a bundle, after checking its
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
    levels = raw.pop("levels", None) if 2 <= schema <= 3 else None
    hierarchies = raw.pop("hierarchies", {}) if schema >= 2 else {}
    kinds = raw.pop("kinds", {})
    lots = raw.pop("lots", [])
    if schema >= 4 and "levels" in raw:
        raise ValueError(
            f"{file_path}: schema {schema} has no [levels]; the ids name only their unit, "
            "and the electoral hierarchy is [hierarchies.electoral]"
        )
    if raw:
        raise ValueError(f"{file_path}: unknown keys {sorted(raw)}")
    # Bad file content, not a bad argument: one exception type for every format error.
    if not isinstance(source, dict):
        raise ValueError(f"{file_path}: expected a [source] table")  # noqa: TRY004
    if 2 <= schema <= 3 and not isinstance(levels, dict):
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
    return (
        schema,
        parsed_source,
        parsed_levels,
        _declared_hierarchies(file_path, hierarchies),
        _declared_kinds(file_path, kinds),
        _recorded_lots(file_path, lots),
    )


def _recorded_lots(file_path: Path, raw: object) -> tuple[Lot, ...]:
    """Each ``[[lots]]`` table as a :class:`Lot`."""
    if not isinstance(raw, list) or not all(isinstance(table, dict) for table in raw):
        raise ValueError(f"{file_path}: expected [[lots]] tables")
    lots = []
    for number, table in enumerate(raw, start=1):
        try:
            lots.append(Lot.model_validate(table))
        except ValidationError as e:
            raise ValueError(f"{file_path}: lot {number}: {e}") from e
    return tuple(lots)


def _declared_kinds(file_path: Path, raw: object) -> tuple[Kind, ...]:
    """Each ``[kinds.<name>]`` table as a :class:`Kind`."""
    if not isinstance(raw, dict):
        raise ValueError(f"{file_path}: expected [kinds.<name>] tables")  # noqa: TRY004
    kinds = []
    for name, table in raw.items():
        if not isinstance(table, dict):
            raise ValueError(f"{file_path}: kinds.{name}: expected a table")  # noqa: TRY004
        try:
            kinds.append(Kind.model_validate({"name": name, **table}))
        except ValidationError as e:
            raise ValueError(f"{file_path}: kinds.{name}: {e}") from e
    return tuple(kinds)


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


def _read_tally(
    file_path: Path,
    levels: tuple[Level, ...],
    schema: int = SCHEMA,
    kinds: tuple[Kind, ...] = (),
) -> Tally:
    columns = (
        TALLY_COLUMNS if schema >= 4 else SCHEMA_3_TALLY_COLUMNS if schema == 3 else LEGACY_TALLY_COLUMNS
    )
    declared = {kind.name: kind for kind in kinds}
    rows = []
    parties: dict[str, str | None] = {}  # schemas 1 to 3: each option's party, from its rows
    with _require(file_path).open(encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if header is None or tuple(header) != columns:
            raise ValueError(
                f"{file_path}: header {header!r} is not {','.join(columns)}"
            )
        for cells in reader:
            line = reader.line_num
            if len(cells) != len(columns):
                raise ValueError(
                    f"{file_path}: line {line}: {len(cells)} cells, "
                    f"expected {len(columns)}"
                )
            try:
                row, party = _parse_row(cells, columns)
                if (
                    schema <= 3
                    and row.option is not None
                    and parties.setdefault(row.option, party) != party
                ):
                    raise ValueError(
                        f"option {row.option!r} stands for {parties[row.option]!r} and {party!r}"
                    )
                if not isinstance(row.kind, TallyKind):
                    # Checked here as well as by the tally, so the error names the line.
                    if row.kind not in declared:
                        raise ValueError(
                            f"kind {row.kind!r} is neither built in nor declared in [kinds]"
                        )
                    declared[row.kind].check(row)
                rows.append(row)
            except ValueError as e:  # ValidationError is a ValueError
                raise ValueError(f"{file_path}: line {line}: {e}") from e
    if schema >= 4:
        options = _read_options(file_path.with_name(OPTIONS_FILE))
    else:
        options = tuple(Option(option=o, party=p) for o, p in parties.items())
    try:
        return Tally(rows=tuple(rows), levels=levels, kinds=kinds, options=options)
    except ValidationError as e:
        raise ValueError(f"{file_path}: {e}") from e


def _read_options(file_path: Path) -> tuple[Option, ...]:
    options = []
    with _require(file_path).open(encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if header is None or tuple(header) != OPTIONS_COLUMNS:
            raise ValueError(f"{file_path}: header {header!r} is not {','.join(OPTIONS_COLUMNS)}")
        for cells in reader:
            line = reader.line_num
            if len(cells) != len(OPTIONS_COLUMNS):
                raise ValueError(
                    f"{file_path}: line {line}: {len(cells)} cells, expected {len(OPTIONS_COLUMNS)}"
                )
            fields = {column: cell for column, cell in zip(OPTIONS_COLUMNS, cells) if cell != ""}
            try:
                options.append(Option.model_validate(fields))
            except ValidationError as e:
                raise ValueError(f"{file_path}: line {line}: {e}") from e
    return tuple(options)


def read_bundle(
    dir_path: str | Path,
    election_file_name: str = ELECTION_FILE,
    tally_file_name: str = TALLY_FILE,
) -> PopularVote:
    """Read the popular vote stored in a bundle directory: its source from
    ``election_file_name``, its tally from ``tally_file_name``, in file order.

    Alternative hierarchies are read from ``<name>.csv`` beside them.

    Raises ``ValueError`` naming the file for a missing file, an unsupported schema, an
    unknown key, a missing or malformed ``[levels]``, ``[hierarchies]``, ``[kinds]`` or ``[[lots]]`` table, a wrong
    header, a row that :class:`TallyRow` rejects, a row of a kind not declared, a row whose level or depth
    ``[levels]`` does not allow, two rows that count the same thing, a hierarchy that is
    not a tree, or one that does not cover every counted unit.
    """
    dir_path = Path(dir_path)
    schema, source, levels, declared, kinds, lots = _read_election(dir_path / election_file_name)
    tally = _read_tally(dir_path / tally_file_name, levels, schema, kinds)
    hierarchies = tuple(
        _read_hierarchy(dir_path / f"{name}.csv", name, hierarchy_levels)
        for name, hierarchy_levels in declared.items()
    )
    logger.info(
        "%s: read %d tally rows, %d hierarchies", dir_path, len(tally), len(hierarchies)
    )
    try:
        return PopularVote(source=source, tally=tally, hierarchies=hierarchies, lots=lots)
    except ValidationError as e:
        raise ValueError(f"{dir_path}: {e}") from e
