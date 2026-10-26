"""Vote counts: one row, and the long table of them.

A :class:`TallyRow` is an anonymous count of a popular vote in one unit, correct for any
secret ballot. A :class:`Tally` is the long table of rows. Rows of small units are summed
into larger ones (Wahlkreis, Land, Bund) with :meth:`Tally.sum_to`, which is why each row
names its ``unit`` and ``level``. Votes and the administrative
counts around them (Wahlberechtigte, Wähler) share one row type, so all of a vote's data
is one long table. An election and a referendum (Volksentscheid, Bürgerentscheid) share
it too: every vote counts for an ``option``, what was voted for, be it a party, a
candidate or an answer such as ``ja``; ``party`` says which party, if any, the option
stands for.
Chamber votes, secret or named, are not tallies; they belong in
:mod:`wahlwerk.vote.chamber`.

The way up from the rows to what a law decides on is a short sequence of operations on
the tally, each returning a tally (decision 0009): *Select* (:meth:`Tally.filter`),
*RollUp* (:meth:`Tally.sum_to`), *Relabel* (:meth:`Tally.relabel`, members of one field
merged or renamed, e.g. Erst- and Zweitstimmen counted as Gesamtstimmen) and *Collapse*
(:meth:`Tally.collapse`, a field summed away, e.g. Urne and Brief). Laws differ in the
sequence, not in the operations; what is not a sum (a threshold, an apportionment) is a
step of the law.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from enum import Enum
from typing import Any

from pydantic import Field, PrivateAttr, model_validator

from wahlwerk.ids import LevelName, OptionId, PartyId, Slug, UnitId
from wahlwerk.model import Count, Model
from wahlwerk.vote.popular.hierarchy import Hierarchy

__all__ = ["Level", "Tally", "TallyKind", "TallyRow"]


class TallyKind(Enum):
    """What a :class:`TallyRow` counts.

    Gültige is not a kind: valid votes are the sum of the ``VOTES`` rows, not a stored
    fact. ``VOTERS`` is one: voters equal valid plus invalid votes per section only under
    some laws (the Bundestag's), not where a voter has several votes (Hamburg, Bremen),
    so it is recorded, and a law can check it against the votes.
    """

    VOTES = "votes"
    """Valid votes for one option, in one section."""
    INVALID = "invalid"
    """Spoiled or invalid votes (Ungültige), in one section."""
    ELIGIBLE = "eligible"
    """People eligible to vote (Wahlberechtigte)."""
    VOTERS = "voters"
    """People who cast a ballot (Wähler), i.e. turnout."""


class TallyRow(Model):
    """One row of the long vote table: one count in one unit.

    Which fields a row must set depends on ``kind``: a ``VOTES`` row names a section and
    the option its votes count for, and the option's party where it has one; an
    ``INVALID`` row names a section and no option; ``ELIGIBLE`` and ``VOTERS`` rows count
    people, so they name no section either.
    """

    unit: UnitId = Field(
        description="The unit this row was counted in.",
    )
    level: LevelName = Field(
        description="Which kind of unit ``unit`` is.",
    )
    kind: TallyKind = Field(
        default=TallyKind.VOTES,
        description="What this row counts: valid votes, invalid votes, or people.",
    )
    section: Slug | None = Field(
        default=None,
        description=(
            "Which vote this row counts, e.g. ``erststimme``, ``zweitstimme``, or the "
            "question of a referendum, e.g. ``frage-1``, ``stichfrage``; meaning is "
            "law-defined, not fixed by the engine. ``None`` for rows counting people."
        ),
    )
    channel: Slug | None = Field(
        default=None,
        description=(
            "How the vote was cast, e.g. ``urne``, ``brief``; ``None`` when not recorded. "
            "Never a precomputed total across channels: that is a sum over rows, not a "
            "stored fact."
        ),
    )
    option: OptionId | None = Field(
        default=None,
        description=(
            "What these votes count for: a party (``cdu``, a Landesliste or a party's "
            "nominee whose name is not recorded), a candidate "
            "(``de.st.wk.002.einzelbewerber.1``) or an answer (``ja``, ``vorlage-a``); "
            "meaning is law-defined. Absent on every row that is not ``VOTES``."
        ),
    )
    party: PartyId | None = Field(
        default=None,
        description=(
            "The party the option stands for: the option itself when it is a party, the "
            "nominating party of a candidate. Absent for an Einzelbewerber, an answer, "
            "and on every row that is not ``VOTES``."
        ),
    )
    count: Count = Field(
        description="The number counted in this row.",
    )

    @model_validator(mode="after")
    def _check_kind(self) -> TallyRow:
        has_option = self.option is not None
        counts_votes = self.kind in (TallyKind.VOTES, TallyKind.INVALID)
        where = (
            f"{self.kind.value} row in unit {self.unit!r} (section={self.section!r}, "
            f"option={self.option!r}, party={self.party!r})"
        )
        if counts_votes and self.section is None:
            raise ValueError(f"{where} names no section")
        if not counts_votes and self.section is not None:
            raise ValueError(f"{where} counts people, so it must name no section")
        if self.kind is TallyKind.VOTES and not has_option:
            raise ValueError(f"{where} names no option")
        if self.kind is not TallyKind.VOTES and (has_option or self.party is not None):
            raise ValueError(f"{where} must name no option or party")
        return self

    @property
    def key(self) -> tuple[Any, ...]:
        """Every field but ``count``: what the row counts, and where."""
        return tuple(getattr(self, name) for name in _KEY_FIELDS)


_KEY_FIELDS = tuple(name for name in TallyRow.model_fields if name != "count")
"""The fields of :class:`TallyRow` that say what a row counts, i.e. all but ``count``."""


_RELABEL_FIELDS = ("section", "channel", "option", "party")
"""The fields :meth:`Tally.relabel` and :meth:`Tally.collapse` may change: what is
counted, not where (units move with :meth:`Tally.sum_to`) and not of what kind."""


def _check_fields(fields: tuple[str, ...] | list[str]) -> None:
    unknown = [name for name in fields if name not in _KEY_FIELDS]
    if unknown:
        raise ValueError(f"{unknown} are not tally fields; expected some of {list(_KEY_FIELDS)}")


class Level(Model):
    """One level of the units a tally names, and how deep its unit ids are.

    Unit ids are dotted with the narrowest scope last, so the depth says how many
    segments a unit of this level has: a Wahlkreis ``de.st.wk.001`` is 4 deep, a
    Wahlbezirk ``de.st.wk.001.gem.15081026.wbz.000001`` is 8. Two levels may share a
    depth (Wahlbezirk and Briefwahlbezirk). These are the levels of the main hierarchy;
    others sit beside it as a :class:`~wahlwerk.vote.popular.hierarchy.Hierarchy`.
    """

    name: LevelName = Field(
        description="The level, as rows name it in ``level``, e.g. ``wahlkreis``.",
    )
    depth: int = Field(
        ge=1,
        strict=True,
        description="The number of dotted segments in the id of a unit of this level.",
    )


class Tally(Model):
    """The long table of a popular vote: every :class:`TallyRow`, in order, and the
    levels its unit ids spell out.

    No two rows count the same thing: rows that agree in every field but ``count``
    would be counted twice when summed, so they are rejected. When ``levels`` is given,
    every row names a listed level, and its unit has that level's depth. Sums are
    derived here and never stored; :meth:`sum_to` rolls rows up into larger units,
    :meth:`sum_by` totals them by any fields.
    """

    rows: tuple[TallyRow, ...] = Field(
        default_factory=tuple,
        description="Every counted row, in file order.",
    )
    levels: tuple[Level, ...] = Field(
        default_factory=tuple,
        description=(
            "The levels of the units, broadest first, e.g. Land, Wahlkreis, Gemeinde, "
            "Wahlbezirk; empty when not recorded."
        ),
    )

    _checked_rows: tuple[TallyRow, ...] | None = PrivateAttr(default=None)
    """The rows the checks below passed for. Pydantic runs a model's "after" validators
    again whenever an existing instance passes through validation (every time an
    allocation step records a fact), and both checks walk every row. A tally is frozen,
    so once its checks pass they hold for good: they run once per instance. The rows
    themselves are kept, not a flag, because ``model_copy`` carries private attributes
    over to a copy that may hold other rows."""

    _sums: dict[tuple[str, int], tuple[tuple[TallyRow, ...], Tally]] = PrivateAttr(
        default_factory=dict
    )
    """The sums along the main hierarchy already made, by (level, depth), each with the
    rows it was made from (see ``_checked_rows``). A tally is frozen, so a sum never
    changes: every law replayed on one election sums it once."""

    @property
    def _is_checked(self) -> bool:
        return self._checked_rows is self.rows

    @model_validator(mode="after")
    def _check_unique(self) -> Tally:
        if self._is_checked:
            return self
        seen: set[tuple[Any, ...]] = set()
        for row in self.rows:
            if row.key in seen:
                raise ValueError(
                    f"tally counts {dict(zip(_KEY_FIELDS, row.key))} more than once"
                )
            seen.add(row.key)
        return self

    @model_validator(mode="after")
    def _check_levels(self) -> Tally:
        if self._is_checked:
            return self
        depths: dict[str, int] = {}
        for level in self.levels:
            if level.name in depths:
                raise ValueError(f"level {level.name!r} is listed more than once")
            depths[level.name] = level.depth
        if not depths:
            return self
        for row in self.rows:
            if row.level not in depths:
                raise ValueError(
                    f"row in unit {row.unit!r} names level {row.level!r}, "
                    f"not one of {list(depths)}"
                )
            segments = row.unit.count(".") + 1
            if segments != depths[row.level]:
                raise ValueError(
                    f"unit {row.unit!r} has {segments} segments, but level "
                    f"{row.level!r} is {depths[row.level]} deep"
                )
        return self

    @model_validator(mode="after")
    def _mark_checked(self) -> Tally:
        # Last of the validators: reached only when every check above has passed.
        self._checked_rows = self.rows
        return self

    def __len__(self) -> int:
        return len(self.rows)

    # ===========================================================
    # Views
    # ===========================================================
    def filter(self, **criteria: Any) -> Tally:
        """The rows whose fields equal every criterion, e.g.
        ``tally.filter(kind="votes", section="zweitstimme")``: the operation *Select*.

        A tuple, list or set selects rows whose field is any of its values
        (``section=("erststimme", "zweitstimme")``). ``kind`` may be a :class:`TallyKind`
        or its value; ``None`` selects rows where the field is absent (``channel=None``).
        Raises ``ValueError`` for a field that is not a tally field or is ``count``.
        """
        _check_fields(list(criteria))
        allowed: dict[str, frozenset[Any]] = {}
        for name, value in criteria.items():
            values = value if isinstance(value, (tuple, list, set, frozenset)) else (value,)
            if name == "kind":
                values = tuple(TallyKind(v) for v in values)
            allowed[name] = frozenset(values)
        return Tally(
            rows=tuple(
                row
                for row in self.rows
                if all(getattr(row, name) in values for name, values in allowed.items())
            ),
            levels=self.levels,
        )

    def relabel(self, field: str, mapping: Mapping[Any, Any]) -> Tally:
        """The rows with the members of ``field`` renamed by ``mapping``, and summed: the
        operation *Relabel*. Members not in ``mapping`` keep their name; several mapped to
        one name are merged, e.g. Erst- and Zweitstimmen counted together (Art. 42 (2)
        BayLWG):

        ``tally.relabel("section", {"erststimme": "gesamtstimme", "zweitstimme": "gesamtstimme"})``

        Rows that then agree in every field but ``count`` are summed into one, kept in
        order of first appearance, and ``levels`` are kept. Only what is counted can be
        relabelled (``section``, ``channel``, ``option``, ``party``); units move with
        :meth:`sum_to`. Raises ``ValueError`` for another field, or a relabelled row that
        is no longer a valid :class:`TallyRow` (a vote mapped to no option).
        """
        if field not in _RELABEL_FIELDS:
            raise ValueError(f"{field!r} cannot be relabelled; expected one of {list(_RELABEL_FIELDS)}")
        index = _KEY_FIELDS.index(field)

        def renamed(key: tuple[Any, ...]) -> tuple[Any, ...]:
            value = key[index]
            if value not in mapping:
                return key
            return (*key[:index], mapping[value], *key[index + 1 :])

        return self._merge(renamed, levels=self.levels)

    def collapse(self, *fields: str) -> Tally:
        """The rows with ``fields`` summed away (made absent), e.g.
        ``tally.collapse("channel")``, Urne and Brief together: the operation *Collapse*.

        Rows that then agree in every field but ``count`` are summed into one, kept in
        order of first appearance, and ``levels`` are kept. Only ``section``,
        ``channel``, ``option`` and ``party`` can be collapsed. Raises ``ValueError`` for
        no field, another field, or a row that is then no longer a valid
        :class:`TallyRow` (a vote without its section or option).
        """
        if not fields:
            raise ValueError("collapse needs at least one field")
        unknown = [name for name in fields if name not in _RELABEL_FIELDS]
        if unknown:
            raise ValueError(f"{unknown} cannot be collapsed; expected some of {list(_RELABEL_FIELDS)}")
        indices = {_KEY_FIELDS.index(name) for name in fields}

        def absent(key: tuple[Any, ...]) -> tuple[Any, ...]:
            return tuple(None if i in indices else value for i, value in enumerate(key))

        return self._merge(absent, levels=self.levels)

    def sum_to(
        self,
        level: LevelName,
        depth: int | None = None,
        *,
        hierarchy: Hierarchy | None = None,
    ) -> Tally:
        """The rows summed into the units of ``level``.

        Along the main hierarchy, unit ids are dotted with the narrowest scope last, so
        a unit's first segments name the unit it lies in:
        ``de.st.wk.001.gem.15081026.wbz.000001`` cut to its first 4 segments is the
        Wahlkreis ``de.st.wk.001``. The depth comes from ``levels``:
        ``tally.sum_to("wahlkreis")``. A tally that records no levels needs it given:
        ``tally.sum_to("wahlkreis", depth=4)``.

        Along another ``hierarchy``, each unit is looked up in it instead:
        ``tally.sum_to("gemeinde", hierarchy=administrative)`` sums Halle's Wahlbezirke
        into one Gemeinde across its four Wahlkreise. Its units are not prefixes of
        each other, so the result records no ``levels``.

        Rows that then agree in every field but ``count`` are summed into one, kept in
        order of first appearance; ``channel`` is kept, so Urne and Brief stay apart.
        Every row is summed as given: filter out rows that already are totals of others
        first, or they are counted twice. Raises ``ValueError`` for a level not listed
        in ``levels`` (or the hierarchy), a ``depth`` that contradicts it, is missing or
        is below 1, a ``depth`` given with a hierarchy, a unit with fewer segments than
        ``depth``, or a unit the hierarchy does not place in ``level``.
        """
        if hierarchy is not None:
            if depth is not None:
                raise ValueError("give a depth or a hierarchy, not both")
            units = hierarchy.units_at(level)

            def along_hierarchy(unit: str) -> str:
                if unit not in units:
                    raise ValueError(
                        f"hierarchy {hierarchy.name!r} places unit {unit!r} in no {level!r}"
                    )
                return units[unit]

            return self._sum(level, along_hierarchy, levels=())

        depth = self._depth_of(level, depth)
        cached = self._sums.get((level, depth))
        if cached is not None and cached[0] is self.rows:
            return cached[1]

        def by_prefix(unit: str) -> str:
            segments = unit.split(".")
            if len(segments) < depth:
                raise ValueError(
                    f"unit {unit!r} has {len(segments)} segments, fewer than depth {depth}"
                )
            return ".".join(segments[:depth])

        # A sum to a finer level already made holds the same counts in fewer rows, in
        # the same order of first appearance: cutting a cut id gives the same unit, so
        # summing that sum gives the same tally (the Land from the Wahlkreise, not from
        # 70,000 Wahlbezirk rows).
        finer = [
            summed
            for (_, finer_depth), (rows, summed) in self._sums.items()
            if rows is self.rows and finer_depth > depth
        ]
        source = min(finer, key=len) if finer else self
        result = source._sum(level, by_prefix, levels=self.levels)
        self._sums[(level, depth)] = (self.rows, result)
        return result

    def _sum(
        self, level: str, unit_of: Callable[[str], str], levels: tuple[Level, ...]
    ) -> Tally:
        """The rows moved to ``unit_of(row.unit)`` at ``level``, and summed."""
        unit_index = _KEY_FIELDS.index("unit")
        level_index = _KEY_FIELDS.index("level")

        def moved(key: tuple[Any, ...]) -> tuple[Any, ...]:
            changed = list(key)
            changed[unit_index] = unit_of(key[unit_index])
            changed[level_index] = level
            return tuple(changed)

        return self._merge(moved, levels=levels)

    def _merge(
        self, new_key: Callable[[tuple[Any, ...]], tuple[Any, ...]], levels: tuple[Level, ...]
    ) -> Tally:
        """Each row given ``new_key(row.key)``, and rows with the same key summed, in
        order of first appearance: the arithmetic of every operation that is a sum."""
        counts: dict[tuple[Any, ...], int] = {}
        for row in self.rows:
            key = new_key(row.key)
            counts[key] = counts.get(key, 0) + row.count
        return Tally(
            rows=tuple(
                TallyRow.model_validate({**dict(zip(_KEY_FIELDS, key)), "count": count})
                for key, count in counts.items()
            ),
            levels=levels,
        )

    def _depth_of(self, level: str, depth: int | None) -> int:
        """The depth to sum ``level`` to: from ``levels``, or ``depth`` when none are
        recorded."""
        if depth is not None and (isinstance(depth, bool) or not isinstance(depth, int)):
            raise TypeError(f"depth must be an int, got {type(depth).__name__}")
        listed: dict[str, int] = {lvl.name: lvl.depth for lvl in self.levels}
        if listed:
            if level not in listed:
                raise ValueError(f"level {level!r} is not one of {list(listed)}")
            if depth is not None and depth != listed[level]:
                raise ValueError(
                    f"depth {depth} contradicts level {level!r}, which is {listed[level]} deep"
                )
            return listed[level]
        if depth is None:
            raise ValueError(f"tally records no levels; give the depth of {level!r}")
        if depth < 1:
            raise ValueError(f"depth {depth} is below 1")
        return depth

    def sum_by(self, *fields: str) -> dict[Any, Count]:
        """The total count for each value of ``fields``, in order of first appearance.

        With one field the keys are its values (``{"afd": 575971, ...}``), with several
        they are tuples (``{("de.st.wk.001", "afd"): 20211, ...}``). Raises
        ``ValueError`` for no field, or a field that is not a tally field.
        """
        if not fields:
            raise ValueError("sum_by needs at least one field")
        _check_fields(fields)
        totals: dict[Any, Count] = {}
        for row in self.rows:
            values = tuple(getattr(row, name) for name in fields)
            key = values[0] if len(fields) == 1 else values
            totals[key] = totals.get(key, 0) + row.count
        return totals

    def total(self) -> Count:
        """The sum of every row's count."""
        return sum(row.count for row in self.rows)
