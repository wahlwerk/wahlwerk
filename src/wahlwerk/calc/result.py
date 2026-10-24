"""The result of a seat formula: the seats decided, and the seats still tied.

A seat formula never lets order decide equal claims. Where the claims for the last
seats are exactly equal, it decides what it can and reports the rest: which options are
tied and how many seats they share, one each. That is a result, not an error; a law
that cannot go on without the lot raises on it, a person exploring a formula reads it.

>>> from wahlwerk.calc import divisor
>>> divisor.d_hondt({"a": 2, "b": 2, "c": 1}, 1)
SeatResult({'a': 0, 'b': 0, 'c': 0}, tied=['a', 'b'], open=1)
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

__all__ = ["SeatResult"]


@dataclass(frozen=True, eq=False)
class SeatResult:
    """Seats per option, shaped like the input of the formula that made it.

    For a single scenario, :attr:`seats` is a ``dict`` (keyed input) or a 1-D ``int64``
    array; :attr:`tied` lists the tied options (or their indices), :attr:`open` the seats
    they share. For several scenarios each of these has one entry per row.
    ``np.asarray(result)`` is the decided seats.
    """

    decided: NDArray[np.int64]
    """Decided seats, options on the last axis."""
    tie_mask: NDArray[np.bool_]
    """Which options share the open seats, same shape as :attr:`decided`."""
    open_seats: NDArray[np.int64]
    """Seats left to the lot, one per scenario (0-D for one scenario)."""
    options: tuple[str, ...] | None = None
    """The options, if the input was a mapping."""

    @classmethod
    def from_rows(
        cls,
        rows: Iterable[tuple[list[int], list[bool], int]],
        options: tuple[str, ...] | None,
        is_batch: bool,
    ) -> SeatResult:
        """Build from per-scenario ``(seats, tied, open)`` triples."""
        triples = list(rows)
        decided = np.asarray([t[0] for t in triples], dtype=np.int64)
        tied = np.asarray([t[1] for t in triples], dtype=bool)
        open_seats = np.asarray([t[2] for t in triples], dtype=np.int64)
        if not is_batch:
            decided, tied, open_seats = decided[0], tied[0], open_seats[0]
        return cls(decided=decided, tie_mask=tied, open_seats=open_seats, options=options)

    @property
    def is_batch(self) -> bool:
        """Whether this holds several scenarios."""
        return self.decided.ndim == 2

    @property
    def seats(self) -> dict[str, Any] | NDArray[np.int64]:
        """The decided seats: ``{option: seats}`` for keyed input, else an array."""
        if self.options is None:
            return self.decided
        if self.is_batch:
            return {option: self.decided[:, i] for i, option in enumerate(self.options)}
        return {option: int(self.decided[i]) for i, option in enumerate(self.options)}

    @property
    def tied(self) -> list[Any]:
        """The tied options (indices for array input); for several scenarios, one list per row."""
        def names(mask: NDArray[np.bool_]) -> list[Any]:
            found = np.flatnonzero(mask).tolist()
            return [self.options[i] for i in found] if self.options is not None else found

        if self.is_batch:
            return [names(row) for row in self.tie_mask]
        return names(self.tie_mask)

    @property
    def open(self) -> Any:
        """Seats the tied options share, one each: an ``int``, or an array per scenario."""
        return int(self.open_seats) if not self.is_batch else self.open_seats

    @property
    def is_decided(self) -> bool:
        """Whether every seat is decided, in every scenario."""
        return not bool(np.any(self.open_seats))

    @property
    def total(self) -> Any:
        """The decided seats summed: an ``int``, or an array per scenario."""
        totals = self.decided.sum(axis=-1)
        return int(totals) if not self.is_batch else totals

    def as_dict(self) -> dict[str, Any]:
        """The decided seats per option; raises ``TypeError`` for array input."""
        seats = self.seats
        if not isinstance(seats, dict):
            raise TypeError("the input had no options; use np.asarray(result)")
        return seats

    def with_lot(self, winners: Iterable[Any]) -> SeatResult:
        """The result with its tie decided by the lot drawn: each winner (an option, or an
        index for array input) gets one of the open seats. One scenario only."""
        if self.is_batch:
            raise ValueError("decide a lot one scenario at a time")
        if self.is_decided:
            raise ValueError("there is no tie to decide by lot")
        drawn = list(winners)
        index = [self.options.index(w) if self.options is not None else int(w) for w in drawn]
        if len(set(index)) != len(index):
            raise ValueError(f"lot names a winner more than once: {drawn}")
        if len(index) != self.open:
            raise ValueError(f"lot must name {self.open} winners, got {len(index)}")
        if not all(self.tie_mask[i] for i in index):
            raise ValueError(f"lot winners {drawn} are not all tied: {self.tied}")
        decided = self.decided.copy()
        decided[index] += 1
        return SeatResult(
            decided=decided,
            tie_mask=np.zeros_like(self.tie_mask),
            open_seats=np.asarray(0, dtype=np.int64),
            options=self.options,
        )

    def __getitem__(self, option: Any) -> Any:
        if self.options is not None and isinstance(option, str):
            return self.as_dict()[option]
        return self.decided[option]

    def __iter__(self) -> Iterator[Any]:
        return iter(self.options) if self.options is not None else iter(self.decided)

    def __len__(self) -> int:
        return int(self.decided.shape[-1])

    def __array__(self, dtype: Any = None, copy: Any = None) -> NDArray[Any]:
        return self.decided if dtype is None else self.decided.astype(dtype)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SeatResult):
            return NotImplemented
        return (
            self.options == other.options
            and np.array_equal(self.decided, other.decided)
            and np.array_equal(self.tie_mask, other.tie_mask)
            and np.array_equal(self.open_seats, other.open_seats)
        )

    def __hash__(self) -> int:
        return hash((self.options, self.decided.tobytes(), self.tie_mask.tobytes()))

    def __repr__(self) -> str:
        seats = self.seats
        shown = seats if isinstance(seats, dict) else seats.tolist()
        if self.is_decided:
            return f"SeatResult({shown})"
        return f"SeatResult({shown}, tied={self.tied}, open={self.open if not self.is_batch else self.open_seats.tolist()})"
