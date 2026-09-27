"""The result of an apportionment: the seats each key won, and any tie."""

from __future__ import annotations

from collections.abc import Iterable

from pydantic import Field, model_validator

from wahlwerk.apportionment.tie import Tie
from wahlwerk.model import Model, Seats

__all__ = ["Apportionment"]


class Apportionment(Model):
    """The seats each key won, and the seats still tied, if any.

    ``seats`` holds every key given, in the order given, including keys that won
    nothing. While ``tie`` is set, ``seats`` holds only the decided seats, so their
    total falls short of the seats apportioned by ``tie.seats``.
    """

    seats: tuple[tuple[str, Seats], ...] = Field(
        default_factory=tuple,
        description="Each key and its decided seats, in the order the weights were given.",
    )
    tie: Tie | None = Field(
        default=None,
        description="Seats whose claims were exactly equal and go by lot; ``None`` if all are decided.",
    )

    @model_validator(mode="after")
    def _check_keys(self) -> Apportionment:
        keys = [key for key, _ in self.seats]
        if len(set(keys)) != len(keys):
            raise ValueError(f"apportionment lists a key more than once: {keys}")
        if self.tie is not None and not self.tie.candidates <= set(keys):
            raise ValueError(
                f"tie candidates {sorted(self.tie.candidates - set(keys))} are not apportioned keys"
            )
        return self

    def __getitem__(self, key: str) -> Seats:
        for name, seats in self.seats:
            if name == key:
                return seats
        raise KeyError(f"no key {key!r} in the apportionment")

    def get(self, key: str, default: Seats | None = None) -> Seats | None:
        """The decided seats of ``key``, or ``default`` if it was not apportioned."""
        return next((seats for name, seats in self.seats if name == key), default)

    def as_dict(self) -> dict[str, Seats]:
        """The decided seats per key, in order."""
        return dict(self.seats)

    @property
    def total(self) -> Seats:
        """The number of decided seats."""
        return sum(seats for _, seats in self.seats)

    @property
    def is_decided(self) -> bool:
        """Whether every seat is decided, i.e. there is no tie."""
        return self.tie is None

    def with_lot(self, winners: Iterable[str]) -> Apportionment:
        """The apportionment with its tie decided by the lot drawn: each of ``winners``
        gets one of the tied seats.

        Raises ``ValueError`` if there is no tie, or if ``winners`` are not exactly
        ``tie.seats`` distinct candidates of the tie.
        """
        if self.tie is None:
            raise ValueError("apportionment has no tie to decide by lot")
        drawn = list(winners)
        if len(set(drawn)) != len(drawn):
            raise ValueError(f"lot names a winner more than once: {drawn}")
        if len(drawn) != self.tie.seats:
            raise ValueError(f"lot must name {self.tie.seats} winners, got {len(drawn)}")
        strangers = sorted(set(drawn) - self.tie.candidates)
        if strangers:
            raise ValueError(
                f"lot winners {strangers} are not candidates of the tie "
                f"{sorted(self.tie.candidates)}"
            )
        return Apportionment(
            seats=tuple((key, seats + (key in drawn)) for key, seats in self.seats)
        )
