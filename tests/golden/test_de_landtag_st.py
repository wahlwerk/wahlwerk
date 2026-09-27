"""Golden tests: the Landtag of Sachsen-Anhalt, derived from the votes under the law in
force on election day, must equal the official Sitzverteilung exactly, party by party,
Wahlkreis and list seats alike.

2021 is the case for Sec. 35 (8): the CDU won 40 of 41 Wahlkreise and the house rose
from 83 to 97. 2026 has no Mehrsitze. The fixtures and their sources are in the
``de.landtag.st.<year>/README.md`` files beside this one. Golden tests never skip and
never xfail.
"""

import csv
from datetime import date
from pathlib import Path

import pytest

from wahlwerk.io.bundle import read_bundle
from wahlwerk.law.registry import LAWS
from wahlwerk.process.allocation.allocate import allocate, derive
from wahlwerk.state.term import Term

HERE = Path(__file__).parent

# Bundle key, election day, Wahlperiode.
ELECTIONS = {
    2021: ("de.landtag.st.2021", date(2021, 6, 6), 8),
    2026: ("de.landtag.st.2026", date(2026, 9, 6), 9),
}

# Party names in the official files (they changed spelling), to the tally's party ids.
PARTY_IDS = {
    "CDU": "cdu",
    "AfD": "afd",
    "DIE LINKE": "linke",
    "Die Linke": "linke",
    "SPD": "spd",
    "GRÜNE": "gruene",
    "BSW": "bsw",
    "FDP": "fdp",
}


def official(year):
    """The official seats per party id, as (total, Wahlkreis, list), and the totals row.

    Columns are read by position: the files name them differently each year."""
    path = HERE / ELECTIONS[year][0] / "sitzverteilung.csv"
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f, delimiter=";"))[1:]
    parties, totals = {}, None
    for _, name, total, wahlkreis, liste in rows:
        seats = (int(total), int(wahlkreis), int(liste))
        if name == "Insgesamt":
            totals = seats
        else:
            parties[PARTY_IDS[name]] = seats
    return parties, totals


@pytest.fixture(scope="module", params=sorted(ELECTIONS), ids=str)
def year(request):
    return request.param


@pytest.fixture(scope="module")
def vote(year):
    return read_bundle(HERE / ELECTIONS[year][0])


@pytest.fixture(scope="module")
def law(year):
    return LAWS.in_force("de.st.landtag", ELECTIONS[year][1])


@pytest.fixture(scope="module")
def chamber(year, vote, law):
    _, elected_on, number = ELECTIONS[year]
    return allocate(vote, law.protocol, term=Term(body="de.st.landtag", number=number, elected_on=elected_on))


def test_official_file_is_consistent(year):
    parties, totals = official(year)
    assert totals == tuple(sum(seats[i] for seats in parties.values()) for i in range(3))
    assert all(total == wahlkreis + liste for total, wahlkreis, liste in parties.values())
    assert totals[1] == 41


def test_the_law_in_force_is_the_lwg(law):
    assert law.id == "de.st.lwg.2021"


def test_seats_per_party_equal_the_official_result(year, chamber):
    parties, totals = official(year)
    assert chamber.seats_by_party == {p: total for p, (total, _, _) in parties.items() if total}
    assert chamber.size == totals[0]


def test_wahlkreis_and_list_seats_equal_the_official_result(year, chamber):
    parties, _ = official(year)
    for party, (_, wahlkreis, liste) in parties.items():
        mine = [m for m in chamber.mandates if m.party == party]
        assert sum(m.id.startswith("wk.") for m in mine) == wahlkreis, party
        assert sum(m.id.startswith("list.") for m in mine) == liste, party


def test_chamber_meets_the_minimum(year, chamber):
    assert chamber.minimum_mandates == 83
    assert not chamber.is_below_minimum
    assert chamber.is_at_minimum == (year == 2026)
    assert chamber.body == "de.st.landtag"


def test_mehrsitze(year, vote, law):
    """2026 has none; in 2021 every Mehrsitz was balanced within the two full rounds of
    Sec. 35 (8), so the house is 97 with no Mehrsitz left unbalanced."""
    derived = derive(vote, law.protocol)
    assert derived.overhang == ()
    assert derived.house == {2021: 97, 2026: 83}[year]
