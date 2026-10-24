"""Sequences: a short row of steps that belong together, used as one step.

A law often says one thing in several steps that feed each other: Sec. 35 (4) to (7)
LWG LSA take the seats of one chamber size, apportion them and deduct the Wahlkreis
seats, and Sec. 35 (8) repeats exactly those. A :class:`StepSequence` names such a row
and is itself a step: it reads what its steps need from outside it, writes what they
write, and applies them in order. So a law can hold it, a loop can repeat it, an edit
can reach into it (``(5, "steps", 1)``), and a drawing can show it as one box.
"""

from __future__ import annotations

from pydantic import Field, SerializeAsAny

from wahlwerk.process.allocation.base import (
    Allocation,
    AllocationStep,
    outside_reads,
    written_by,
)

__all__ = ["StepSequence"]


class StepSequence(AllocationStep):
    """Several steps as one: applied in order, reading only what they need from outside."""

    title: str = Field(
        min_length=1,
        description="What the steps do together, e.g. ``allocate the seats of one chamber size``.",
    )
    steps: tuple[SerializeAsAny[AllocationStep], ...] = Field(
        min_length=1,
        description="The steps, applied first to last.",
    )

    @property
    def reads(self) -> frozenset[str]:
        """The facts its steps read that no earlier step of the sequence writes."""
        return outside_reads(self.steps)

    @property
    def optional_reads(self) -> frozenset[str]:
        return outside_reads(self.steps, optional=True)

    @property
    def writes(self) -> frozenset[str]:
        return written_by(self.steps)

    def _apply(self, allocation: Allocation) -> Allocation:
        for step in self.steps:
            allocation = step.apply(allocation)
        return allocation

