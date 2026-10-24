"""Thresholds: which options take part in an apportionment at all.

Like the apportionment methods, thresholds know nothing about parties or any law. Each
selects options from their weights (and, where the rule needs it, the seats they already
won, e.g. in Wahlkreise), and they compose: :class:`AlternativeThresholds` passes an option
that any of its thresholds passes, which is how "5 % or three Wahlkreis seats" is
written, and :class:`Exempt` passes named options regardless, as a party of a national
minority is exempt. Modelled on the seatless selectors of votelib
(github.com/simberaj/votelib); comparisons are exact, in :mod:`wahlwerk.calc.threshold`.
"""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import Callable, Mapping
from fractions import Fraction
from typing import Any, ClassVar

from pydantic import Field, SerializeAsAny, field_validator

from wahlwerk.apportionment.method import _exact_weights
from wahlwerk.calc import threshold as calc
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
    """A rule that passes some options and excludes the others."""

    formulas: ClassVar[tuple[Callable[..., Any], ...]] = ()
    """The functions in ``wahlwerk.calc`` the threshold computes with, called through
    this attribute (see :attr:`wahlwerk.apportionment.method.ApportionmentMethod.formulas`)."""

    def select(
        self,
        weights: Mapping[str, int | Fraction],
        won: Mapping[str, int] | None = None,
    ) -> frozenset[str]:
        """The options of ``weights`` that pass.

        ``won`` holds seats already won per option, for thresholds that count them; options
        missing from it won none. Weights are checked as in
        :meth:`~wahlwerk.apportionment.ApportionmentMethod.apportion`.
        """
        exact = _exact_weights(weights)
        seats_won = dict(won or {})
        for option, seats in seats_won.items():
            if isinstance(seats, bool) or not isinstance(seats, int) or seats < 0:
                raise TypeError(f"seats won by {option!r} must be a non-negative int, got {seats!r}")
        return frozenset(self._select(exact, seats_won))

    @abstractmethod
    def _select(self, weights: dict[str, Fraction], won: dict[str, int]) -> frozenset[str]:
        """The passing options of checked weights."""

    @property
    def uses_won(self) -> bool:
        """Whether this threshold counts seats already won, so a caller must pass them."""
        return False


class RelativeThreshold(Threshold):
    """Passes options whose weight is at least ``share`` of the total weight, e.g. five
    percent of the valid Zweitstimmen (``share=Fraction(5, 100)``)."""

    formulas: ClassVar[tuple[Callable[..., Any], ...]] = (calc.share_threshold,)

    share: Share = Field(
        description="The share of the total weight an option needs, e.g. ``Fraction(5, 100)``.",
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
        if not weights:
            return frozenset()
        (share_threshold,) = self.formulas
        return _passed(share_threshold(weights, self.share, accept_equal=self.accept_equal))


class AbsoluteThreshold(Threshold):
    """Passes options whose weight is at least ``weight``, e.g. a number of votes."""

    formulas: ClassVar[tuple[Callable[..., Any], ...]] = (calc.count_threshold,)

    weight: Count = Field(
        description="The weight an option needs, e.g. a number of votes.",
    )
    accept_equal: bool = Field(
        default=True,
        description="Whether exactly ``weight`` passes.",
    )

    def _select(self, weights: dict[str, Fraction], won: dict[str, int]) -> frozenset[str]:
        if not weights:
            return frozenset()
        (count_threshold,) = self.formulas
        return _passed(count_threshold(weights, self.weight, accept_equal=self.accept_equal))


class SeatThreshold(Threshold):
    """Passes options that already won at least ``seats`` seats, e.g. three Wahlkreis seats
    (the Grundmandatsklausel), whatever their weight."""

    formulas: ClassVar[tuple[Callable[..., Any], ...]] = (calc.seat_threshold,)

    seats: int = Field(
        ge=1,
        description="The seats already won an option needs, e.g. 3.",
    )

    def _select(self, weights: dict[str, Fraction], won: dict[str, int]) -> frozenset[str]:
        if not weights:
            return frozenset()
        (seat_threshold,) = self.formulas
        return _passed(seat_threshold({option: won.get(option, 0) for option in weights}, self.seats))

    @property
    def uses_won(self) -> bool:
        return True


class Exempt(Threshold):
    """Passes the named options regardless of their weight, e.g. a party of a national
    minority; excludes every other option, so it is used inside
    :class:`AlternativeThresholds`."""

    options: frozenset[str] = Field(
        min_length=1,
        description="The options that always pass, e.g. ``frozenset({'ssw'})``.",
    )

    def _select(self, weights: dict[str, Fraction], won: dict[str, int]) -> frozenset[str]:
        return frozenset(option for option in weights if option in self.options)


class AlternativeThresholds(Threshold):
    """Passes options that any of ``thresholds`` passes: an "or", e.g. 5 % or three
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


def _passed(mask: object) -> frozenset[str]:
    """The options a ``wahlwerk.calc`` threshold passed."""
    assert isinstance(mask, dict)
    return frozenset(option for option, passed in mask.items() if passed)
