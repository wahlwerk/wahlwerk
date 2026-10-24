from datetime import date
from fractions import Fraction
from pathlib import Path

import pytest

from wahlwerk.apportionment.divisor import DHondt, SainteLague
from wahlwerk.apportionment.threshold import RelativeThreshold
from wahlwerk.io.bundle import read_bundle
from wahlwerk.law.de.st.lwg import LWG_2021
from wahlwerk.law.edit import find, insert, remove, replace, step_at, steps, substitute
from wahlwerk.process.allocation.allocate import allocate
from wahlwerk.process.allocation.chamber import FormChamber
from wahlwerk.process.allocation.count import SumVotes
from wahlwerk.process.allocation.eligibility import ApplyThresholdToKeys, SetChamberSize
from wahlwerk.process.allocation.overhang import RaiseByOverhang
from wahlwerk.process.allocation.seats import ApportionSeats

GOLDEN = Path(__file__).parents[1] / "golden" / "de.landtag.st.2026"
P = LWG_2021.protocol


def test_steps_walks_nested_protocols_depth_first():
    paths = [path for path, _ in steps(P)]
    assert paths[0] == (0,)
    assert (3, "protocol", 0, "steps", 1) in paths
    assert paths.index((3,)) < paths.index((3, "protocol", 0)) < paths.index((3, "protocol", 0, "steps", 1)) < paths.index((4,))
    assert isinstance(step_at(P, (3, "protocol", 0, "steps", 1)), ApportionSeats)


def test_find_reaches_into_the_mehrsitze_loop():
    assert find(P, ApportionSeats) == [(3, "protocol", 0, "steps", 1)]
    assert find(P, RaiseByOverhang) == [(3,)]


def test_replace_changes_every_occurrence():
    edited = replace(P, ApportionSeats, method=SainteLague())
    assert all(isinstance(step_at(edited, p).method, SainteLague) for p in find(edited, ApportionSeats))
    assert P == LWG_2021.protocol  # nothing changed in place


def test_replace_one_occurrence():
    edited = replace(P, ApportionSeats, at=(3, "protocol", 0, "steps", 1), method=DHondt())
    assert isinstance(step_at(edited, (3, "protocol", 0, "steps", 1)).method, DHondt)
    assert step_at(edited, (3, "protocol", 0, "steps", 0)) == step_at(P, (3, "protocol", 0, "steps", 0))


def test_replace_validates_and_names_what_is_wrong():
    with pytest.raises(ValueError, match="no field"):
        replace(P, SetChamberSize, size=101)
    with pytest.raises(ValueError):
        replace(P, SetChamberSize, seats=-1)
    with pytest.raises(KeyError, match="no FormChamber at"):
        replace(P, FormChamber, at=(3,), minimum_mandates=1)
    with pytest.raises(KeyError, match="has no"):
        replace((SumVotes(level="land"),), SetChamberSize, seats=1)


def test_substitute_insert_remove():
    threshold = ApplyThresholdToKeys(
        threshold=RelativeThreshold(share=Fraction(1, 10)), section="zweitstimme", level="land"
    )
    assert step_at(substitute(P, (2, "steps", 1), threshold), (2, "steps", 1)) == threshold
    longer = insert(P, (3, "protocol", 0, "steps", 0), SumVotes(level="land"))
    assert len(step_at(longer, (3, "protocol", 0)).steps) == 4
    shorter = remove(P, (3, "protocol", 0, "steps", 2))
    assert len(step_at(shorter, (3, "protocol", 0)).steps) == 2
    with pytest.raises(KeyError):
        remove(P, (42,))
    with pytest.raises(KeyError, match="step path"):
        step_at(P, (3, "protocol"))


def test_revise_makes_a_counterfactual_that_is_never_in_force():
    law = LWG_2021.revise(
        id="example.st.lwg.101",
        title="LWG LSA with a chamber size of 101",
        protocol=replace(P, SetChamberSize, seats=101),
    )
    assert law.based_on == "de.st.lwg.2021"
    assert law.source is None
    assert not law.is_in_force(date(2026, 9, 6))
    vote = read_bundle(GOLDEN)
    assert allocate(vote, LWG_2021.protocol).size == 83
    assert allocate(vote, law.protocol).size == 101


def test_revise_needs_a_new_id_and_a_valid_protocol():
    with pytest.raises(ValueError, match="id of its own"):
        LWG_2021.revise(id="de.st.lwg.2021")
    with pytest.raises(ValueError, match="no field"):
        LWG_2021.revise(id="example.x", seats=101)
    with pytest.raises(ValueError, match="forms no chamber"):
        LWG_2021.revise(id="example.x", protocol=remove(P, (4,)))
