"""Golden tests: the Landtag of Mecklenburg-Vorpommern, derived from the votes under the
law in force on election day, must equal the official Mandate der Parteien exactly: party
by party, Wahlkreis by Wahlkreis, Überhang and Ausgleich alike.

2021 is the case for Sec. 58 (6) LKWG M-V: the SPD won 34 of 36 Wahlkreise, 3 more than
its 31 seats of 71, and the house rose to 78 for Ausgleich and to 79 to be odd. 2011 and
2016 have no Überhang. The 2026 result is still preliminary. The fixtures and their
sources are in the ``de.landtag.mv.<year>/README.md`` files beside this one. Golden tests
never skip and never xfail.
"""

import csv
from datetime import date
from pathlib import Path

import pytest

from wahlwerk.io.bundle import read_bundle
from wahlwerk.law.registry import LAWS
from wahlwerk.process.allocation.allocate import allocate, derive
from wahlwerk.process.allocation.mehrsitze import RaiseForAusgleich
from wahlwerk.state.term import Term

HERE = Path(__file__).parent

# Bundle key, election day, Wahlperiode.
ELECTIONS = {
    2011: ("de.landtag.mv.2011", date(2011, 9, 4), 6),
    2016: ("de.landtag.mv.2016", date(2016, 9, 4), 7),
    2021: ("de.landtag.mv.2021", date(2021, 9, 26), 8),
}

# Party columns in the official files, to the tally's party ids.
PARTY_IDS = {
    "SPD": "spd",
    "CDU": "cdu",
    "DIE LINKE": "linke",
    "GRÜNE": "gruene",
    "NPD": "npd",
    "FDP": "fdp",
    "AfD": "afd",
}

LAND = "99"


def official(year):
    """The official seats, as {(Wahlkreis, Mandatstyp): {party id: seats}}; the Land is
    Wahlkreis ``99``. Parties without a seat anywhere are left out."""
    path = HERE / ELECTIONS[year][0] / "mandate.csv"
    with path.open(encoding="latin-1", newline="") as f:
        rows = [row for row in csv.reader(f, delimiter=";") if row]
    header = next(i for i, row in enumerate(rows) if "Mandatstyp" in row)
    names = rows[header]
    wahlkreis, kind = names.index("Wahlkreis"), names.index("Mandatstyp")
    parties = [(i, name) for i, name in enumerate(names[kind + 1 :], start=kind + 1) if name]
    seats = {}
    for row in rows[header + 1 :]:
        counts = {name: int(row[i]) for i, name in parties if row[i] not in ("x", "")}
        seats[row[wahlkreis], row[kind]] = counts
    won = {name for counts in seats.values() for name, n in counts.items() if n}
    assert won <= set(PARTY_IDS), won - set(PARTY_IDS)
    return {
        key: {PARTY_IDS[name]: n for name, n in counts.items() if name in won}
        for key, counts in seats.items()
    }


@pytest.fixture(scope="module", params=sorted(ELECTIONS), ids=str)
def year(request):
    return request.param


@pytest.fixture(scope="module")
def vote(year):
    return read_bundle(HERE / ELECTIONS[year][0])


@pytest.fixture(scope="module")
def law(year):
    return LAWS.in_force("de.mv.landtag", ELECTIONS[year][1])


@pytest.fixture(scope="module")
def chamber(year, vote, law):
    _, elected_on, number = ELECTIONS[year]
    return allocate(vote, law.protocol, term=Term(body="de.mv.landtag", number=number, elected_on=elected_on))


def test_official_file_is_consistent(year):
    seats = official(year)
    direct, lists, total = (seats[LAND, kind] for kind in ("Direktmandate", "Mandate nach Landesliste", "Insgesamt"))
    assert all(total[p] == direct[p] + lists[p] for p in total)
    assert sum(direct.values()) == 36
    assert sum(sum(seats[str(n), "Direktmandate"].values()) for n in range(1, 37)) == 36


def test_the_law_in_force_is_the_lkwg(law):
    assert law.id == "de.mv.lkwg.2011"


def test_seats_per_party_equal_the_official_result(year, chamber):
    total = official(year)[LAND, "Insgesamt"]
    assert chamber.seats_by_party == {p: n for p, n in total.items() if n}
    assert chamber.size == sum(total.values())


def test_wahlkreis_and_list_seats_equal_the_official_result(year, chamber):
    seats = official(year)
    for party in seats[LAND, "Insgesamt"]:
        mine = [m for m in chamber.mandates if m.party == party]
        assert sum(m.id.startswith("wk.") for m in mine) == seats[LAND, "Direktmandate"][party], party
        assert sum(m.id.startswith("list.") for m in mine) == seats[LAND, "Mandate nach Landesliste"][party], party


def test_each_wahlkreis_winner_equals_the_official_result(year, chamber):
    seats = official(year)
    for mandate in chamber.mandates:
        if mandate.id.startswith("wk."):
            number = str(int(mandate.id.split(".")[1]))
            assert seats[number, "Direktmandate"][mandate.party] == 1, mandate.id


def test_ueberhang_and_ausgleich_equal_the_official_result(year, vote, law):
    """The Überhang of the first allocation of 71 seats, and the Ausgleichsmandate the
    raised house gives each party beyond it."""
    seats = official(year)
    raise_at = next(i for i, step in enumerate(law.protocol) if isinstance(step, RaiseForAusgleich))
    first = derive(vote, law.protocol[:raise_at])
    derived = derive(vote, law.protocol)
    ueberhang = {p: n for p, n in seats[LAND, "darunter Überhangmandate"].items() if n}
    assert dict(first.overhang) == ueberhang
    before, after = first.entitlement.as_dict(), derived.entitlement.as_dict()
    ausgleich = {p: after[p] - before[p] for p in after if p not in ueberhang and after[p] > before[p]}
    assert ausgleich == {p: n for p, n in seats[LAND, "darunter Ausgleichsmandate"].items() if n}
    assert derived.overhang == ()
    assert derived.house == {2011: 71, 2016: 71, 2021: 79}[year]


def test_chamber_meets_the_minimum(year, chamber):
    assert chamber.minimum_mandates == 71
    assert not chamber.is_below_minimum
    assert chamber.is_at_minimum == (year != 2021)
    assert chamber.body == "de.mv.landtag"
