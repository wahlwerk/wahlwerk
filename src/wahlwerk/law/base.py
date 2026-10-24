"""A law: one version of an electoral law, as a protocol, with when it was in force.

A :class:`Law` names its version (``de.st.lwg.2021``), the body it elects, where its text
comes from and the dates it was in force, and holds its allocation protocol. The
protocol is checked when the law is created, so a law in the wrong order fails on
import. A :class:`LawRegistry` finds a law by id or by the body and date it applies to.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from typing import Any

from pydantic import Field, SerializeAsAny, model_validator

from wahlwerk.ids import BodyId, LawId
from wahlwerk.model import Model
from wahlwerk.process.allocation.base import AllocationStep, check_protocol
from wahlwerk.process.allocation.flow import (
    protocol_data,
    protocol_html,
    protocol_table,
)

__all__ = ["Law", "LawRegistry"]


class Law(Model):
    """One version of an electoral law, as the protocol that allocates a body's seats.

    ``in_force_from`` and ``in_force_until`` bound the elections it governs; either is
    ``None`` when not on record, which leaves that side open.
    """

    id: LawId = Field(
        description="The version's key, jurisdiction first, e.g. ``de.st.lwg.2021``.",
    )
    title: str = Field(
        min_length=1,
        description="The law's title, e.g. ``Wahlgesetz des Landes Sachsen-Anhalt (LWG)``.",
    )
    citation: str = Field(
        min_length=1,
        description="Which text this version follows: the Fassung and its last amendment.",
    )
    body: BodyId = Field(
        description="The body whose seats it allocates, e.g. ``de.st.landtag``.",
    )
    source: str | None = Field(
        default=None,
        pattern=r"^https?://\S+$",
        description="Where the text this version follows was retrieved from.",
    )
    in_force_from: date | None = Field(
        default=None,
        description="The first day elections were held under it; ``None`` if not on record.",
    )
    in_force_until: date | None = Field(
        default=None,
        description="The last day it was in force; ``None`` if it still is, or not on record.",
    )
    protocol: tuple[SerializeAsAny[AllocationStep], ...] = Field(
        min_length=1,
        description="The allocation protocol, from the tally to the chamber.",
    )
    based_on: LawId | None = Field(
        default=None,
        description=(
            "The law this one was revised from (:meth:`revise`); ``None`` for a law as "
            "enacted."
        ),
    )

    @model_validator(mode="after")
    def _check(self) -> Law:
        if self.in_force_from and self.in_force_until and self.in_force_until < self.in_force_from:
            raise ValueError(
                f"law {self.id!r} ends on {self.in_force_until} before it starts on "
                f"{self.in_force_from}"
            )
        facts = check_protocol(self.protocol)
        if "chamber" not in facts:
            raise ValueError(f"law {self.id!r} forms no chamber; end its protocol with FillVacantSeatsFromLists")
        return self

    def revise(self, *, id: str, **changes: Any) -> Law:
        """A new law from this one: the same, except for ``changes``, under a new ``id``.

        A revised law is a counterfactual, not a law that was enacted: it records
        ``based_on`` (this law's id) and is in force on no date, so the registry never
        picks it for an election, unless ``in_force_from`` or ``in_force_until`` are
        given. It has no ``source`` of its own unless one is given. Change the protocol
        with :mod:`wahlwerk.law.edit`::

            LWG_2021.revise(
                id="example.st.lwg.101",
                title="LWG LSA with a chamber size of 101",
                protocol=replace(LWG_2021.protocol, SetChamberSize, seats=101),
            )

        Raises ``ValueError`` if ``id`` is this law's own, or the result fails a law's
        checks (a protocol in the wrong order, one that forms no chamber).
        """
        if id == self.id:
            raise ValueError(f"a revised law needs an id of its own, not {id!r}")
        unknown = set(changes) - set(type(self).model_fields)
        if unknown:
            raise ValueError(f"Law has no field {sorted(unknown)}")
        defaults: dict[str, Any] = {
            "based_on": self.id,
            "source": None,
            "in_force_from": None,
            "in_force_until": None,
        }
        return type(self).model_validate({**dict(self), **defaults, **changes, "id": id})

    # ===========================================================
    # Display
    # ===========================================================
    def __repr__(self) -> str:
        return f"Law {self.id}: {self.title}\n{protocol_table(self.protocol)}"

    def _repr_html_(self) -> str:
        return protocol_html(self.protocol, caption=f"{self.id}: {self.title}")

    def fancy_html(self, width: int = 640) -> str:
        """The protocol as a drawing: its steps in order, what each reads and writes,
        the steps a sequence or loop holds inside it. Call explicitly in a notebook.
        Needs the optional ``wahlwerk-ui`` package (``wahlwerk[ui]``)."""
        try:
            from wahlwerk_ui.plot.protocol import protocol_html as drawing
        except ImportError as error:
            raise ImportError("Law.fancy_html needs wahlwerk-ui: install wahlwerk[ui]") from error
        return drawing(protocol_data(self.protocol), title=f"{self.id}: {self.title}", width=width)

    def is_in_force(self, on: date) -> bool:
        """Whether an election on ``on`` was held under this version; an open side
        (``None``) counts as in force. A revised law (``based_on``) with no dates of its
        own is in force on no date."""
        if self.based_on is not None and self.in_force_from is None and self.in_force_until is None:
            return False
        starts = self.in_force_from is None or self.in_force_from <= on
        ends = self.in_force_until is None or on <= self.in_force_until
        return starts and ends


class LawRegistry(Model):
    """Every known version of every law, looked up by id or by body and date."""

    laws: tuple[Law, ...] = Field(
        default_factory=tuple,
        description="Every registered version, each id at most once.",
    )

    @model_validator(mode="after")
    def _check_unique(self) -> LawRegistry:
        ids = [law.id for law in self.laws]
        duplicates = sorted({law_id for law_id in ids if ids.count(law_id) > 1})
        if duplicates:
            raise ValueError(f"laws {duplicates} are registered twice")
        return self

    def __len__(self) -> int:
        return len(self.laws)

    def __iter__(self) -> Iterator[Law]:  # type: ignore[override]
        return iter(self.laws)

    def __getitem__(self, law_id: str) -> Law:
        found = self.get(law_id)
        if found is None:
            raise KeyError(f"no law {law_id!r}; known: {[law.id for law in self.laws]}")
        return found

    def get(self, law_id: str, default: Law | None = None) -> Law | None:
        """The law ``law_id``, or ``default`` if it is not registered."""
        return next((law for law in self.laws if law.id == law_id), default)

    def in_force(self, body: str, on: date) -> Law:
        """The version that governs an election of ``body`` on ``on``.

        Raises ``KeyError`` if none does, and ``ValueError`` if several do: the dates
        on record then overlap, which is a gap in the registry, not a choice to make.
        """
        found = [law for law in self.laws if law.body == body and law.is_in_force(on)]
        if not found:
            raise KeyError(f"no law for {body!r} in force on {on}")
        if len(found) > 1:
            raise ValueError(
                f"several laws for {body!r} in force on {on}: {[law.id for law in found]}; "
                "record their dates"
            )
        return found[0]
