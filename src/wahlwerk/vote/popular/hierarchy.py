"""Alternative hierarchies over the units of a tally, for analysis.

A tally's unit ids follow one hierarchy, its *main* one: the one the law counts along,
e.g. Wahlbezirk, Wahlkreis, Land. Its levels are :attr:`Tally.levels`, and a unit lies
in another when that one's id is a prefix of its own.

Other hierarchies cross the main one. Administratively, a Wahlbezirk lies in a Gemeinde,
a Gemeinde in a Kreis; but Halle (Saale) spans four Wahlkreise, so no prefix of a
Wahlbezirk id is its Gemeinde. A :class:`Hierarchy` records such a tree explicitly: every
unit it covers, with its level and its parent. It sits beside the main hierarchy and
never replaces it; the law is never evaluated along it.
"""

from __future__ import annotations

from pydantic import Field, model_validator

from wahlwerk.ids import LevelName, Slug, UnitId
from wahlwerk.model import Model

__all__ = ["Hierarchy", "HierarchyUnit"]


class HierarchyUnit(Model):
    """One unit of a :class:`Hierarchy`, and the unit it lies in."""

    unit: UnitId = Field(
        description="The unit, e.g. ``de.st.gem.15002000``.",
    )
    level: LevelName = Field(
        description="Which kind of unit ``unit`` is, e.g. ``gemeinde``.",
    )
    parent: UnitId | None = Field(
        default=None,
        description="The unit it lies in; ``None`` only for a unit of the broadest level.",
    )


class Hierarchy(Model):
    """A tree of units beside a tally's main hierarchy, e.g. Land, Kreis, Gemeinde.

    ``levels`` are the hierarchy's own levels, broadest first. Its units are those
    levels' units, plus the tally's units it covers (Wahlbezirke), whose levels belong
    to the main hierarchy and which lie in a unit of the narrowest level. Every parent
    is a unit of the hierarchy, one level broader.
    """

    name: Slug = Field(
        description="The name of the hierarchy, e.g. ``administrative``.",
    )
    levels: tuple[LevelName, ...] = Field(
        min_length=1,
        description="The hierarchy's own levels, broadest first, e.g. ``('land', 'kreis', 'gemeinde')``.",
    )
    units: tuple[HierarchyUnit, ...] = Field(
        default_factory=tuple,
        description="Every unit of the hierarchy with its parent, in file order.",
    )

    @model_validator(mode="after")
    def _check_tree(self) -> Hierarchy:
        where = f"hierarchy {self.name!r}"
        if len(set(self.levels)) != len(self.levels):
            raise ValueError(f"{where} lists a level more than once: {self.levels}")
        level_of: dict[str, str] = {}
        for entry in self.units:
            if entry.unit in level_of:
                raise ValueError(f"{where} lists unit {entry.unit!r} more than once")
            level_of[entry.unit] = entry.level
        for entry in self.units:
            if entry.level in self.levels:
                index = self.levels.index(entry.level)
                expected = self.levels[index - 1] if index else None
            else:
                expected = self.levels[-1]
            if expected is None:
                if entry.parent is not None:
                    raise ValueError(
                        f"{where}: unit {entry.unit!r} is at the broadest level "
                        f"{entry.level!r}, so it has no parent, not {entry.parent!r}"
                    )
                continue
            if entry.parent is None:
                raise ValueError(
                    f"{where}: unit {entry.unit!r} has no parent, expected one at {expected!r}"
                )
            if entry.parent not in level_of:
                raise ValueError(
                    f"{where}: unit {entry.unit!r} lies in {entry.parent!r}, "
                    "which is not a unit of the hierarchy"
                )
            if level_of[entry.parent] != expected:
                raise ValueError(
                    f"{where}: unit {entry.unit!r} ({entry.level}) lies in {entry.parent!r} "
                    f"({level_of[entry.parent]}), expected a unit at {expected!r}"
                )
        return self

    def units_at(self, level: str) -> dict[str, UnitId]:
        """Every unit that lies in a unit at ``level``, or is one, mapped to that unit:
        ``units_at("gemeinde")["de.st.wk.035.gem.15002000.wbz.000001"]`` is
        ``de.st.gem.15002000``. Units of broader levels are left out.

        Raises ``ValueError`` for a level that is not one of the hierarchy's.
        """
        if level not in self.levels:
            raise ValueError(
                f"hierarchy {self.name!r} has no level {level!r}; "
                f"expected one of {list(self.levels)}"
            )
        broader = set(self.levels[: self.levels.index(level)])
        parent_of = {entry.unit: entry.parent for entry in self.units}
        level_of = {entry.unit: entry.level for entry in self.units}
        found: dict[str, UnitId] = {}
        for entry in self.units:
            if entry.level in broader:
                continue
            unit: UnitId | None = entry.unit
            while unit is not None and level_of[unit] != level:
                unit = parent_of[unit]
            if unit is not None:
                found[entry.unit] = unit
        return found
