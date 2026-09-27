"""The composition of a body at a point in time."""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from html import escape
from typing import TYPE_CHECKING, Literal

from pydantic import Field, model_validator

from wahlwerk.ids import BodyId, PartyId
from wahlwerk.model import Model, Seats
from wahlwerk.party.party import Party, party_id_of
from wahlwerk.state.caucus import NON_ATTACHED, Caucus
from wahlwerk.state.mandate import Mandate
from wahlwerk.state.term import Term

if TYPE_CHECKING:
    from wahlwerk.process.caucus import CaucusProtocol

__all__ = ["Chamber"]

logger = logging.getLogger(__name__)


class Chamber(Model):
    """The mandates constituting a body at a point in time, and the caucuses over them.

    The mandates are the source of truth for the seats; the caucuses group those seats
    by position, and the chamber validates that the two agree. The body is not stored
    here: a chamber sits in a :class:`Term`, and the term knows its body. A chamber whose
    body is known but whose term details are not uses ``Term(body=...)`` with everything
    else left out.
    """

    term: Term | None = Field(
        default=None,
        description="The term during which the chamber sits; carries the body.",
    )
    mandates: tuple[Mandate, ...] = Field(
        default_factory=tuple,
        description="The mandates in the chamber; the source of truth for its seats.",
    )
    caucuses: tuple[Caucus, ...] = Field(
        default_factory=tuple,
        description="The caucuses, each grouping seats by their position in ``mandates``.",
    )
    minimum_mandates: Seats | None = Field(
        default=None,
        description="The number of seats the chamber has at least, by law, if known.",
    )
    are_caucuses_recorded: bool = Field(
        default=False,
        description=(
            "Whether caucus membership is on record even if there are no caucuses, so a "
            "filled seat in no caucus is known to be non-attached. Set by "
            "form_caucuses; a chamber with caucuses counts as recorded either way."
        ),
    )

    @model_validator(mode="after")
    def _check_mandates(self) -> Chamber:
        who = self._name() or "chamber"
        seen: set[str] = set()
        for mandate in self.mandates:
            if mandate.id in seen:
                raise ValueError(f"{who}: mandate {mandate.id!r} appears twice")
            seen.add(mandate.id)
        return self

    @model_validator(mode="after")
    def _check_caucuses(self) -> Chamber:
        who = self._name() or "chamber"
        by_id = {mandate.id: mandate for mandate in self.mandates}
        caucus_of: dict[str, str] = {}
        seen: set[str] = set()
        for caucus in self.caucuses:
            if caucus.id in seen:
                raise ValueError(f"{who}: caucus {caucus.id!r} appears twice")
            seen.add(caucus.id)
            if caucus.id == NON_ATTACHED:
                raise ValueError(
                    f"{who}: caucus id {NON_ATTACHED!r} is reserved for non-attached seats"
                )
            if not caucus.mandates:
                raise ValueError(f"{who}: caucus {caucus.id!r} has no seats")
            for mandate_id in sorted(caucus.mandates):
                if mandate_id not in by_id:
                    raise ValueError(
                        f"{who}: caucus {caucus.id!r} claims mandate {mandate_id!r}, "
                        "which is not in the chamber"
                    )
                if by_id[mandate_id].is_vacant:
                    raise ValueError(
                        f"{who}: caucus {caucus.id!r} claims vacant mandate {mandate_id!r}"
                    )
                if mandate_id in caucus_of:
                    raise ValueError(
                        f"{who}: mandate {mandate_id!r} is in both caucus "
                        f"{caucus_of[mandate_id]!r} and caucus {caucus.id!r}"
                    )
                caucus_of[mandate_id] = caucus.id
        return self

    # ===========================================================
    # Constructors
    # ===========================================================
    @classmethod
    def from_seats(
        cls,
        seats: Mapping[Party | str | None, Seats],
        *,
        term: Term | None = None,
        minimum_mandates: Seats | None = None,
        caucus_protocol: CaucusProtocol | None = None,
    ) -> Chamber:
        """A chamber from a seat table: ``{"cdu": 164, "spd": 120}`` or ``{cdu: 164}``.

        The shallowest constructor: each seat knows its party and nothing else, as in a
        published seat distribution. Mandates are ordered as the mapping is. If the table
        fills fewer seats than ``minimum_mandates``, the rest are added as vacant seats in
        no caucus.

        Caucuses are formed with ``caucus_protocol``, by default ``(CaucusPerParty(),)``:
        one per party with seats. ``caucus_protocol=()`` forms none, so every filled seat
        is non-attached. For a chamber whose caucuses are simply not known, call
        :meth:`clear_caucuses` on the result.

        The key :data:`NON_ATTACHED` (``"non-attached"``), or ``None`` for short, counts
        filled seats whose holders belong to no caucus: ``{"afd": 149, None: 3}``. Their
        party is not given, so it is left unrecorded, and they count towards the filled
        seats. Giving both keys is an error.

        Each mandate is given the id ``<party>.<nnn>``, numbered per party in table order:
        ``spd.001`` to ``spd.120``, ``non-attached.001``, and ``vacant.001`` for padding.
        """
        seen: set[str] = set()
        mandates: list[Mandate] = []
        for party, count in seats.items():
            if isinstance(party, Party) and party.id == NON_ATTACHED:
                raise ValueError(f"party id {NON_ATTACHED!r} is reserved for non-attached seats")
            party_id = NON_ATTACHED if party is None else party_id_of(party)
            if party_id in seen:
                raise ValueError(f"party {party_id!r} appears twice in the seat table")
            seen.add(party_id)
            _check_seats(f"seats for {party_id!r}", count)
            ids = _numbered(party_id, count)
            if party_id == NON_ATTACHED:
                mandates.extend(Mandate.model_validate({"id": mandate_id}) for mandate_id in ids)
            else:
                mandates.extend(Mandate.from_party(party_id, mandate_id) for mandate_id in ids)
        if minimum_mandates is not None:
            _check_seats("minimum_mandates", minimum_mandates)
            missing = minimum_mandates - len(mandates)
            if missing > 0:
                logger.info(
                    "seat table fills %d of %d seats; padding %d vacant seats",
                    len(mandates), minimum_mandates, missing,
                )
                mandates.extend(
                    Mandate.model_validate({"id": mandate_id, "is_vacant": True})
                    for mandate_id in _numbered("vacant", missing)
                )

        chamber = cls(term=term, mandates=tuple(mandates), minimum_mandates=minimum_mandates)
        if caucus_protocol is None:
            # Processes depend on state, not the other way round; importing here keeps
            # wahlwerk.state free of a module-level dependency on wahlwerk.process.
            from wahlwerk.process.caucus import CaucusPerParty

            caucus_protocol = (CaucusPerParty(),)
        return chamber.form_caucuses(caucus_protocol)

    # ===========================================================
    # Processes
    # ===========================================================
    def clear_caucuses(self) -> Chamber:
        """The chamber with no caucuses and membership no longer on record; its seats are
        unchanged."""
        logger.debug("%s: clearing %d caucuses", self._title(), len(self.caucuses))
        return type(self).model_validate(
            {**dict(self), "caucuses": (), "are_caucuses_recorded": False}
        )

    def form_caucuses(self, protocol: CaucusProtocol) -> Chamber:
        """The chamber with its caucuses formed anew: the old ones are cleared, then
        each step of ``protocol`` is applied in order.

        ``chamber.form_caucuses((CaucusPerParty(), CaucusOfParties(parties=("cdu", "csu"))))``
        """
        chamber = self.clear_caucuses()
        for step in protocol:
            chamber = step(chamber)
            logger.debug("form_caucuses: %r -> %d caucuses", step, len(chamber.caucuses))
        return type(chamber).model_validate({**dict(chamber), "are_caucuses_recorded": True})

    def with_caucuses(self, caucuses: Iterable[Caucus]) -> Chamber:
        """This chamber with ``caucuses`` in place of its own, validated against the seats."""
        return type(self).model_validate({**dict(self), "caucuses": tuple(caucuses)})

    # ===========================================================
    # Properties
    # ===========================================================
    @property
    def body(self) -> BodyId | None:
        """The body this chamber belongs to, from its term."""
        return self.term.body if self.term else None

    @property
    def is_empty(self) -> bool:
        """Return True if the chamber has no mandates."""
        return not self.mandates

    @property
    def has_caucuses(self) -> bool:
        """Return True if the chamber has any caucuses."""
        return bool(self.caucuses)

    @property
    def size(self) -> int:
        """The number of mandates in the chamber, vacant seats included."""
        return len(self.mandates)

    @property
    def seats_without_caucus(self) -> int:
        """The number of seats in no caucus, vacant seats included."""
        return self.size - sum(caucus.size for caucus in self.caucuses)

    @property
    def non_attached_seats(self) -> int | None:
        """The number of filled seats in no caucus (fraktionslos in the Bundestag).

        ``None`` if membership is not on record: no caucuses and
        :attr:`are_caucuses_recorded` false.
        """
        if not (self.has_caucuses or self.are_caucuses_recorded):
            return None
        in_caucus = sum(caucus.size for caucus in self.caucuses)
        return self.filled_seats - in_caucus

    @property
    def vacant_seats(self) -> int:
        """The number of seats nobody holds."""
        return sum(1 for m in self.mandates if m.is_vacant)

    @property
    def filled_seats(self) -> int:
        """The number of seats somebody holds."""
        return self.size - self.vacant_seats

    @property
    def is_below_minimum(self) -> bool:
        """Whether fewer seats are filled than ``minimum_mandates``; False if unknown."""
        return self.minimum_mandates is not None and self.filled_seats < self.minimum_mandates

    @property
    def is_above_minimum(self) -> bool:
        """Whether more seats are filled than ``minimum_mandates``, e.g. through
        Überhang; False if unknown."""
        return self.minimum_mandates is not None and self.filled_seats > self.minimum_mandates

    @property
    def is_at_minimum(self) -> bool:
        """Whether exactly ``minimum_mandates`` seats are filled; False if unknown."""
        return self.minimum_mandates is not None and self.filled_seats == self.minimum_mandates

    @property
    def seats_by_party(self) -> dict[PartyId | None, int]:
        """Seats per party, in order of first appearance; ``None`` for seats whose
        party is not on record."""
        seats: dict[PartyId | None, int] = {}
        for mandate in self.mandates:
            seats[mandate.party] = seats.get(mandate.party, 0) + 1
        return seats

    def get_caucuses(self, include_non_attached: bool = False) -> list[Caucus]:
        """The caucuses, in order; with ``include_non_attached``, the non-attached seats
        follow as an imaginary caucus.

        The imaginary caucus has id :data:`NON_ATTACHED` (``"non-attached"``), holds the
        filled seats in no caucus, and
        is built for this list only, never stored in :attr:`caucuses`. It is left out
        when there are no non-attached seats or membership is not on record.
        """
        caucuses = list(self.caucuses)
        if not include_non_attached or not self.non_attached_seats:
            return caucuses
        in_caucus = {mandate_id for caucus in self.caucuses for mandate_id in caucus.mandates}
        mandates = frozenset(
            m.id for m in self.mandates if not m.is_vacant and m.id not in in_caucus
        )
        caucuses.append(
            Caucus.model_validate({"id": NON_ATTACHED, "mandates": mandates})
        )
        return caucuses

    @property
    def seats_by_caucus(self) -> dict[str, int] | None:
        """Seats per caucus id, in caucus order, then the non-attached seats under the
        imaginary caucus :data:`NON_ATTACHED` (``"non-attached"``) if there are any.

        The imaginary caucus exists only in this view, never in :attr:`caucuses`. Vacant
        seats are left out, so the values sum to :attr:`filled_seats`. ``None`` when
        membership is not on record, as for :attr:`non_attached_seats`.
        """
        non_attached = self.non_attached_seats
        if non_attached is None:
            return None
        seats: dict[str, int] = {caucus.id: caucus.size for caucus in self.caucuses}
        if non_attached:
            seats[NON_ATTACHED] = non_attached
        return seats

    # ===========================================================
    # Display
    # ===========================================================
    def _name(self) -> str:
        """``de.bund.bundestag, term 21``, with whatever of that is known; may be empty."""
        parts: list[str] = [self.body] if self.body else []
        if self.term is not None and self.term.number is not None:
            parts.append(f"term {self.term.number}")
        return ", ".join(parts)

    def _title(self) -> str:
        """``Chamber de.bund.bundestag, term 21``, with whatever of that is known."""
        return f"Chamber {self._name()}".rstrip()

    def _rows(self) -> list[tuple[str, int, str]]:
        """Party label, seats and share (as a percentage string) per party."""
        return [
            (
                "unrecorded" if party is None else party,
                seats,
                f"{100 * seats / self.size:.1f}%",
            )
            for party, seats in self.seats_by_party.items()
        ]

    def __repr__(self) -> str:
        head = f"{self._title()}: {self.size} seats"
        rows = self._rows()
        if not rows:
            return head
        width = max(5, *(len(label) for label, _, _ in rows))
        lines = [
            head,
            f"  {'party':<{width}}  {'seats':>5}  {'share':>6}",
            f"  {'-' * width}  {'-' * 5}  {'-' * 6}",
        ]
        lines += [f"  {label:<{width}}  {seats:>5}  {share:>6}" for label, seats, share in rows]
        return "\n".join(lines)

    def _repr_html_(self) -> str:
        th = "padding:2px 10px;border-bottom:2px solid #555"
        td = "padding:1px 10px;border-bottom:1px solid #ddd"
        lines = [
            "<table style='border-collapse:collapse;font-family:monospace;font-size:12px'>",
            (
                f"<caption style='text-align:left;font-weight:bold;padding-bottom:2px'>"
                f"{escape(self._title())} &nbsp;|&nbsp; {self.size} seats</caption>"
            ),
            (
                f"<thead><tr><th style='{th};text-align:left'>party</th>"
                f"<th style='{th};text-align:right'>seats</th>"
                f"<th style='{th};text-align:right'>share</th></tr></thead><tbody>"
            ),
        ]
        for label, seats, share in self._rows():
            lines.append(
                f"<tr><td style='{td};text-align:left'>{escape(label)}</td>"
                f"<td style='{td};text-align:right'>{seats}</td>"
                f"<td style='{td};text-align:right'>{share}</td></tr>"
            )
        lines.append("</tbody></table>")
        return "\n".join(lines)

    def fancy_html(self, kind: Literal["seats", "pie"] = "seats", width: int = 240) -> str:
        """The chamber as a chart; call explicitly in a notebook.

        ``kind="seats"`` draws every seat in a hemicycle, ``kind="pie"`` a half pie with
        one wedge per party. Parties run in mandate order, left to right. Needs the
        optional ``wahlwerk-ui`` package (``wahlwerk[ui]``); the engine itself has no
        plotting dependency. The result is a ``str`` that Jupyter renders.
        """
        try:
            from wahlwerk_ui.plot.chamber.card import chamber_html
        except ImportError as error:
            raise ImportError(
                "Chamber.fancy_html needs wahlwerk-ui: install wahlwerk[ui]"
            ) from error
        return chamber_html(
            list(self.seats_by_party.items()),
            kind=kind,
            title=self._name(),
            width=width,
        )


def _check_seats(label: str, seats: object) -> None:
    """Reject a seat count that is not a non-negative ``int`` (``bool`` included)."""
    if isinstance(seats, bool) or not isinstance(seats, int):
        raise TypeError(f"{label} must be an int, got {seats!r}")
    if seats < 0:
        raise ValueError(f"{label} is negative: {seats}")


def _numbered(prefix: str, count: int) -> list[str]:
    """``count`` mandate ids ``<prefix>.001``, ``<prefix>.002``, ...; at least 3 digits."""
    return [f"{prefix}.{n:03d}" for n in range(1, count + 1)]
