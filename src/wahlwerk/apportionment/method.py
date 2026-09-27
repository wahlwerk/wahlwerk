"""The interface every apportionment method shares, and the checks and tie-aware
selection its families build on."""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import Mapping
from fractions import Fraction

from wahlwerk.apportionment.result import Apportionment
from wahlwerk.apportionment.tie import Tie
from wahlwerk.model import Model

__all__ = ["ApportionmentMethod"]


class ApportionmentMethod(Model):
    """A way to divide seats among keys in proportion to their weights."""

    def apportion(self, weights: Mapping[str, int | Fraction], seats: int) -> Apportionment:
        """Divide ``seats`` among the keys of ``weights``.

        Weights are non-negative ``int`` or :class:`~fractions.Fraction`; a key of
        weight 0 wins nothing. Raises ``TypeError`` for a float, a bool or any other
        weight or seat count that is not exact, and ``ValueError`` for a negative one,
        or for seats to give when every weight is 0.
        """
        exact = _exact_weights(weights)
        _check_seats(seats)
        if seats and not any(exact.values()):
            raise ValueError(f"cannot apportion {seats} seats: every weight is 0")
        if not seats:
            return Apportionment(seats=tuple((key, 0) for key in exact))
        return self._apportion(exact, seats)

    @abstractmethod
    def _apportion(self, weights: dict[str, Fraction], seats: int) -> Apportionment:
        """Divide at least one seat among checked weights, at least one of them positive."""


def _largest(claims: list[tuple[Fraction, str]], count: int) -> tuple[list[str], Tie | None]:
    """The keys of the ``count`` largest claims, and the tie if the claims at the edge
    are equal. A key may appear in several claims, but at most once at any one value.

    Never lets order decide: every claim above the ``count``-th largest wins; those equal
    to it win if they all fit, and otherwise they share the seats left as a tie.
    """
    if count == 0:
        return [], None
    edge = sorted((claim for claim, _ in claims), reverse=True)[count - 1]
    above = [key for claim, key in claims if claim > edge]
    at = [key for claim, key in claims if claim == edge]
    if len(above) + len(at) == count:
        return above + at, None
    return above, Tie(candidates=frozenset(at), seats=count - len(above))


def _exact_weights(weights: Mapping[str, int | Fraction]) -> dict[str, Fraction]:
    if not isinstance(weights, Mapping):
        raise TypeError(f"weights must be a mapping of key to weight, got {type(weights).__name__}")
    exact = {}
    for key, weight in weights.items():
        if not isinstance(key, str) or not key:
            raise TypeError(f"weight keys must be non-empty strings, got {key!r}")
        if isinstance(weight, bool) or not isinstance(weight, (int, Fraction)):
            raise TypeError(
                f"weight of {key!r} must be an int or a Fraction, got {type(weight).__name__}"
            )
        if weight < 0:
            raise ValueError(f"weight of {key!r} is negative: {weight}")
        exact[key] = Fraction(weight)
    return exact


def _check_seats(seats: int) -> None:
    if isinstance(seats, bool) or not isinstance(seats, int):
        raise TypeError(f"seats must be an int, got {type(seats).__name__}")
    if seats < 0:
        raise ValueError(f"seats is negative: {seats}")
