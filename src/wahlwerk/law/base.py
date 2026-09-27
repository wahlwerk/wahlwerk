"""A law: one version of an electoral law, as a protocol, with when it was in force.

A :class:`Law` names its version (``de.st.lwg.2021``), the body it elects, where its text
comes from and the dates it was in force, and holds its allocation protocol. The
protocol is checked when the law is created, so a law in the wrong order fails on
import. A :class:`LawRegistry` finds a law by id or by the body and date it applies to.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date

from pydantic import Field, SerializeAsAny, model_validator

from wahlwerk.ids import BodyId, LawId
from wahlwerk.model import Model
from wahlwerk.process.allocation.base import AllocationStep, check_protocol

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

    @model_validator(mode="after")
    def _check(self) -> Law:
        if self.in_force_from and self.in_force_until and self.in_force_until < self.in_force_from:
            raise ValueError(
                f"law {self.id!r} ends on {self.in_force_until} before it starts on "
                f"{self.in_force_from}"
            )
        facts = check_protocol(self.protocol)
        if "chamber" not in facts:
            raise ValueError(f"law {self.id!r} forms no chamber; end its protocol with FormChamber")
        return self

    def is_in_force(self, on: date) -> bool:
        """Whether an election on ``on`` was held under this version; an open side
        (``None``) counts as in force."""
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
