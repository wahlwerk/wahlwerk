"""One row of vote counts.

A :class:`TallyRow` is an anonymous count of a popular vote in one unit, correct for any
secret ballot. Rows of small units are summed into larger ones (Wahlkreis, Land, Bund),
which is why each row names its ``unit`` and ``level``. Votes and the administrative
counts around them (Wahlberechtigte, Wähler) share one row type, so all of a vote's data
is one long table. An election and a referendum (Volksentscheid, Bürgerentscheid) share
it too: a vote counts for a party or candidate, or for an ``option`` such as ``ja``.
Chamber votes, secret or named, are not tallies; they belong in
:mod:`wahlwerk.vote.chamber`.
"""

from __future__ import annotations

from enum import Enum

from pydantic import Field, model_validator

from wahlwerk.ids import CandidateId, LevelName, PartyId, Slug, UnitId
from wahlwerk.model import Count, Model

__all__ = ["TallyKind", "TallyRow"]


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
