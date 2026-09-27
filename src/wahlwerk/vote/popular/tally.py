"""Vote counts: one row, and the long table of them.

A :class:`TallyRow` is an anonymous count of a popular vote in one unit, correct for any
secret ballot. A :class:`Tally` is the long table of rows. Rows of small units are summed
into larger ones (Wahlkreis, Land, Bund) with :meth:`Tally.sum_to`, which is why each row
names its ``unit`` and ``level``. Votes and the administrative
counts around them (Wahlberechtigte, Wähler) share one row type, so all of a vote's data
is one long table. An election and a referendum (Volksentscheid, Bürgerentscheid) share
it too: a vote counts for a party or candidate, or for an ``option`` such as ``ja``.
Chamber votes, secret or named, are not tallies; they belong in
:mod:`wahlwerk.vote.chamber`.
"""

from __future__ import annotations

from collections.abc import Callable
from enum import Enum
from typing import Any

from pydantic import Field, model_validator

from wahlwerk.ids import CandidateId, LevelName, PartyId, Slug, UnitId
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
    """Valid votes for a party, a candidate or an option, in one section."""
    INVALID = "invalid"
    """Spoiled or invalid votes (Ungültige), in one section."""
    ELIGIBLE = "eligible"
    """People eligible to vote (Wahlberechtigte)."""
    VOTERS = "voters"
    """People who cast a ballot (Wähler), i.e. turnout."""


class TallyRow(Model):
    """One row of the long vote table: one count in one unit.

    Which fields a row must set depends on ``kind``: a ``VOTES`` row names a section and
    either a recipient (a party, a candidate or both) or an option, never both; an
    ``INVALID`` row names a section and neither; ``ELIGIBLE`` and ``VOTERS`` rows count
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
    party: PartyId | None = Field(
        default=None,
        description=(
            "The party these votes count for, absent for an independent candidate and on "
            "every row that is not ``VOTES``."
        ),
    )
    candidate: CandidateId | None = Field(
        default=None,
        description="The candidate these votes count for, when known.",
    )
    option: Slug | None = Field(
        default=None,
        description=(
            "The answer these votes count for in a referendum, e.g. ``ja``, ``nein``, "
            "``vorlage-a``; meaning is law-defined. Absent when the votes count for a "
            "party or candidate, and on every row that is not ``VOTES``."
        ),
    )
    count: Count = Field(
        description="The number counted in this row.",
    )

    @model_validator(mode="after")
    def _check_kind(self) -> TallyRow:
        has_recipient = self.party is not None or self.candidate is not None
        has_option = self.option is not None
        counts_votes = self.kind in (TallyKind.VOTES, TallyKind.INVALID)
        where = (
            f"{self.kind.value} row in unit {self.unit!r} (section={self.section!r}, "
            f"party={self.party!r}, candidate={self.candidate!r}, option={self.option!r})"
        )
        if counts_votes and self.section is None:
            raise ValueError(f"{where} names no section")
        if not counts_votes and self.section is not None:
            raise ValueError(f"{where} counts people, so it must name no section")
        if self.kind is TallyKind.VOTES and has_recipient and has_option:
            raise ValueError(f"{where} names both a recipient and an option")
        if self.kind is TallyKind.VOTES and not (has_recipient or has_option):
            raise ValueError(f"{where} names neither a party, a candidate nor an option")
        if self.kind is not TallyKind.VOTES and (has_recipient or has_option):
            raise ValueError(f"{where} must name no party, candidate or option")
        return self

    @property
    def key(self) -> tuple[Any, ...]:
        """Every field but ``count``: what the row counts, and where."""
        return tuple(getattr(self, name) for name in _KEY_FIELDS)


_KEY_FIELDS = tuple(name for name in TallyRow.model_fields if name != "count")
"""The fields of :class:`TallyRow` that say what a row counts, i.e. all but ``count``."""


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

    @model_validator(mode="after")
    def _check_unique(self) -> Tally:
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

    def __len__(self) -> int:
        return len(self.rows)

    # ===========================================================
    # Views
    # ===========================================================
    def filter(self, **criteria: Any) -> Tally:
        """The rows whose fields equal every criterion, e.g.
        ``tally.filter(kind="votes", section="zweitstimme")``.

        ``kind`` may be a :class:`TallyKind` or its value; ``None`` selects rows where
        the field is absent (``channel=None``). Raises ``ValueError`` for a field that
        is not a tally field or is ``count``.
        """
        _check_fields(list(criteria))
        if "kind" in criteria:
            criteria["kind"] = TallyKind(criteria["kind"])
        return Tally(
            rows=tuple(
                row
                for row in self.rows
                if all(getattr(row, name) == value for name, value in criteria.items())
            ),
            levels=self.levels,
        )

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

        def by_prefix(unit: str) -> str:
            segments = unit.split(".")
            if len(segments) < depth:
                raise ValueError(
                    f"unit {unit!r} has {len(segments)} segments, fewer than depth {depth}"
                )
            return ".".join(segments[:depth])

        return self._sum(level, by_prefix, levels=self.levels)

    def _sum(
        self, level: str, unit_of: Callable[[str], str], levels: tuple[Level, ...]
    ) -> Tally:
        """The rows moved to ``unit_of(row.unit)`` at ``level``, and summed."""
        counts: dict[tuple[Any, ...], int] = {}
        for row in self.rows:
            fields = dict(zip(_KEY_FIELDS, row.key))
            fields["unit"] = unit_of(row.unit)
            fields["level"] = level
            key = tuple(fields.values())
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
