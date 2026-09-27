from datetime import date

import pytest
from pydantic import ValidationError

from wahlwerk.law.base import Law, LawRegistry
from wahlwerk.law.de.mv.lkwg import LKWG_2011
from wahlwerk.law.de.st.lwg import LWG_2021
from wahlwerk.law.registry import LAWS
from wahlwerk.process.allocation.chamber import FormChamber
from wahlwerk.process.allocation.count import SumVotes
from wahlwerk.process.allocation.district import ElectDistricts


def law(law_id="de.xx.test.1", protocol=None, **fields):
    if protocol is None:
        protocol = LWG_2021.protocol
    return Law(
        id=law_id,
        title="Test",
        citation="none",
        body="de.xx.landtag",
        protocol=protocol,
        **fields,
    )


def test_lwg_2021_is_registered():
    assert LAWS["de.st.lwg.2021"] is LWG_2021
    assert LWG_2021.body == "de.st.landtag"


def test_lwg_2021_governs_the_elections_of_2021_and_2026():
    assert LAWS.in_force("de.st.landtag", date(2021, 6, 6)) is LWG_2021
    assert LAWS.in_force("de.st.landtag", date(2026, 9, 6)) is LWG_2021


def test_lkwg_2011_is_registered():
    assert LAWS["de.mv.lkwg.2011"] is LKWG_2011
    assert LKWG_2011.body == "de.mv.landtag"


def test_lkwg_2011_governs_the_elections_from_2011():
    for elected_on in (date(2011, 9, 4), date(2016, 9, 4), date(2021, 9, 26), date(2026, 9, 20)):
        assert LAWS.in_force("de.mv.landtag", elected_on) is LKWG_2011
    with pytest.raises(KeyError, match="no law for 'de.mv.landtag'"):
        LAWS.in_force("de.mv.landtag", date(2006, 9, 17))


def test_a_misordered_law_fails_when_created():
    with pytest.raises(ValidationError, match=r"reads \['total:wahlkreis'\]"):
        law(protocol=(ElectDistricts(section="erststimme", level="wahlkreis"), FormChamber()))


def test_a_law_must_form_a_chamber():
    with pytest.raises(ValidationError, match="forms no chamber"):
        law(protocol=(SumVotes(level="land"),))


def test_dates_must_be_in_order():
    with pytest.raises(ValidationError, match="ends on 2020-01-01 before it starts"):
        law(in_force_from=date(2021, 1, 1), in_force_until=date(2020, 1, 1))


def test_is_in_force_with_open_sides():
    bounded = law(in_force_from=date(2016, 1, 1), in_force_until=date(2020, 12, 31))
    assert bounded.is_in_force(date(2016, 3, 13))
    assert not bounded.is_in_force(date(2021, 6, 6))
    assert law().is_in_force(date(1990, 10, 14))


def test_registry_lookup():
    first = law("de.xx.test.1", in_force_until=date(2020, 12, 31))
    second = law("de.xx.test.2", in_force_from=date(2021, 1, 1))
    registry = LawRegistry(laws=(first, second))
    assert registry["de.xx.test.2"] is second
    assert registry.get("de.xx.none") is None
    assert len(registry) == 2
    assert list(registry) == [first, second]
    assert registry.in_force("de.xx.landtag", date(2016, 3, 13)) is first
    assert registry.in_force("de.xx.landtag", date(2021, 6, 6)) is second
    with pytest.raises(KeyError, match="no law 'de.xx.none'"):
        registry["de.xx.none"]
    with pytest.raises(KeyError, match="no law for 'de.yy.landtag'"):
        registry.in_force("de.yy.landtag", date(2021, 6, 6))


def test_registry_refuses_duplicates_and_overlaps():
    with pytest.raises(ValidationError, match="registered twice"):
        LawRegistry(laws=(law(), law()))
    overlapping = LawRegistry(laws=(law("de.xx.test.1"), law("de.xx.test.2")))
    with pytest.raises(ValueError, match="several laws"):
        overlapping.in_force("de.xx.landtag", date(2021, 6, 6))
