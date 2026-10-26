"""Counting: the valid votes of one section grouped by the units of a level and by
option or party, and summed (e.g. Sec. 31, 32 and 35 (2) LWG LSA: the Erststimmen per Wahlkreis,
the Zweitstimmen in the Land; Art. 42 (2) BayLWG: Erst- and Zweitstimmen together).

The step is a named composition of the operations on a tally (decision 0009): *Select*
the valid votes of its sections, *RollUp* to its level, *Relabel* several sections to
one, *Collapse* the channels, and lay the rows out as a table by option or by party."""

from __future__ import annotations

from pydantic import Field, model_validator

from wahlwerk.ids import LevelName, Slug
from wahlwerk.process.allocation.base import (
    Allocation,
    AllocationStep,
    Counts,
    GroupBy,
    counts_fact,
)
from wahlwerk.vote.popular.tally import Tally, TallyKind

__all__ = ["SumGroupBy"]


class SumGroupBy(AllocationStep):
    """Sum the valid votes of ``section``, grouped by the units of ``level`` and ``by``
    option or party: the table ``<section> by <level> × <by>``
    (``erststimme by wahlkreis × option``), a row per unit, a counter per column,
    channels (Urne and Brief) summed.

    With ``sections``, the votes of several sections are counted together as one,
    named ``section``: Art. 42 (2) BayLWG counts Erst- and Zweitstimmen as Gesamtstimmen,
    ``SumGroupBy(section="gesamtstimme", sections=("erststimme", "zweitstimme"),
    level="wahlkreis", by="party")``.

    Only valid votes are counted, so invalid votes and people are not in it. Grouped by
    option, each option's party is taken along, and an option recorded with two parties
    is refused; grouped by party, an option's votes go to its party, and votes for no
    party (an Einzelbewerber) are left out. Making a table again replaces it.

    The units are those of ``level`` in ``hierarchy``, by default ``electoral``: the law
    names the tree it counts along, so the Wahlkreise of another law version are
    another hierarchy, not other data.

    In terms of the operations on a tally: ``filter`` (Select), ``sum_to`` (RollUp),
    ``relabel`` of the sections (Relabel), ``collapse`` of the channel (Collapse), see
    :attr:`operations`.
    """

    section: Slug = Field(
        description="The vote to count, e.g. ``erststimme``; with ``sections``, the name the votes are counted under, e.g. ``gesamtstimme``.",
    )
    sections: tuple[Slug, ...] | None = Field(
        default=None,
        description=(
            "The sections counted together as ``section``, e.g. ``('erststimme', "
            "'zweitstimme')``; ``None`` counts ``section`` alone."
        ),
    )
    level: LevelName = Field(
        description="The level to group by, a level of ``hierarchy``, e.g. ``wahlkreis``.",
    )
    hierarchy: Slug = Field(
        default="electoral",
        description=(
            "The hierarchy the votes are counted along, as the popular vote names it, "
            "e.g. ``electoral`` (Land, Wahlkreis). A vote of bundle schema 2 or 3 has "
            "none: its ids spell it, and the tally's levels are used."
        ),
    )
    by: GroupBy = Field(
        description="What to count per unit: each ``option`` voted for, or each ``party``; always stated.",
    )

    @model_validator(mode="after")
    def _check_sections(self) -> SumGroupBy:
        if self.sections is not None:
            if len(self.sections) < 2:
                raise ValueError(f"sections {self.sections} count one section; give it as section alone")
            if len(set(self.sections)) != len(self.sections):
                raise ValueError(f"sections {self.sections} list a section more than once")
        return self

    @property
    def counted(self) -> tuple[str, ...]:
        """The sections whose votes are counted: ``sections``, or ``section`` alone."""
        return self.sections if self.sections is not None else (self.section,)

    @property
    def operations(self) -> tuple[tuple[str, str], ...]:
        """The operations on the tally this step is made of, in order, each as
        (operation, what it is applied to), e.g. ``("RollUp", "wahlkreis")``."""
        steps = [
            ("RollUp", f"{self.level} of {self.hierarchy}"),
            ("Select", f"votes of {', '.join(self.counted)}"),
        ]
        if self.sections is not None:
            steps.append(("Relabel", f"{' + '.join(self.sections)} -> {self.section}"))
        steps.append(("Collapse", "channel"))
        if self.by == "party":
            steps.append(("Relabel", "option -> party"))
        return tuple(steps)

    @property
    def inputs(self) -> dict[str, str]:
        return {"tally": "tally"}

    @property
    def writes(self) -> frozenset[str]:
        return frozenset({counts_fact(self.section, self.level, self.by)})

    def _rolled_up(self, allocation: Allocation) -> Tally:
        """The tally summed to ``level`` along ``hierarchy``; for a vote that records no
        such hierarchy, along its ids, when its levels list ``level`` (schemas 2 and 3)."""
        tally = allocation.tally
        hierarchy = allocation.hierarchy(self.hierarchy)
        if hierarchy is not None:
            return tally.sum_to(self.level, hierarchy=hierarchy)
        if any(level.name == self.level for level in tally.levels):
            return tally.sum_to(self.level)
        raise ValueError(
            f"{self!r}: the vote records no hierarchy {self.hierarchy!r}, and its ids spell "
            f"no level {self.level!r}; hierarchies: {[h.name for h in allocation.hierarchies]}"
        )

    def _apply(self, allocation: Allocation) -> Allocation:
        # RollUp first: a tally keeps its sums, so every law replayed on one vote sums it
        # once; Select, Relabel and Collapse then work on the few rows of the level.
        summed = self._rolled_up(allocation).filter(kind=TallyKind.VOTES, section=self.counted)
        if self.sections is not None:
            summed = summed.relabel("section", {name: self.section for name in self.sections})
        summed = summed.collapse("channel")
        rows: dict[str, dict[str, int]] = {}
        parties: dict[str, str | None] = {}
        for row in summed.rows:
            option = row.option
            assert option is not None  # a VOTES row always names its option
            party = summed.party_of(option)
            parties.setdefault(option, party)
            # Relabel(option -> party) as the table is laid out: by party, a column per
            # party, and votes for no party have no column.
            column = option if self.by == "option" else party
            if column is None:
                continue
            counter = rows.setdefault(row.unit, {})
            counter[column] = counter.get(column, 0) + row.count
        if self.by == "party":
            parties = {party: party for party in parties.values() if party is not None}
        table = Counts(
            section=self.section,
            level=self.level,
            by=self.by,
            rows=tuple((unit, tuple(counter.items())) for unit, counter in rows.items()),
            parties=tuple(parties.items()),
        )
        others = tuple(t for t in allocation.counts if t.fact != table.fact)
        return allocation.with_values(counts=(*others, table))
