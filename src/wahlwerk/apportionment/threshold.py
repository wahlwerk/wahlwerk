"""Thresholds: which keys take part in an apportionment at all.

Like the apportionment methods, thresholds know nothing about parties or any law. Each
selects keys from their weights (and, where the rule needs it, the seats they already
won, e.g. in Wahlkreise), and they compose: :class:`AlternativeThresholds` passes a key
that any of its thresholds passes, which is how "5 % or three Wahlkreis seats" is
written, and :class:`Exempt` passes named keys regardless, as a party of a national
minority is exempt. Modelled on the seatless selectors of votelib
(github.com/simberaj/votelib); comparisons are exact.
"""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import Mapping
from fractions import Fraction
from typing import Any

from pydantic import Field, SerializeAsAny, field_validator

from wahlwerk.apportionment.method import _exact_weights
from wahlwerk.model import Count, Model, Share

__all__ = [
    "AbsoluteThreshold",
    "AlternativeThresholds",
    "Exempt",
    "RelativeThreshold",
    "SeatThreshold",
    "Threshold",
]


class Threshold(Model):
    """A rule that passes some keys and excludes the others."""

    def select(
        self,
        weights: Mapping[str, int | Fraction],
        won: Mapping[str, int] | None = None,
    ) -> frozenset[str]:
        """The keys of ``weights`` that pass.

        ``won`` holds seats already won per key, for thresholds that count them; keys
        missing from it won none. Weights are checked as in
        :meth:`~wahlwerk.apportionment.ApportionmentMethod.apportion`.
        """
        exact = _exact_weights(weights)
        seats_won = dict(won or {})
        for key, seats in seats_won.items():
            if isinstance(seats, bool) or not isinstance(seats, int) or seats < 0:
                raise TypeError(f"seats won by {key!r} must be a non-negative int, got {seats!r}")
        return frozenset(self._select(exact, seats_won))

    @abstractmethod
    def _select(self, weights: dict[str, Fraction], won: dict[str, int]) -> frozenset[str]:
        """The passing keys of checked weights."""

    @property
    def uses_won(self) -> bool:
        """Whether this threshold counts seats already won, so a caller must pass them."""
        return False


class RelativeThreshold(Threshold):
    """Passes keys whose weight is at least ``share`` of the total weight, e.g. five
    percent of the valid Zweitstimmen (``share=Fraction(5, 100)``)."""

    share: Share = Field(
        description="The share of the total weight a key needs, e.g. ``Fraction(5, 100)``.",
    )
    accept_equal: bool = Field(
        default=True,
        description="Whether exactly ``share`` passes (\"mindestens\"); false for \"mehr als\".",
    )

    @field_validator("share", mode="before")
    @classmethod
    def _no_float(cls, value: Any) -> Any:
        if isinstance(value, float):
            # A ValueError, so pydantic reports it as a ValidationError on the field.
            raise ValueError(f"share must be exact (Fraction or 'p/q'), got float {value}")  # noqa: TRY004
        return value

    def _select(self, weights: dict[str, Fraction], won: dict[str, int]) -> frozenset[str]:
        total = sum(weights.values(), Fraction(0))
        needed = self.share * total
        return frozenset(
            key
            for key, weight in weights.items()
            if weight > needed or (self.accept_equal and weight == needed)
        )


class AbsoluteThreshold(Threshold):
    """Passes keys whose weight is at least ``weight``, e.g. a number of votes."""

    weight: Count = Field(
        description="The weight a key needs, e.g. a number of votes.",
    )
    accept_equal: bool = Field(
        default=True,
        description="Whether exactly ``weight`` passes.",
    )

    def _select(self, weights: dict[str, Fraction], won: dict[str, int]) -> frozenset[str]:
        return frozenset(
            key
            for key, weight in weights.items()
            if weight > self.weight or (self.accept_equal and weight == self.weight)
        )


class SeatThreshold(Threshold):
    """Passes keys that already won at least ``seats`` seats, e.g. three Wahlkreis seats
    (the Grundmandatsklausel), whatever their weight."""

    seats: int = Field(
        ge=1,
        description="The seats already won a key needs, e.g. 3.",
    )

    def _select(self, weights: dict[str, Fraction], won: dict[str, int]) -> frozenset[str]:
        return frozenset(key for key in weights if won.get(key, 0) >= self.seats)

    @property
    def uses_won(self) -> bool:
        return True


class Exempt(Threshold):
    """Passes the named keys regardless of their weight, e.g. a party of a national
    minority; excludes every other key, so it is used inside
    :class:`AlternativeThresholds`."""

    keys: frozenset[str] = Field(
        min_length=1,
        description="The keys that always pass, e.g. ``frozenset({'ssw'})``.",
    )

    def _select(self, weights: dict[str, Fraction], won: dict[str, int]) -> frozenset[str]:
        return frozenset(key for key in weights if key in self.keys)


class AlternativeThresholds(Threshold):
    """Passes keys that any of ``thresholds`` passes: an "or", e.g. 5 % or three
    Wahlkreis seats or a minority party."""

    thresholds: tuple[SerializeAsAny[Threshold], ...] = Field(
        min_length=2,
        description="The thresholds, any of which is enough.",
    )

    def _select(self, weights: dict[str, Fraction], won: dict[str, int]) -> frozenset[str]:
        passed: frozenset[str] = frozenset()
        for threshold in self.thresholds:
            passed |= threshold._select(weights, won)
        return passed

    @property
    def uses_won(self) -> bool:
        return any(threshold.uses_won for threshold in self.thresholds)
