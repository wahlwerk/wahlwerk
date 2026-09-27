import pytest

from wahlwerk.law.de.bund.gobt import CAUCUS_PROTOCOL
from wahlwerk.process.caucus import ProtocolWarning
from wahlwerk.state import Chamber


def _seats(chamber: Chamber) -> list[tuple[str, frozenset[str]]]:
    return [(c.id, c.mandates) for c in chamber.caucuses]


def test_cdu_and_csu_form_the_union():
    chamber = Chamber.from_seats(
        {"cdu": 2, "spd": 1, "csu": 1}, caucus_protocol=CAUCUS_PROTOCOL
    )
    assert _seats(chamber) == [
        ("union", frozenset({"cdu.001", "cdu.002", "csu.001"})),
        ("spd", frozenset({"spd.001"})),
    ]


def test_every_other_party_forms_its_own_caucus():
    with pytest.warns(ProtocolWarning, match="no caucus formed"):
        chamber = Chamber.from_seats(
            {"spd": 2, "afd": 1}, caucus_protocol=CAUCUS_PROTOCOL
        )
    assert [c.id for c in chamber.caucuses] == ["spd", "afd"]
