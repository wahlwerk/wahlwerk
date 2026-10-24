"""The working record of an allocation, and the steps and protocols that build it.

An allocation turns the tally of a popular vote into seats under an electoral law. The
law is an :data:`AllocationProtocol`, an ordered tuple of :class:`AllocationStep`; each
step reads facts from the :class:`Allocation` and adds or replaces others, e.g. the
votes summed per Wahlkreis, then the Wahlkreis winners. The allocation exists only
while the result is derived, so it lives here and not in ``state``.

Every step declares the facts it reads and writes. :func:`check_protocol` walks a
protocol and refuses one that reads a fact before any step writes it, so a law written
in the wrong order fails when it is checked, not halfway through a run; each step checks
its own facts again when applied.

Facts are named by strings: ``tally`` (the input); a table of counts is named by
what it counts and by what: ``<section> by <level> × <by>`` (the valid votes of one
section per unit and per option or party, e.g. ``erststimme by wahlkreis × option``, a
:class:`Counts` made by :class:`~wahlwerk.process.allocation.count.SumGroupBy`);
``eligible parties of <section>`` (the parties past the threshold of one vote, e.g.
``eligible parties of zweitstimme``); and one per optional field of :class:`Allocation`,
named like it: ``unit_mandates``, ``chamber_size``, ``minimum_mandates``, ``seats_to_apportion``, ``entitlement``, ``list_seats``,
``overhang``, ``chamber``.

Steps that belong together, one feeding the next, can be written as one step: a
:class:`~wahlwerk.process.allocation.sequence.StepSequence`. Which step depends on which
follows from the facts alone (:mod:`~wahlwerk.process.allocation.flow`); it is never
declared.
"""

from __future__ import annotations

import logging
from abc import abstractmethod
from typing import Any, Literal

from pydantic import Field, model_validator

from wahlwerk.apportionment.result import Apportionment
from wahlwerk.apportionment.tie import Tie
from wahlwerk.ids import LevelName, OptionId, PartyId, Slug, UnitId
from wahlwerk.model import Count, Model, Seats
from wahlwerk.state.chamber import Chamber
from wahlwerk.vote.popular.tally import Tally

__all__ = [
    "INPUT_FACTS",
    "OPTIONAL_FACTS",
    "Allocation",
    "AllocationProtocol",
    "AllocationStep",
    "Counts",
    "GroupBy",
    "UnitResult",
    "check_protocol",
    "counts_fact",
    "eligible_fact",
    "outside_reads",
]

logger = logging.getLogger(__name__)

INPUT_FACTS = frozenset({"tally"})
"""The facts every allocation starts with."""

OPTIONAL_FACTS = (
    "unit_mandates",
    "caucus_size",
    "chamber_size",
    "minimum_mandates",
    "seats_to_apportion",
    "entitlement",
    "list_seats",
    "overhang",
    "chamber",
)
"""The facts held by an optional field of :class:`Allocation` of the same name."""


GroupBy = Literal["option", "party"]
"""What a table of counts has a column for: each ``option`` voted for, or each ``party``
(its options' votes added up; votes for no party left out)."""


def counts_fact(section: str, level: str, by: str = "option") -> str:
    """The name of the table of ``section``'s valid votes per unit of ``level`` and per
    ``by``: ``<section> by <level> × <by>``, e.g. ``erststimme by wahlkreis × option``,
    ``zweitstimme by land × party``."""
    return f"{section} by {level} × {by}"


def eligible_fact(section: str, to: str = "party") -> str:
    """The name of the fact holding the parties (or options) past the threshold of
    ``section``: ``eligible parties of <section>``, e.g. ``eligible parties of
    zweitstimme``, or ``eligible options of <section>``."""
    return f"eligible {'parties' if to == 'party' else 'options'} of {section}"


class Counts(Model):
    """A table of valid votes: the votes cast in ``section``, one row per unit of
    ``level``, one column per ``by`` (each option, or each party), summed over channels;
    each row a counter. Its name says so: ``erststimme by wahlkreis × option``
    (:attr:`fact`).

    Grouped by option, a row is a unit's contest, and ``parties`` gives each option's
    party (``None`` for an Einzelbewerber or an answer): the party a seat the option wins
    goes to. Grouped by party, each column is a party, its options' votes added up, and
    votes for no party are not in it.
    """

    section: Slug = Field(description="The vote counted, e.g. ``erststimme``.")
    level: LevelName = Field(description="The level of the rows' units, e.g. ``wahlkreis``.")
    by: GroupBy = Field(default="option", description="What each column is: ``option`` or ``party``.")
    rows: tuple[tuple[UnitId, tuple[tuple[OptionId, Count], ...]], ...] = Field(
        default_factory=tuple,
        description="Per unit, in order of first appearance, each column and its votes.",
    )
    parties: tuple[tuple[OptionId, PartyId | None], ...] = Field(
        default_factory=tuple,
        description="Each column and the party it stands for (a party, itself).",
    )

    @property
    def fact(self) -> str:
        """The table's name: ``<section> by <level> × <by>``."""
        return counts_fact(self.section, self.level, self.by)

    def per_unit(self) -> dict[str, dict[str, int]]:
        """Each unit's row: its columns and their votes."""
        return {unit: dict(row) for unit, row in self.rows}

    def per_column(self) -> dict[str, int]:
        """The votes per column (option or party), summed over the units, in order of
        first appearance."""
        votes: dict[str, int] = {}
        for _, row in self.rows:
            for column, count in row:
                votes[column] = votes.get(column, 0) + count
        return votes

    def party_of(self, column: str) -> str | None:
        """The party ``column`` stands for; ``None`` for an Einzelbewerber or an answer.
        Raises ``KeyError`` for a column not counted."""
        for name, party in self.parties:
            if name == column:
                return party
        raise KeyError(f"{column!r} is not counted in {self.fact!r}")


class UnitResult(Model):
    """Who won one single-seat unit (a Wahlkreis), or who tied for it.

    The winner is an option of the unit's contest: a candidate where the tally names one,
    otherwise a party's nominee. ``party`` is the option's party, ``None`` for an
    Einzelbewerber. When the most votes are shared, ``tie`` names the options and no
    winner is set; the lot is drawn by an official and applied later.
    """

    unit: UnitId = Field(
        description="The unit, e.g. ``de.st.wk.001``.",
    )
    option: OptionId | None = Field(
        default=None,
        description="The winning option: a candidate id, or a party id; ``None`` on a tie.",
    )
    party: PartyId | None = Field(
        default=None,
        description="The winning option's party; ``None`` for an Einzelbewerber or on a tie.",
    )
    votes: Count = Field(
        description="The winner's votes, or each tied option's.",
    )
    tie: Tie | None = Field(
        default=None,
        description="The options with equally many votes, for one seat; ``None`` if decided.",
    )

    @model_validator(mode="after")
    def _check_winner_or_tie(self) -> UnitResult:
        if (self.option is None) == (self.tie is None):
            raise ValueError(
                f"unit {self.unit!r} needs a winner or a tie, not both or neither "
                f"(option={self.option!r}, tie={self.tie!r})"
            )
        if self.tie is not None and self.tie.seats != 1:
            raise ValueError(f"unit {self.unit!r} has one seat, but the tie is over {self.tie.seats}")
        return self

    @property
    def is_decided(self) -> bool:
        """Whether a winner is set, i.e. there is no tie."""
        return self.tie is None


class Allocation(Model):
    """What the law has established so far about one popular vote.

    Starts from the ``tally`` alone; each step adds facts. A fact not yet established is
    absent (``None``, or no entry in ``totals``), never a placeholder.
    """

    tally: Tally = Field(
        description="The tally of the popular vote, as recorded.",
    )
    counts: tuple[Counts, ...] = Field(
        default_factory=tuple,
        description="The tables of valid votes a step made, one per level and section, in the order made.",
    )
    unit_mandates: tuple[UnitResult, ...] | None = Field(
        default=None,
        description="The result of each single-seat unit; ``None`` until decided.",
    )
    passed: tuple[tuple[str, frozenset[OptionId]], ...] = Field(
        default_factory=tuple,
        description=(
            "Per threshold applied, the fact it established (``eligible parties of "
            "zweitstimme``) and the parties or options that passed, taking part in the "
            "proportional allocation; in the order established."
        ),
    )
    chamber_size: Seats | None = Field(
        default=None,
        description=(
            "The number of seats the chamber has at this stage: the size the law sets, then "
            "as raised for Mehrsitze or Ausgleich."
        ),
    )
    minimum_mandates: Seats | None = Field(
        default=None,
        description=(
            "The seats the chamber has at least, by law, e.g. 83; it stays when the chamber "
            "size is raised."
        ),
    )
    seats_to_apportion: Seats | None = Field(
        default=None,
        description="The seats apportioned among the eligible parties' lists and Wahlkreise.",
    )
    entitlement: Apportionment | None = Field(
        default=None,
        description="The seats each eligible party is entitled to in total.",
    )
    list_seats: tuple[tuple[PartyId, Seats], ...] | None = Field(
        default=None,
        description="The seats each eligible party fills from its list, after its Wahlkreis seats.",
    )
    caucus_size: Seats | None = Field(
        default=None,
        description="The seats a party needs for a caucus, as a law measures it (Sec. 35 (8a) LWG LSA).",
    )
    overhang: tuple[tuple[PartyId, Seats], ...] | None = Field(
        default=None,
        description=(
            "The Wahlkreis seats each party won beyond its entitlement (Überhang, "
            "Mehrsitze), for the parties that have any."
        ),
    )
    chamber: Chamber | None = Field(
        default=None,
        description="The chamber the allocation forms, its last fact.",
    )

    @model_validator(mode="after")
    def _check_totals(self) -> Allocation:
        tables = [table.fact for table in self.counts]
        if len(set(tables)) != len(tables):
            raise ValueError(f"allocation holds a table more than once: {tables}")
        established = [fact for fact, _ in self.passed]
        if len(set(established)) != len(established):
            raise ValueError(f"allocation holds a threshold's result more than once: {established}")
        return self

    @property
    def facts(self) -> frozenset[str]:
        """The names of the facts established so far."""
        facts = set(INPUT_FACTS)
        facts.update(table.fact for table in self.counts)
        facts.update(fact for fact, _ in self.passed)
        facts.update(name for name in OPTIONAL_FACTS if getattr(self, name) is not None)
        return frozenset(facts)

    def unit_wins(self) -> dict[str, int]:
        """The Wahlkreise each party won, from ``unit_mandates``. Raises ``ValueError`` if
        they are not decided yet, or a tie in one is still to be decided by lot."""
        if self.unit_mandates is None:
            raise ValueError("the Wahlkreise are not decided yet")
        tied = [d.unit for d in self.unit_mandates if not d.is_decided]
        if tied:
            raise ValueError(f"Wahlkreise {tied} are tied; the lot must be applied first")
        wins: dict[str, int] = {}
        for result in self.unit_mandates:
            if result.party is not None:
                wins[result.party] = wins.get(result.party, 0) + 1
        return wins

    def count(self, section: str, level: str, by: str = "option") -> Counts:
        """The table ``<section> by <level> × <by>``; raises ``KeyError`` naming it if
        no step made it."""
        fact = counts_fact(section, level, by)
        for table in self.counts:
            if table.fact == fact:
                return table
        raise KeyError(f"allocation has no table {fact!r}; made: {[t.fact for t in self.counts]}")

    def eligible(self, section: str, to: str = "party") -> frozenset[str]:
        """The parties (or, with ``to="option"``, the options) past the threshold of
        ``section``; raises ``KeyError`` naming the fact if no such threshold was
        applied."""
        fact = eligible_fact(section, to)
        for name, passed in self.passed:
            if name == fact:
                return passed
        raise KeyError(f"allocation has no {fact!r}; applied: {[n for n, _ in self.passed]}")

    def with_values(self, **changes: Any) -> Allocation:
        """This allocation with ``changes`` in place of its fields, validated."""
        return type(self).model_validate({**dict(self), **changes})


class AllocationStep(Model):
    """One rule of an electoral law: an allocation in, an allocation out.

    A step never computes with a formula of its own: every function of
    ``wahlwerk.calc`` it needs is called by a core concept it holds (a method, a
    threshold, a quota, a :class:`~wahlwerk.apportionment.deduction.Deduction`), which
    the step hands plain numbers. A step is a function of the facts it reads: :attr:`inputs` names each argument and
    the fact it takes (``votes`` takes ``erststimme by wahlkreis × option``), its fields are
    its settings, and :attr:`writes` are its results. Subclasses implement :meth:`_apply`
    and declare :attr:`inputs` (or, for a step holding others, :attr:`reads` directly)
    and :attr:`writes` (and :attr:`optional_reads`, facts used when present). Callable,
    so ``step(allocation)`` is ``step.apply(allocation)``.
    """

    citation: str | None = Field(
        default=None,
        description=(
            "The provision this step follows, e.g. ``Sec. 35 (3)`` of its own law or "
            "``Art. 20 (2) Verf. M-V``; ``None`` where none is recorded."
        ),
    )

    @property
    def inputs(self) -> dict[str, str]:
        """The step's arguments: each name and the fact it takes, e.g.
        ``{"votes": "erststimme by wahlkreis × option"}``."""
        return {}

    @property
    def reads(self) -> frozenset[str]:
        """The facts this step needs: those its :attr:`inputs` take."""
        return frozenset(self.inputs.values())

    @property
    @abstractmethod
    def writes(self) -> frozenset[str]:
        """The facts this step establishes or replaces."""

    @property
    def optional_reads(self) -> frozenset[str]:
        """Facts this step uses when they are established, and does without otherwise."""
        return frozenset()

    @property
    def passes(self) -> dict[str, tuple[tuple[str, str], ...]]:
        """What the step hands each core concept it holds, by field: the arguments the
        concept is called with, in words and in terms of the step's own arguments, e.g.
        ``{"method": (("seats", "1"),)}``. A step calls no function of
        ``wahlwerk.calc`` itself: only the concepts it holds do. Shown by
        :func:`wahlwerk.process.allocation.flow.describe` above the functions; the
        concept's own settings come from the concept."""
        return {}

    @abstractmethod
    def _apply(self, allocation: Allocation) -> Allocation:
        """The allocation with this step's facts, given that its reads are established."""

    def apply(self, allocation: Allocation) -> Allocation:
        """Apply this step. Raises ``ValueError`` naming the step if a fact it reads is
        missing, or if it did not establish every fact it writes."""
        missing = self.reads - allocation.facts
        if missing:
            raise ValueError(f"{self!r} reads {sorted(missing)}, which are not established")
        logger.debug("applying %r", self)
        result = self._apply(allocation)
        unwritten = self.writes - result.facts
        if unwritten:
            raise ValueError(f"{self!r} did not establish {sorted(unwritten)}")
        return result

    def __call__(self, allocation: Allocation) -> Allocation:
        return self.apply(allocation)


AllocationProtocol = tuple[AllocationStep, ...]
"""An electoral law as an ordered protocol of allocation steps, applied first to last."""


def outside_reads(steps: AllocationProtocol, *, optional: bool = False) -> frozenset[str]:
    """The facts ``steps`` read that no earlier one of them writes: what they need from
    outside when applied in order (with ``optional``, their optional reads instead)."""
    written: set[str] = set()
    needed: set[str] = set()
    for step in steps:
        needed |= (step.optional_reads if optional else step.reads) - written
        written |= step.writes
    return frozenset(needed)


def written_by(steps: AllocationProtocol) -> frozenset[str]:
    """Every fact one of ``steps`` writes."""
    return frozenset().union(*(step.writes for step in steps))


def check_protocol(
    protocol: AllocationProtocol, established: frozenset[str] = INPUT_FACTS
) -> frozenset[str]:
    """Check that each step of ``protocol`` reads only facts established before it,
    starting from ``established``; return the facts established at the end.

    Raises ``ValueError`` naming the first step that reads a missing fact, and its
    position.
    """
    facts = set(established)
    for position, step in enumerate(protocol, start=1):
        missing = step.reads - facts
        if missing:
            # The kind and the paragraph name the step; its repr can hold a whole law.
            named = getattr(step, "name", None)  # a sequence's name is its kind
            name = (named if isinstance(named, str) else type(step).__name__) + (f" ({step.citation})" if step.citation else "")
            raise ValueError(
                f"step {position} {name} reads {sorted(missing)}, "
                f"which no earlier step writes; established: {sorted(facts)}"
            )
        facts |= step.writes
    return frozenset(facts)
