"""Largest remainder methods (quota methods): each key gets the whole part of its weight
over a quota, and the seats left go to the largest remainders."""

from __future__ import annotations

from abc import abstractmethod
from fractions import Fraction

from wahlwerk.apportionment.method import ApportionmentMethod, _largest
from wahlwerk.apportionment.result import Apportionment

__all__ = ["HareNiemeyer", "LargestRemainder"]


class LargestRemainder(ApportionmentMethod):
    """Quota methods: each key gets the whole part of its weight over the quota, and the
    seats left go to the largest remainders, one each."""

    @abstractmethod
    def quota(self, total: Fraction, seats: int) -> Fraction:
        """The weight one seat is worth, given the total weight and the seats."""

    def _apportion(
        self, weights: dict[str, Fraction], seats: int, first: str | None = None
    ) -> Apportionment:
        """Whole seats, then the seats left by largest remainder; ``first``, if given,
        takes one of the seats left before any remainder is compared."""
        quota = self.quota(sum(weights.values(), Fraction(0)), seats)
        shares = {key: weight / quota for key, weight in weights.items()}
        whole = {key: share.numerator // share.denominator for key, share in shares.items()}
        left = seats - sum(whole.values())
        if left < 0:
            raise ValueError(
                f"{type(self).__name__}: the quota {quota} gives {seats - left} whole seats, "
                f"more than the {seats} to apportion"
            )
        ahead = [first] if first is not None and left else []
        rest = [(shares[key] - whole[key], key) for key in weights if key not in ahead]
        winners, tie = _largest(rest, left - len(ahead))
        winners = ahead + winners
        return Apportionment(
            seats=tuple((key, whole[key] + (key in winners)) for key in weights), tie=tie
        )


class HareNiemeyer(LargestRemainder):
    """Hare/Niemeyer (Hamilton): the Hare quota, total weight over seats. So each key's
    share is exactly its weight's proportion of the seats; the whole parts are kept, and
    the largest remainders win the rest."""

    def quota(self, total: Fraction, seats: int) -> Fraction:
        return total / seats
