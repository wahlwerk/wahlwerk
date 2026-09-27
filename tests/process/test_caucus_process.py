import warnings

import pytest
from pydantic import ValidationError

from wahlwerk.party import Party
from wahlwerk.process.caucus import (
    CaucusOfParties,
    CaucusPerParty,
    CaucusStep,
    ProtocolWarning,
)
from wahlwerk.state import Caucus, Chamber, Mandate

CDU_CSU = CaucusOfParties(parties=("cdu", "csu"))
CDU = Party(id="cdu", name="Christlich Demokratische Union Deutschlands", short_name="CDU")
CSU = Party(id="csu", name="Christlich-Soziale Union in Bayern", short_name="CSU")


def _seats(chamber: Chamber) -> list[tuple[str, frozenset[str]]]:
    return [(c.id, c.mandates) for c in chamber.caucuses]


def _union() -> Chamber:
    """cdu.001-002, spd.001, csu.001, with no caucuses."""
    return Chamber.from_seats({"cdu": 2, "spd": 1, "csu": 1}).clear_caucuses()


UNION = frozenset({"cdu.001", "cdu.002", "csu.001"})


# ===========================================================
# form_caucuses
# ===========================================================
def test_form_caucuses_clears_old_caucuses():
    chamber = Chamber.from_seats({"cdu": 2}).form_caucuses(())
    assert chamber.caucuses == ()
    assert chamber.size == 2


def test_form_caucuses_applies_steps_in_order():
    chamber = _union().form_caucuses((CaucusPerParty(), CDU_CSU))
    assert _seats(chamber) == [("spd", frozenset({"spd.001"})), ("cdu-csu", UNION)]


def test_order_of_steps_matters():
    """Grouping first leaves nothing for CaucusPerParty to take from CDU or CSU."""
    chamber = _union().form_caucuses((CDU_CSU, CaucusPerParty()))
    assert _seats(chamber) == [("cdu-csu", UNION), ("spd", frozenset({"spd.001"}))]


def test_form_caucuses_leaves_the_seats_alone():
    before = _union()
    after = before.form_caucuses((CaucusPerParty(), CDU_CSU))
    assert after.mandates == before.mandates


def test_from_seats_uses_caucus_per_party():
    chamber = Chamber.from_seats({"cdu": 2, "spd": 1})
    assert chamber == chamber.form_caucuses((CaucusPerParty(),))


def test_protocol_is_data():
    """Steps compare, hash and print by their parameters, so protocols can be diffed."""
    assert (CaucusPerParty(), CDU_CSU) == (CaucusPerParty(), CaucusOfParties(parties=["cdu", "csu"]))
    assert hash(CDU_CSU) == hash(CaucusOfParties(parties=("cdu", "csu")))
    assert "cdu" in repr(CDU_CSU)


def test_step_is_callable():
    assert CaucusPerParty()(_union()) == CaucusPerParty().apply(_union())


def test_step_base_is_abstract():
    with pytest.raises(TypeError):
        CaucusStep()


# ===========================================================
# CaucusPerParty
# ===========================================================
def test_caucus_per_party_skips_vacant_and_unrecorded_seats():
    chamber = Chamber(
        mandates=(
            Mandate(id="m.1", party="spd"),
            Mandate(id="m.2", party="spd", is_vacant=True),
            Mandate(id="m.3"),
            Mandate(id="m.4", party="afd"),
        )
    )
    formed = chamber.form_caucuses((CaucusPerParty(),))
    assert _seats(formed) == [("spd", frozenset({"m.1"})), ("afd", frozenset({"m.4"}))]
    assert formed.seats_without_caucus == 2


def test_caucus_per_party_uses_the_party_id():
    (caucus,) = Chamber.from_seats({CDU: 1}).caucuses
    assert caucus.id == "cdu"


def test_caucus_per_party_keeps_seats_already_in_a_caucus():
    chamber = _union().with_caucuses((Caucus(id="union", mandates={"cdu.001", "csu.001"}),))
    formed = CaucusPerParty()(chamber)
    assert _seats(formed) == [
        ("union", frozenset({"cdu.001", "csu.001"})),
        ("cdu", frozenset({"cdu.002"})),
        ("spd", frozenset({"spd.001"})),
    ]


# ===========================================================
# CaucusOfParties
# ===========================================================
def test_group_parties_takes_seats_from_other_caucuses():
    chamber = CDU_CSU(Chamber.from_seats({"cdu": 2, "spd": 1, "csu": 1}))
    assert _seats(chamber) == [("spd", frozenset({"spd.001"})), ("cdu-csu", UNION)]


def test_group_parties_accepts_party_objects_for_their_ids():
    step = CaucusOfParties(parties=(CDU, "csu"))
    assert step.parties == ("cdu", "csu")
    assert step.id == "cdu-csu"
    assert step == CDU_CSU


def test_group_parties_with_explicit_id():
    step = CaucusOfParties(parties=("cdu", "csu"), id="union")
    (caucus,) = step(_union()).caucuses
    assert (caucus.id, caucus.mandates) == ("union", UNION)


def test_group_parties_without_seats_changes_nothing_and_warns():
    chamber = Chamber.from_seats({"spd": 1})
    with pytest.warns(
        ProtocolWarning, match=r"only \[\] of \['cdu', 'csu'\] have filled seats; no caucus formed"
    ):
        assert CaucusOfParties(parties=("cdu", "csu"))(chamber) == chamber


def test_group_parties_with_one_party_present_changes_nothing_and_warns():
    """One party alone is not a grouping: it keeps its own caucus."""
    chamber = Chamber.from_seats({"cdu": 2, "spd": 1})
    with pytest.warns(
        ProtocolWarning, match=r"only \['cdu'\] of \['cdu', 'csu'\] have filled seats; no caucus formed"
    ):
        assert CDU_CSU(chamber) == chamber


def test_group_parties_with_a_party_missing_still_forms_and_warns():
    step = CaucusOfParties(parties=("cdu", "csu", "fdp"))
    with pytest.warns(
        ProtocolWarning,
        match=r"\['fdp'\] have no filled seats; forming 'cdu-csu-fdp' from \['cdu', 'csu'\] only",
    ):
        formed = step(_union())
    assert ("cdu-csu-fdp", UNION) in _seats(formed)


def test_group_parties_with_all_parties_present_does_not_warn():
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        CDU_CSU(_union())


def test_protocol_warning_can_be_escalated():
    with warnings.catch_warnings():
        warnings.simplefilter("error", ProtocolWarning)
        with pytest.raises(ProtocolWarning):
            CDU_CSU(Chamber.from_seats({"cdu": 1}))


def test_group_parties_skips_vacant_seats():
    chamber = Chamber(
        mandates=(
            Mandate(id="m.1", party="cdu"),
            Mandate(id="m.2", party="csu"),
            Mandate(id="m.3", party="csu", is_vacant=True),
        )
    )
    assert _seats(CDU_CSU(chamber)) == [("cdu-csu", frozenset({"m.1", "m.2"}))]


def test_party_with_only_vacant_seats_counts_as_missing():
    chamber = Chamber(
        mandates=(Mandate(id="m.1", party="cdu"), Mandate(id="m.2", party="csu", is_vacant=True))
    )
    with pytest.warns(ProtocolWarning, match=r"only \['cdu'\]"):
        assert CDU_CSU(chamber) == chamber


@pytest.mark.parametrize(
    "bad",
    [
        {"parties": ("cdu",)},
        {"parties": ("cdu", "cdu")},
        {"parties": ("CDU", "csu")},
        {"parties": ("cdu", "csu"), "id": "CDU/CSU"},
        {"parties": ("cdu", "csu"), "name": "CDU/CSU"},
        {"parties": ("cdu", "csu"), "short_name": "CDU/CSU"},
        {"parties": ("cdu", "csu"), "members": ()},
    ],
)
def test_group_parties_rejects_bad_parameters(bad):
    with pytest.raises(ValidationError):
        CaucusOfParties(**bad)


def test_with_caucuses_validates_against_the_seats():
    """Every step's output goes through the chamber's caucus checks."""
    with pytest.raises(ValidationError, match="claims mandate 'm.9'"):
        _union().with_caucuses((Caucus(id="spd", mandates={"m.9"}),))
