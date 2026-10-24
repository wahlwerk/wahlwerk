"""Plurality: a list of options and their votes, the most votes win."""

from fractions import Fraction

import pytest

from wahlwerk.apportionment.plurality import Plurality
from wahlwerk.apportionment.tie import Tie
from wahlwerk.calc.plurality import plurality


def test_the_most_votes_win_the_seat():
    result = Plurality().apportion({"a": 120, "b": 95, "c": 80}, 1)
    assert result.as_dict() == {"a": 1, "b": 0, "c": 0}
    assert result.tie is None


def test_a_relative_majority_is_enough():
    # 40 % of the votes is no absolute majority, but the most.
    assert Plurality().apportion({"a": 40, "b": 35, "c": 25}, 1)["a"] == 1


def test_equal_tops_are_a_tie():
    result = Plurality().apportion({"a": 120, "b": 120, "c": 80}, 1)
    assert result.tie == Tie(candidates=frozenset({"a", "b"}), seats=1)
    assert result.total == 0


def test_it_is_the_formula():
    votes = {"a": 7, "b": Fraction(15, 2), "c": 3}
    assert Plurality().apportion(votes, 1).as_dict() == plurality(votes).as_dict()


def test_floats_are_refused():
    with pytest.raises(TypeError):
        Plurality().apportion({"a": 1.5, "b": 1}, 1)
