import wahlwerk as ww
from wahlwerk.io import read_bundle
from wahlwerk.party import PartyRegistry
from wahlwerk.process.caucus import CaucusOfParties
from wahlwerk.state import Chamber
from wahlwerk.vote.popular import TallyRow


def test_root_exposes_packages_and_setup_logger():
    assert set(ww.__all__) == {"apportionment", "io", "law", "measure", "party", "process", "setup_logger", "state", "vote"}


def test_packages_are_reached_through_the_root():
    assert ww.io.read_bundle is read_bundle
    assert ww.party.PartyRegistry is PartyRegistry
    assert ww.process.caucus.CaucusOfParties is CaucusOfParties
    assert ww.state.Chamber is Chamber
    assert ww.vote.popular.TallyRow is TallyRow


def test_nothing_is_flattened():
    assert not hasattr(ww, "Chamber")
    assert not hasattr(ww.process, "CaucusPerParty")
    assert not hasattr(ww.vote, "TallyRow")
    assert not hasattr(ww.apportionment, "SainteLague")
    assert ww.apportionment.divisor.SainteLague
