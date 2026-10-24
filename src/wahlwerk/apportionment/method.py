"""The interface every apportionment method shares, and the checks its families run.

The arithmetic is not here: every method calls its formula in ``wahlwerk.calc``
(:meth:`ApportionmentMethod.calculate`), which the engine only checks and wraps. So a
step in a law and a formula called by hand give the same seats by construction.
"""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import Mapping
from fractions import Fraction

from wahlwerk.apportionment.result import Apportionment
from wahlwerk.calc.result import SeatResult
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
        return Apportionment.from_seat_result(self.calculate(exact, seats))

    @abstractmethod
    def calculate(self, weights: Mapping[str, int | Fraction], seats: int) -> SeatResult:
        """The seats by this method's formula in ``wahlwerk.calc``, unchecked: the
        plain-number face of the method, which :class:`~wahlwerk.apportionment.ausgleich.Ausgleich`
        also uses."""


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
