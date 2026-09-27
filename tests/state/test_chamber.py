import logging

import pytest
from pydantic import ValidationError

from wahlwerk.party import Party
from wahlwerk.state import (
    NON_ATTACHED,
    Caucus,
    Chamber,
    Mandate,
    MandateSource,
    Term,
)

BT = "de.bund.bundestag"


def _m(n: int, **fields: object) -> Mandate:
    """Mandate ``m.<n>``, with any other fields given."""
    return Mandate(id=f"m.{n}", **fields)


def _chamber(*mandates: Mandate, term: Term | None = None) -> Chamber:
    """A chamber holding ``mandates``."""
    return Chamber(term=term, mandates=mandates)


def test_empty_chamber():
    chamber = Chamber()
    assert chamber.body is None
    assert chamber.term is None
    assert chamber.mandates == ()
    assert chamber.caucuses == ()


def test_chamber_with_mandates():
    chamber = _chamber(_m(1), _m(2, party="spd"), term=Term(body=BT, number=21))
    assert len(chamber.mandates) == 2
    assert chamber.mandates[0].party is None
    assert chamber.mandates[1].party == "spd"
    assert chamber.mandates[0].origin.source is MandateSource.UNRECORDED


def test_mandates_and_caucuses_lists_become_tuples():
    chamber = Chamber(mandates=[_m(1)], caucuses=[Caucus(id="spd", mandates={"m.1"})])
    assert isinstance(chamber.mandates, tuple)
    assert isinstance(chamber.caucuses, tuple)


def test_is_hashable():
    term = Term(body=BT)
    assert hash(_chamber(_m(1), term=term)) == hash(_chamber(_m(1), term=term))


def test_mandate_id_twice_is_rejected():
    with pytest.raises(ValidationError, match="mandate 'm.1' appears twice"):
        _chamber(_m(1), _m(1, party="spd"))


def test_body_comes_from_term():
    assert Chamber(term=Term(body=BT)).body == BT


def test_body_is_none_without_term_or_body():
    assert Chamber().body is None
    assert Chamber(term=Term(number=21)).body is None


def test_body_is_not_a_field():
    """The body lives on the term; passing it to the chamber is an error."""
    with pytest.raises(ValidationError):
        Chamber(body=BT)
    assert "body" not in Chamber(term=Term(body=BT)).model_dump()


def test_new_chamber_is_empty():
    chamber = Chamber()
    assert chamber.is_empty
    assert chamber.size == 0


def test_chamber_with_mandates_is_not_empty():
    chamber = _chamber(_m(1), _m(2, party="spd"))
    assert not chamber.is_empty
    assert chamber.size == 2


def test_vacant_seats_still_count():
    """A seat nobody holds is still a seat: vacancy is not absence."""
    chamber = _chamber(_m(1, is_vacant=True), _m(2, is_vacant=True, party="spd"), _m(3))
    assert not chamber.is_empty
    assert chamber.size == 3
    assert chamber.vacant_seats == 2
    assert chamber.filled_seats == 1


def test_derived_properties_are_not_fields():
    """Derived values are computed, never serialised or passed in."""
    dumped = _chamber(_m(1)).model_dump()
    for name in ("size", "is_empty", "vacant_seats", "seats_without_caucus", "is_at_minimum"):
        assert name not in dumped
    with pytest.raises(ValidationError):
        Chamber(size=1)


# ===========================================================
# Caucuses over mandates
# ===========================================================
def test_caucus_twice_is_rejected():
    with pytest.raises(ValidationError, match="caucus 'spd' appears twice"):
        Chamber(
            mandates=(_m(1), _m(2)),
            caucuses=(Caucus(id="spd", mandates={"m.1"}), Caucus(id="spd", mandates={"m.2"})),
        )


def test_empty_caucus_is_rejected():
    with pytest.raises(ValidationError, match="caucus 'spd' has no seats"):
        Chamber(mandates=(_m(1),), caucuses=(Caucus(id="spd"),))


def test_caucus_mandate_must_be_in_the_chamber():
    with pytest.raises(
        ValidationError, match="caucus 'spd' claims mandate 'm.9', which is not in the chamber"
    ):
        Chamber(mandates=(_m(1), _m(2)), caucuses=(Caucus(id="spd", mandates={"m.9"}),))


def test_caucus_mandate_must_not_be_vacant():
    with pytest.raises(ValidationError, match="caucus 'spd' claims vacant mandate 'm.1'"):
        Chamber(
            mandates=(_m(1, is_vacant=True),),
            caucuses=(Caucus(id="spd", mandates={"m.1"}),),
        )


def test_mandate_in_two_caucuses_is_rejected():
    with pytest.raises(
        ValidationError, match="mandate 'm.1' is in both caucus 'spd' and caucus 'bsw'"
    ):
        Chamber(
            mandates=(_m(1),),
            caucuses=(Caucus(id="spd", mandates={"m.1"}), Caucus(id="bsw", mandates={"m.1"})),
        )


def test_seats_without_caucus():
    chamber = Chamber(
        mandates=(_m(1, party="spd"), _m(2, party="spd"), _m(3, party="spd")),
        caucuses=(Caucus(id="spd", mandates={"m.1", "m.3"}),),
    )
    assert chamber.seats_without_caucus == 1


def test_caucus_can_span_parties():
    """A caucus groups seats, whatever party won them (e.g. CDU/CSU)."""
    chamber = Chamber.from_seats({"cdu": 2, "csu": 1})
    merged = Chamber(
        mandates=chamber.mandates,
        caucuses=(
            Caucus(
                id="cdu-csu",
                mandates={"cdu.001", "cdu.002", "csu.001"},
            ),
        ),
    )
    assert merged.seats_without_caucus == 0
    assert merged.seats_by_party == {"cdu": 2, "csu": 1}
    assert merged.seats_by_caucus == {"cdu-csu": 3}


def test_from_seats_by_party_id():
    chamber = Chamber.from_seats({"cdu": 2, "spd": 1})
    assert chamber.size == 3
    assert [m.party for m in chamber.mandates] == ["cdu", "cdu", "spd"]
    assert [(c.id, c.mandates) for c in chamber.caucuses] == [
        ("cdu", frozenset({"cdu.001", "cdu.002"})),
        ("spd", frozenset({"spd.001"})),
    ]
    assert chamber.seats_without_caucus == 0


def test_from_seats_numbers_mandates_per_party():
    chamber = Chamber.from_seats({"cdu": 2, None: 1, "spd": 1}, minimum_mandates=6)
    assert [m.id for m in chamber.mandates] == [
        "cdu.001",
        "cdu.002",
        "non-attached.001",
        "spd.001",
        "vacant.001",
        "vacant.002",
    ]


def test_from_seats_forms_no_caucus_for_zero_seats():
    chamber = Chamber.from_seats({"cdu": 1, "fdp": 0})
    assert [c.id for c in chamber.caucuses] == ["cdu"]


def test_from_seats_by_party_and_mixed():
    spd = Party(id="spd", name="Sozialdemokratische Partei Deutschlands", short_name="SPD")
    by_party = Chamber.from_seats({spd: 1, "cdu": 2})
    by_id = Chamber.from_seats({"spd": 1, "cdu": 2})
    assert by_party.mandates == by_id.mandates
    assert [c.id for c in by_party.caucuses] == [c.id for c in by_id.caucuses]


def test_from_seats_sets_term_and_body():
    term = Term(body=BT, number=21)
    chamber = Chamber.from_seats({"cdu": 1}, term=term)
    assert chamber.term == term
    assert chamber.body == BT


def test_from_seats_empty_table():
    assert Chamber.from_seats({}).is_empty


def test_from_seats_same_party_twice_is_rejected():
    cdu = Party(id="cdu", name="CDU")
    with pytest.raises(ValueError, match="'cdu' appears twice"):
        Chamber.from_seats({cdu: 1, "cdu": 2})
    with pytest.raises(ValueError, match="'cdu' appears twice in the seat table"):
        Chamber.from_seats({cdu: 0, "cdu": 2})


def test_from_seats_negative_is_rejected():
    with pytest.raises(ValueError, match="seats for 'cdu' is negative: -1"):
        Chamber.from_seats({"cdu": -1})


@pytest.mark.parametrize("bad", [2.0, "2", True])
def test_from_seats_non_int_is_rejected(bad):
    with pytest.raises(TypeError, match="seats for 'cdu' must be an int"):
        Chamber.from_seats({"cdu": bad})


@pytest.mark.parametrize("bad", [-1, 2.0, True])
def test_from_seats_bad_minimum_is_rejected(bad):
    with pytest.raises((TypeError, ValueError), match="minimum_mandates"):
        Chamber.from_seats({"cdu": 1}, minimum_mandates=bad)


def test_from_seats_invalid_party_id_is_rejected():
    with pytest.raises(ValidationError):
        Chamber.from_seats({"SPD": 1})


# ===========================================================
# Minimum mandates
# ===========================================================
def test_minimum_unknown_answers_false():
    chamber = Chamber.from_seats({"cdu": 2})
    assert chamber.minimum_mandates is None
    assert not (chamber.is_below_minimum or chamber.is_above_minimum or chamber.is_at_minimum)


def test_from_seats_pads_short_table_with_vacant_seats():
    chamber = Chamber.from_seats({"cdu": 2, "spd": 1}, minimum_mandates=5)
    assert chamber.size == 5
    assert chamber.filled_seats == 3
    assert chamber.vacant_seats == 2
    assert all(m.is_vacant and m.party is None for m in chamber.mandates[3:])
    assert [c.id for c in chamber.caucuses] == ["cdu", "spd"]
    assert chamber.seats_without_caucus == 2
    assert chamber.is_below_minimum
    assert not chamber.is_at_minimum


def test_from_seats_at_minimum():
    chamber = Chamber.from_seats({"cdu": 2, "spd": 1}, minimum_mandates=3)
    assert len(chamber.caucuses) == 2
    assert chamber.is_at_minimum
    assert not chamber.is_below_minimum and not chamber.is_above_minimum


def test_from_seats_above_minimum_is_kept():
    """More seats than the minimum, as with Überhang, are not trimmed."""
    chamber = Chamber.from_seats({"cdu": 4}, minimum_mandates=3)
    assert chamber.size == 4
    assert chamber.is_above_minimum


def test_minimum_counts_filled_seats_not_size():
    chamber = Chamber(
        mandates=tuple(_m(n, is_vacant=True) for n in range(3)), minimum_mandates=3
    )
    assert chamber.size == 3
    assert chamber.is_below_minimum


def test_minimum_must_not_be_negative():
    with pytest.raises(ValidationError):
        Chamber(minimum_mandates=-1)


def test_unknown_field_is_rejected():
    with pytest.raises(ValidationError):
        Chamber(seats=630)


# ===========================================================
# Seats per party and display
# ===========================================================
def _bundestag() -> Chamber:
    return Chamber.from_seats(
        {"spd": 120, "cdu-csu": 208, "afd": 152},
        term=Term(body=BT, number=21),
    )


def test_seats_by_party_counts_in_order_of_appearance():
    chamber = _chamber(_m(1, party="spd"), _m(2), _m(3, party="spd"))
    assert chamber.seats_by_party == {"spd": 2, None: 1}
    assert list(_bundestag().seats_by_party) == ["spd", "cdu-csu", "afd"]


def test_repr_is_a_text_table():
    text = repr(_bundestag())
    lines = text.splitlines()
    assert lines[0] == "Chamber de.bund.bundestag, term 21: 480 seats"
    assert lines[1].split() == ["party", "seats", "share"]
    assert lines[3].split() == ["spd", "120", "25.0%"]
    assert len(lines) == 6


def test_repr_of_empty_and_unrecorded_chambers():
    assert repr(Chamber()) == "Chamber: 0 seats"
    assert "unrecorded" in repr(_chamber(_m(1)))


def test_repr_html_is_a_table():
    html = _bundestag()._repr_html_()
    assert html.startswith("<table") and html.endswith("</table>")
    assert html.count("<tr>") == 4
    assert "de.bund.bundestag, term 21" in html


def test_fancy_html_is_a_hemicycle():
    card = _bundestag().fancy_html()
    assert isinstance(card, str)
    assert card._repr_html_() == card
    assert card.count("<circle") == 480
    assert "de.bund.bundestag, term 21" in card
    assert "Chamber" not in card
    assert "majority" not in card


def test_fancy_html_as_half_pie():
    card = _bundestag().fancy_html(kind="pie")
    assert "<circle" not in card
    assert card.count("<path") == 3


def test_has_caucuses():
    assert Chamber.from_seats({"cdu": 1}).has_caucuses
    assert not Chamber.from_seats({"cdu": 1}).clear_caucuses().has_caucuses
    assert Chamber(mandates=(_m(1),), caucuses=(Caucus(id="spd", mandates={"m.1"}),)).has_caucuses


def test_clear_caucuses_keeps_the_seats():
    chamber = Chamber.from_seats({"cdu": 2, "spd": 1}, minimum_mandates=4)
    cleared = chamber.clear_caucuses()
    assert cleared.caucuses == ()
    assert cleared.mandates == chamber.mandates
    assert cleared.minimum_mandates == 4
    assert cleared.seats_without_caucus == 4


def test_from_seats_logs_padding(caplog):
    with caplog.at_level(logging.INFO, logger="wahlwerk"):
        Chamber.from_seats({"cdu": 3}, minimum_mandates=5)
    assert "seat table fills 3 of 5 seats; padding 2 vacant seats" in caplog.text


def test_from_seats_logs_nothing_without_padding(caplog):
    with caplog.at_level(logging.INFO, logger="wahlwerk"):
        Chamber.from_seats({"cdu": 5}, minimum_mandates=5)
    assert caplog.text == ""


# ===========================================================
# Non-attached seats
# ===========================================================
def test_non_attached_seats_from_the_seat_table():
    chamber = Chamber.from_seats({"afd": 149, "spd": 120, NON_ATTACHED: 3})
    assert chamber.size == 272
    assert chamber.filled_seats == 272
    assert chamber.non_attached_seats == 3
    assert [c.id for c in chamber.caucuses] == ["afd", "spd"]
    assert all(m.party is None and not m.is_vacant for m in chamber.mandates[269:])


def test_non_attached_seats_count_towards_the_minimum():
    """They are filled seats: no vacant padding is added for them."""
    chamber = Chamber.from_seats({"cdu": 3, "non-attached": 2}, minimum_mandates=5)
    assert chamber.vacant_seats == 0
    assert chamber.is_at_minimum


def test_non_attached_excludes_vacant_seats():
    chamber = Chamber.from_seats({"cdu": 3, NON_ATTACHED: 1}, minimum_mandates=6)
    assert chamber.vacant_seats == 2
    assert chamber.seats_without_caucus == 3
    assert chamber.non_attached_seats == 1


def test_non_attached_is_unknown_without_caucuses():
    assert Chamber.from_seats({"cdu": 3}).clear_caucuses().non_attached_seats is None
    assert Chamber.from_seats({"cdu": 3}).non_attached_seats == 0


def test_party_may_not_use_the_reserved_id():
    with pytest.raises(ValueError, match="party id 'non-attached' is reserved"):
        Chamber.from_seats({Party(id="non-attached", name="x"): 1})


# ===========================================================
# Caucus protocol and recorded membership
# ===========================================================
def test_all_seats_non_attached_is_known():
    """No caucus at all is still a recorded fact after from_seats."""
    chamber = Chamber.from_seats({None: 3})
    assert not chamber.has_caucuses
    assert chamber.are_caucuses_recorded
    assert chamber.non_attached_seats == 3
    assert chamber.seats_by_caucus == {NON_ATTACHED: 3}


def test_empty_protocol_forms_no_caucuses():
    chamber = Chamber.from_seats({"cdu": 2, "spd": 1}, caucus_protocol=())
    assert chamber.caucuses == ()
    assert chamber.non_attached_seats == 3


def test_explicit_protocol_is_used():
    from wahlwerk.process.caucus import CaucusOfParties, CaucusPerParty

    chamber = Chamber.from_seats(
        {"cdu": 2, "csu": 1},
        caucus_protocol=(CaucusPerParty(), CaucusOfParties(parties=("cdu", "csu"))),
    )
    assert chamber.seats_by_caucus == {"cdu-csu": 3}


def test_cleared_caucuses_are_unknown():
    chamber = Chamber.from_seats({None: 3}).clear_caucuses()
    assert not chamber.are_caucuses_recorded
    assert chamber.non_attached_seats is None


def test_direct_chamber_without_caucuses_is_unknown():
    assert Chamber(mandates=(_m(1),)).non_attached_seats is None


def test_form_caucuses_records_membership():
    chamber = Chamber(mandates=(_m(1, party="spd"),)).form_caucuses(())
    assert chamber.are_caucuses_recorded
    assert chamber.non_attached_seats == 1


def test_non_attached_count_is_checked():
    with pytest.raises(ValueError, match="seats for 'non-attached' is negative"):
        Chamber.from_seats({NON_ATTACHED: -1})


def test_none_is_short_for_non_attached():
    assert Chamber.from_seats({"afd": 2, None: 3}) == Chamber.from_seats({"afd": 2, NON_ATTACHED: 3})


def test_none_and_non_attached_together_are_rejected():
    with pytest.raises(ValueError, match="'non-attached' appears twice"):
        Chamber.from_seats({None: 1, NON_ATTACHED: 1})


def test_seats_by_caucus_shows_non_attached_as_imaginary_caucus():
    chamber = Chamber.from_seats({"afd": 149, "spd": 120, None: 3}, minimum_mandates=275)
    assert chamber.seats_by_caucus == {"afd": 149, "spd": 120, NON_ATTACHED: 3}
    assert sum(chamber.seats_by_caucus.values()) == chamber.filled_seats
    assert NON_ATTACHED not in [c.id for c in chamber.caucuses]


def test_seats_by_caucus_without_non_attached_has_none():
    assert Chamber.from_seats({"afd": 2}).seats_by_caucus == {"afd": 2}


def test_seats_by_caucus_is_unknown_without_caucuses():
    assert Chamber.from_seats({"afd": 2}).clear_caucuses().seats_by_caucus is None


# ===========================================================
# get_caucuses
# ===========================================================
def test_get_caucuses_returns_a_list_of_the_real_caucuses():
    chamber = Chamber.from_seats({"afd": 2, "spd": 1, None: 2})
    caucuses = chamber.get_caucuses()
    assert isinstance(caucuses, list)
    assert [c.id for c in caucuses] == ["afd", "spd"]


def test_get_caucuses_with_non_attached():
    chamber = Chamber.from_seats({"afd": 2, None: 2, "spd": 1}, minimum_mandates=7)
    *real, na = chamber.get_caucuses(include_non_attached=True)
    assert [c.id for c in real] == ["afd", "spd"]
    assert (na.id, na.mandates) == (
        NON_ATTACHED,
        frozenset({"non-attached.001", "non-attached.002"}),
    )
    assert NON_ATTACHED not in [c.id for c in chamber.caucuses]


def test_get_caucuses_without_non_attached_seats_adds_nothing():
    chamber = Chamber.from_seats({"afd": 2})
    assert chamber.get_caucuses(include_non_attached=True) == chamber.get_caucuses()


def test_get_caucuses_with_unknown_membership_adds_nothing():
    chamber = Chamber.from_seats({None: 2}).clear_caucuses()
    assert chamber.get_caucuses(include_non_attached=True) == []


def test_real_caucus_may_not_use_the_reserved_id():
    with pytest.raises(ValidationError, match="caucus id 'non-attached' is reserved"):
        Chamber(mandates=(_m(1),), caucuses=(Caucus(id=NON_ATTACHED, mandates={"m.1"}),))
