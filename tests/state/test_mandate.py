import pytest
from pydantic import ValidationError

from wahlwerk.party import Party
from wahlwerk.state import Mandate, MandateSource

SPD = Party(id="spd", name="Sozialdemokratische Partei Deutschlands")


def test_from_party_by_id():
    mandate = Mandate.from_party("spd", "spd.001")
    assert mandate.id == "spd.001"
    assert mandate.party == "spd"
    assert mandate.origin.source is MandateSource.UNRECORDED
    assert not mandate.is_vacant


def test_from_party_by_party():
    assert Mandate.from_party(SPD, "spd.001") == Mandate.from_party("spd", "spd.001")


def test_from_party_invalid_id_is_rejected():
    with pytest.raises(ValidationError):
        Mandate.from_party("SPD", "spd.001")


def test_id_is_required():
    with pytest.raises(ValidationError):
        Mandate(party="spd")


@pytest.mark.parametrize("good", ["spd.001", "wk.001", "list.by.csu.004", "m1"])
def test_id_is_a_dotted_key(good):
    assert Mandate(id=good).id == good


@pytest.mark.parametrize("bad", ["SPD.001", "spd..001", ".001", "spd 1", ""])
def test_malformed_id_is_rejected(bad):
    with pytest.raises(ValidationError):
        Mandate(id=bad)


def test_mandate_is_filled_by_default():
    assert not Mandate(id="m.1").is_vacant


def test_vacant_mandate_may_keep_its_party():
    """A seat awaiting Nachrücken is vacant, yet its party is known."""
    mandate = Mandate(id="spd.001", party="spd", is_vacant=True)
    assert mandate.is_vacant
    assert mandate.party == "spd"


def test_has_party():
    assert Mandate(id="m.1", party="spd").has_party
    assert not Mandate(id="m.1").has_party
    assert "has_party" not in Mandate(id="m.1").model_dump()
