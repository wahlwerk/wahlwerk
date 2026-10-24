"""Deduction and Increment: the concepts behind the seats to apportion, the list seats
and overhang, and a raised chamber size."""

from fractions import Fraction

import pytest

from wahlwerk.apportionment.deduction import Deduction
from wahlwerk.apportionment.increment import Increment
from wahlwerk.apportionment.quota import HareQuota


def test_deduction_gives_what_is_left_and_what_is_beyond():
    deduction = Deduction()
    assert deduction.left({"afd": 5, "linke": 2}, {"afd": 3, "linke": 3}) == {"afd": 2, "linke": 0}
    assert deduction.excess({"afd": 5, "linke": 2}, {"afd": 3, "linke": 3}) == {"linke": 1}
    assert deduction.left({"chamber": 83}, {"chamber": 1}) == {"chamber": 82}
    assert deduction.left({}, {}) == {} and deduction.excess({}, {}) == {}


def test_increment_raises_by_factor_per_seat_of_overhang():
    assert Increment(factor=2).of(83, {"cdu": 6}) == 95
    assert Increment().of(10, {"a": 1, "b": 2}) == 13
    with pytest.raises(ValueError):
        Increment(factor=0)


def test_a_quota_gives_the_whole_seats_of_a_part():
    # 50 of 950 votes, 20 seats: the Hare quota is 47.5, so 50 votes make 1 whole seat.
    assert HareQuota().whole_seats(50, 950, 20) == 1
    assert HareQuota().whole_seats(Fraction(100), 1000, 20) == 2
