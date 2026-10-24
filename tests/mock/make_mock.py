"""Generate the synthetic bundles beside this file.

Run from the engine root with ``uv run python tests/mock/make_mock.py``. Every scenario
draws from its own seeded generator, so a run rewrites the same files. The bundles are
committed; this script is how they were made, and its SHA-256 is each bundle's
``[source] sha256``. What each scenario is for is in ``README.md`` beside this file.

Everything is deliberately generic: parties ``party-a`` to ``party-y``, units
``mock.<scenario>.unit01``, sections ``type1`` and ``type2``, channels ``channel1``
(cast in person) and ``channel2`` (cast by post), options ``option1`` and ``option2``.
What a section or channel means is up to the law under test.
"""

from __future__ import annotations

import csv
import hashlib
import random
from collections.abc import Callable
from pathlib import Path

HERE = Path(__file__).parent
URL = "https://github.com/wahlwerk/wahlwerk/blob/main/tests/mock/make_mock.py"
GENERATED = "2026-10-10"
"""Fixed, so a rerun does not change every ``election.toml``."""

COLUMNS = ("unit", "level", "kind", "section", "channel", "party", "candidate", "option", "count")
IN_PERSON = "channel1"
POSTAL = "channel2"
LEVEL = "unit"

Recipient = tuple[str, str]
"""Who a vote counts for: ``("party", "party-a")``, ``("candidate", ...)``, ``("option", ...)``."""

Shares = dict[str, dict[Recipient, float]]
"""Section to recipient to weight; weights need not sum to one."""


def party(letter: str) -> Recipient:
    return ("party", f"party-{letter}")


def parties(weights: dict[str, float]) -> dict[Recipient, float]:
    """``{"a": 0.4}`` to ``{("party", "party-a"): 0.4}``."""
    return {party(letter): weight for letter, weight in weights.items()}


def split(total: int, weights: dict[Recipient, float] | dict[str, float]) -> dict:
    """Split ``total`` by ``weights`` into integers summing to it (largest remainder)."""
    keys = list(weights)
    whole = sum(weights.values())
    if total == 0 or whole == 0:
        return {key: 0 for key in keys}
    exact = {key: total * weights[key] / whole for key in keys}
    counts = {key: int(exact[key]) for key in keys}
    left = total - sum(counts.values())
    order = sorted(keys, key=lambda key: (-(exact[key] - counts[key]), keys.index(key)))
    for key in order[:left]:
        counts[key] += 1
    return counts


def noisy(weights: dict[Recipient, float], rng: random.Random, sigma: float) -> dict[Recipient, float]:
    """Each weight times a log-normal factor, so units differ around the mean."""
    return {key: weight * rng.lognormvariate(0, sigma) for key, weight in weights.items()}


def row(unit: str, kind: str, count: int, section: str = "", channel: str = "",
        recipient: Recipient | None = None, level: str = LEVEL) -> tuple[str, ...]:
    field, value = recipient if recipient else ("", "")
    return (
        unit, level, kind, section, channel,
        value if field == "party" else "",
        value if field == "candidate" else "",
        value if field == "option" else "",
        str(count),
    )


def unit_rows(unit: str, eligible: int | None, ballots: dict[str, tuple[int, dict[str, tuple[int, dict[Recipient, int]]]]],
                  level: str = LEVEL) -> list[tuple[str, ...]]:
    """The rows of one unit.

    ``ballots`` maps a channel (``""`` when not recorded) to its voters and, per section,
    the invalid votes and the votes per recipient. Every voter casts one vote in every
    section, so valid plus invalid equals the voters in each. ``eligible`` is ``None``
    for a Briefwahlbezirk, whose voters are counted among the eligible of the
    Wahlbezirke.
    """
    rows = [] if eligible is None else [row(unit, "eligible", eligible, level=level)]
    for channel, (voters, sections) in ballots.items():
        rows.append(row(unit, "voters", voters, channel=channel, level=level))
        for section, (invalid, votes) in sections.items():
            assert invalid + sum(votes.values()) == voters, (unit, channel, section)
            rows.append(row(unit, "invalid", invalid, section, channel, level=level))
            rows.extend(row(unit, "votes", count, section, channel, recipient, level)
                        for recipient, count in votes.items())
    assert eligible is None or sum(voters for voters, _ in ballots.values()) <= eligible, unit
    return rows


def cast(voters: int, invalid_rate: float, shares: Shares, rng: random.Random,
         tilt: dict[Recipient, float] | None = None) -> tuple[int, dict[str, tuple[int, dict[Recipient, int]]]]:
    """One channel's ballots: invalid votes drawn around ``invalid_rate``, the rest split
    by ``shares``, each weight times its ``tilt`` (how this channel leans)."""
    sections = {}
    for section, weights in shares.items():
        invalid = min(voters, round(voters * invalid_rate * rng.uniform(0.7, 1.3)))
        if tilt:
            weights = {key: weight * tilt.get(key, 1.0) for key, weight in weights.items()}
        sections[section] = (invalid, split(voters - invalid, weights))
    return voters, sections


def simulate_unit(unit: str, eligible: int, turnout: float, invalid_rate: float, shares: Shares,
             rng: random.Random, postal: float | None = None,
             postal_tilt: dict[Recipient, float] | None = None) -> list[tuple[str, ...]]:
    """A unit's rows; with ``postal``, that share of voters cast by post, which
    has fewer invalid votes and leans by ``postal_tilt``."""
    voters = round(eligible * turnout)
    if postal is None:
        return unit_rows(unit, eligible, {"": cast(voters, invalid_rate, shares, rng)})
    by_post = round(voters * postal)
    return unit_rows(unit, eligible, {
        IN_PERSON: cast(voters - by_post, invalid_rate, shares, rng),
        POSTAL: cast(by_post, invalid_rate / 2, shares, rng, postal_tilt),
    })


def units(name: str, count: int) -> list[str]:
    return [f"mock.{name}.unit{index:02d}" for index in range(1, count + 1)]


def standard(name: str, n_units: int, shares: Callable[[int, random.Random], Shares], *,
             turnout: float, turnout_sd: float = 0.04, invalid: float = 0.012,
             size: int = 60_000, size_spread: float = 0.25, postal: float | None = None,
             postal_tilt: dict[Recipient, float] | None = None,
             turnouts: dict[int, float] | None = None) -> list[tuple[str, ...]]:
    """Units of similar size; ``shares(index, rng)`` gives each its weights, and
    ``turnouts`` fixes the turnout of single units (1-based)."""
    rng = random.Random(name)
    rows = []
    for index, unit in enumerate(units(name, n_units), start=1):
        eligible = round(size * rng.uniform(1 - size_spread, 1 + size_spread))
        rate = (turnouts or {}).get(index) or min(0.99, max(0.05, rng.gauss(turnout, turnout_sd)))
        unit_postal = None if postal is None else min(0.9, max(0.02, rng.gauss(postal, 0.05)))
        rows += simulate_unit(unit, eligible, rate, invalid, shares(index, rng), rng,
                         unit_postal, postal_tilt)
    return rows


def exact(name: str, totals: dict[str, int], n_units: int, *, turnout: float,
          invalid: float, sigma: float = 0.08) -> list[tuple[str, ...]]:
    """One section, ``type1``, whose valid votes sum to exactly ``totals`` per party.

    Each unit but the last splits its valid votes by noisy national shares; the
    last takes what is left, so the party totals come out exact.
    """
    rng = random.Random(name)
    grand = sum(totals.values())
    sizes = {unit: rng.uniform(0.75, 1.25) for unit in units(name, n_units)}
    valid = split(grand, sizes)
    national = parties({letter: count / grand for letter, count in totals.items()})
    left = {party(letter): count for letter, count in totals.items()}
    rows = []
    for position, unit in enumerate(sizes):
        if position < n_units - 1:
            votes = split(valid[unit], noisy(national, rng, sigma))
            for key, count in votes.items():
                left[key] -= count
        else:
            votes = left
            assert all(count >= 0 for count in votes.values()), name
        spoiled = round(valid[unit] * invalid / (1 - invalid))
        voters = valid[unit] + spoiled
        eligible = round(voters / min(0.99, max(0.05, rng.gauss(turnout, 0.03))))
        rows += unit_rows(unit, eligible, {"": (voters, {"type1": (spoiled, votes)})})
    return rows


def leaned(base: dict[str, float], lean: float) -> dict[Recipient, float]:
    """Two-party weights with ``lean`` moved from party B to party A."""
    weights = dict(base)
    weights["a"] += lean
    weights["b"] -= lean
    return parties(weights)


# Scenarios. Each returns its rows; units are 1-based in every rule below.


def two_party_close() -> list[tuple[str, ...]]:
    base = {"a": 0.505, "b": 0.475, "c": 0.02}
    return standard("two-party-close", 20,
                    lambda i, rng: {"type1": leaned(base, rng.uniform(-0.12, 0.12))},
                    turnout=0.65, postal=0.35, postal_tilt={party("b"): 1.12})


def two_party_landslide() -> list[tuple[str, ...]]:
    base = {"a": 0.60, "b": 0.38, "c": 0.01, "d": 0.01}
    return standard("two-party-landslide", 20,
                    lambda i, rng: {"type1": leaned(base, rng.uniform(-0.12, 0.12))},
                    turnout=0.55)


def two_party_inverted() -> list[tuple[str, ...]]:
    # Party A is packed into five units and loses the other ten narrowly.
    def shares(index: int, rng: random.Random) -> Shares:
        lean = 0.30 if index <= 5 else -0.05
        return {"type1": leaned({"a": 0.5, "b": 0.5}, lean + rng.uniform(-0.02, 0.02))}
    return standard("two-party-inverted", 15, shares, turnout=0.60, size_spread=0.05)


def electoral_college() -> list[tuple[str, ...]]:
    # Three large units go heavily to A, twelve small ones narrowly to B.
    sizes = [900_000, 700_000, 600_000, 250_000, 220_000, 200_000, 180_000, 150_000,
             130_000, 110_000, 90_000, 80_000, 70_000, 60_000, 50_000]
    rng = random.Random("electoral-college")
    rows = []
    for index, (unit, eligible) in enumerate(zip(units("electoral-college", 15), sizes), start=1):
        if index <= 3:
            weights = {"a": 0.68, "b": 0.29, "c": 0.02, "d": 0.01}
        else:
            weights = {"a": 0.47 + rng.uniform(-0.01, 0.01), "b": 0.49, "c": 0.025, "d": 0.015}
        rows += simulate_unit(unit, eligible, rng.gauss(0.62, 0.03), 0.008,
                         {"type1": parties(weights)}, rng)
    return rows


def fptp_regional() -> list[tuple[str, ...]]:
    # Party D stands almost only in the last three units, and is strong there.
    national = {"a": 0.34, "b": 0.31, "c": 0.18, "d": 0.003, "e": 0.07, "f": 0.05, "g": 0.03}
    def shares(index: int, rng: random.Random) -> Shares:
        weights = dict(national)
        if index >= 28:
            weights = {key: value * 0.64 for key, value in weights.items()}
            weights["d"] = 0.36
        return {"type1": noisy(parties(weights), rng, 0.25)}
    return standard("fptp-regional", 30, shares, turnout=0.67)


def two_round() -> tuple[list[tuple[str, ...]], list[tuple[str, ...]]]:
    """Both rounds; the second only where the first elected nobody.

    The rule used to pick the second round (one way of many a law may define): elected
    in the first round with more than half the valid votes and at least a quarter of the
    eligible; otherwise a second round between everyone with at least an eighth of the
    eligible, and at least the two strongest.
    """
    name = "two-round"
    national = {"a": 0.27, "b": 0.24, "c": 0.20, "d": 0.11, "e": 0.07, "f": 0.05, "g": 0.035, "h": 0.025}
    special = {
        2: {"a": 0.58, "b": 0.20, "c": 0.12, "d": 0.10},              # decided outright
        5: {"a": 0.55, "b": 0.22, "c": 0.15, "d": 0.08},              # a majority, too few eligible
        8: {"a": 0.31, "b": 0.29, "c": 0.27, "d": 0.08, "e": 0.05},   # three go on
    }
    def shares(index: int, rng: random.Random) -> Shares:
        weights = special.get(index) or noisy(parties(national), rng, 0.3)
        if index in special:
            weights = parties(weights)
        return {"type1": weights}
    first_name = f"{name}-first"
    first = standard(first_name, 12, shares, turnout=0.48, turnouts={2: 0.50, 5: 0.40, 8: 0.66})

    rng = random.Random(f"{name}-second")
    second = []
    for unit in units(first_name, 12):
        here = [r for r in first if r[0] == unit]
        eligible = int(next(r[8] for r in here if r[2] == "eligible"))
        votes = {("party", r[5]): int(r[8]) for r in here if r[2] == "votes"}
        valid = sum(votes.values())
        ranked = sorted(votes, key=lambda key: -votes[key])
        if votes[ranked[0]] * 2 > valid and votes[ranked[0]] * 4 >= eligible:
            continue
        qualified = [key for key in ranked if votes[key] * 8 >= eligible] or ranked[:2]
        if len(qualified) < 2:
            qualified = ranked[:2]
        voters = int(next(r[8] for r in here if r[2] == "voters"))
        weights = {key: votes[key] * rng.uniform(1.0, 1.6) for key in qualified}
        rows = simulate_unit(unit.replace(first_name, f"{name}-second"), eligible,
                        voters / eligible * rng.uniform(0.85, 1.05), 0.03,
                        {"type1": weights}, rng)
        second += rows
    return first, second


def mixed_member() -> list[tuple[str, ...]]:
    # Party A's unit candidates run far ahead of its list (type2).
    type1 = {"a": 0.38, "b": 0.30, "c": 0.12, "d": 0.08, "e": 0.07, "f": 0.03, "g": 0.02}
    type2 = {"a": 0.28, "b": 0.25, "c": 0.15, "d": 0.12, "e": 0.10, "f": 0.07, "g": 0.03}
    def shares(index: int, rng: random.Random) -> Shares:
        lean = rng.uniform(-0.06, 0.08)
        one, two = dict(type1), dict(type2)
        one["a"] += lean
        one["b"] -= lean
        return {"type1": noisy(parties(one), rng, 0.1), "type2": noisy(parties(two), rng, 0.1)}
    return standard("mixed-member", 15, shares, turnout=0.76, postal=0.40,
                    postal_tilt={party("c"): 1.15, party("d"): 0.9})


def basic_mandate() -> list[tuple[str, ...]]:
    # Party G is weak on lists (type2) but its candidates win three units.
    type1 = {"a": 0.33, "b": 0.29, "c": 0.13, "d": 0.10, "e": 0.07, "f": 0.05, "g": 0.02, "h": 0.01}
    type2 = {"a": 0.30, "b": 0.27, "c": 0.14, "d": 0.10, "e": 0.08, "f": 0.05, "g": 0.025, "h": 0.025}
    def shares(index: int, rng: random.Random) -> Shares:
        one, two = dict(type1), dict(type2)
        if index in (2, 8, 13):
            one = {key: value * 0.58 for key, value in one.items()}
            one["g"] = 0.42
            two["g"] = 0.09
        return {"type1": noisy(parties(one), rng, 0.08), "type2": noisy(parties(two), rng, 0.08)}
    return standard("basic-mandate", 15, shares, turnout=0.74, postal=0.30)


def threshold_edge() -> list[tuple[str, ...]]:
    # Of 100 000 valid votes: E 5.01 %, F exactly 5.00 %, G 4.99 %, H exactly 3.00 %.
    totals = {"a": 30_000, "b": 25_000, "c": 18_000, "d": 6_990, "e": 5_010, "f": 5_000,
              "g": 4_990, "h": 3_000, "i": 2_010}
    return exact("threshold-edge", totals, 10, turnout=0.70, invalid=0.012)


def fragmented() -> list[tuple[str, ...]]:
    percent = [14, 12, 11, 9.5, 8, 7, 6, 5, 4.2, 3.6, 3, 2.6, 2.2, 1.9, 1.6, 1.4, 1.2,
               1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3]
    national = parties(dict(zip("abcdefghijklmnopqrstuvwxy", percent)))
    return standard("fragmented", 10, lambda i, rng: {"type1": noisy(national, rng, 0.15)},
                    turnout=0.60)


def few_big() -> list[tuple[str, ...]]:
    national = parties({"a": 0.27, "b": 0.25, "c": 0.23, "d": 0.21, "e": 0.025, "f": 0.015})
    return standard("few-big", 15, lambda i, rng: {"type1": noisy(national, rng, 0.12)},
                    turnout=0.72, postal=0.25, postal_tilt={party("a"): 1.1, party("d"): 0.9})


def dominant() -> list[tuple[str, ...]]:
    # Party A has 50.2 % of the valid votes; most of the rest is scattered.
    percent = {"a": 50.2, "b": 14.0, "c": 9.5, "d": 7.3, "e": 5.6, "f": 4.8, "g": 3.9,
               "h": 2.7, "i": 2.0}
    totals = {letter: round(value * 5_000) for letter, value in percent.items()}
    return exact("dominant", totals, 15, turnout=0.68, invalid=0.01)


def low_turnout() -> list[tuple[str, ...]]:
    national = parties({"a": 0.30, "b": 0.24, "c": 0.17, "d": 0.13, "e": 0.09, "f": 0.07})
    return standard("low-turnout", 20, lambda i, rng: {"type1": noisy(national, rng, 0.2)},
                    turnout=0.18, invalid=0.04, postal=0.50,
                    postal_tilt={party("a"): 1.2, party("f"): 0.8})


def high_turnout() -> list[tuple[str, ...]]:
    national = parties({"a": 0.33, "b": 0.29, "c": 0.18, "d": 0.12, "e": 0.08})
    return standard("high-turnout", 20, lambda i, rng: {"type1": noisy(national, rng, 0.15)},
                    turnout=0.93, turnout_sd=0.02, invalid=0.035, postal=0.15)


def referendum() -> list[tuple[str, ...]]:
    # Option 1 wins the votes but has fewer than a quarter of the eligible.
    def shares(index: int, rng: random.Random) -> Shares:
        one = 0.58 + rng.uniform(-0.08, 0.08)
        return {"type1": {("option", "option1"): one, ("option", "option2"): 1 - one}}
    return standard("referendum", 10, shares, turnout=0.35, invalid=0.01, postal=0.30,
                    postal_tilt={("option", "option2"): 1.1})


def independent_winner() -> list[tuple[str, ...]]:
    # Independents stand in units 4 (and win) and 9 (and lose).
    name = "independent-winner"
    type1 = {"a": 0.32, "b": 0.28, "c": 0.17, "d": 0.13, "e": 0.10}
    type2 = {"a": 0.30, "b": 0.27, "c": 0.18, "d": 0.14, "e": 0.11}
    strength = {4: 0.45, 9: 0.15}
    def shares(index: int, rng: random.Random) -> Shares:
        one = noisy(parties(type1), rng, 0.08)
        if index in strength:
            whole = sum(one.values())
            one = {key: value / whole * (1 - strength[index]) for key, value in one.items()}
            one[("candidate", f"mock.{name}.unit{index:02d}.indep1")] = strength[index]
        return {"type1": one, "type2": noisy(parties(type2), rng, 0.08)}
    return standard(name, 12, shares, turnout=0.70)


def pathological() -> list[tuple[str, ...]]:
    """Written out by hand, see ``README.md``."""
    name = "pathological"
    a, b, c, d = (party(letter) for letter in "abcd")
    table = [  # eligible, voters, invalid, A, B, C, D
        (2_000, 1_500, 20, 700, 700, 80, 0),       # A and B tie for the unit
        (500, 0, 0, 0, 0, 0, 0),                   # nobody voted
        (300, 120, 120, 0, 0, 0, 0),               # every vote invalid
        (1, 1, 0, 0, 0, 1, 0),                     # one eligible, one vote
        (6_000, 4_800, 30, 2_650, 1_000, 1_120, 0),
        (11_000, 8_800, 51, 2_650, 4_300, 1_799, 0),
    ]
    rows = []
    for unit, (eligible, voters, invalid, *votes) in zip(units(name, len(table)), table):
        counts = dict(zip((a, b, c, d), votes))
        rows += unit_rows(unit, eligible, {"": (voters, {"type1": (invalid, counts)})})
    return rows


SCENARIOS: dict[str, Callable[[], list[tuple[str, ...]]]] = {
    "two-party-close": two_party_close,
    "two-party-landslide": two_party_landslide,
    "two-party-inverted": two_party_inverted,
    "electoral-college": electoral_college,
    "fptp-regional": fptp_regional,
    "mixed-member": mixed_member,
    "basic-mandate": basic_mandate,
    "threshold-edge": threshold_edge,
    "fragmented": fragmented,
    "few-big": few_big,
    "dominant": dominant,
    "low-turnout": low_turnout,
    "high-turnout": high_turnout,
    "referendum": referendum,
    "independent-winner": independent_winner,
    "pathological": pathological,
}


# Landtag scenarios: Erst- and Zweitstimme, Urnen- and Briefwahl, with units and levels
# as in the real bundles (``mock.<scenario>.wk.001.wbz.01``), so the Landtag laws run on
# them unchanged and can be compared on the same votes.

WAHLKREISE = 40
WAHLBEZIRKE = 3
URNE = "urne"
BRIEF = "brief"
ERST = "erststimme"
ZWEIT = "zweitstimme"

Profile = Callable[[int, dict[Recipient, float], dict[Recipient, float]],
                   tuple[dict[Recipient, float], dict[Recipient, float]]]
"""Wahlkreis number, its Erst- and Zweitstimme weights, to the weights to use there."""


def boost(weights: dict[Recipient, float], key: Recipient, share: float) -> dict[Recipient, float]:
    """``weights`` with ``key`` at ``share`` of the whole, the rest scaled to fit."""
    rest = sum(value for other, value in weights.items() if other != key)
    scaled = {other: value / rest * (1 - share) for other, value in weights.items() if other != key}
    return {**scaled, key: share}


def landtag(name: str, erst: dict[Recipient, float], zweit: dict[Recipient, float], *,
            turnout: float, brief: float, brief_tilt: dict[Recipient, float] | None = None,
            sigma: float = 0.2, profile: Profile | None = None) -> list[tuple[str, ...]]:
    """40 Wahlkreise of three Wahlbezirke (Urne) and one Briefwahlbezirk (Brief) each.

    A party's regional strength is drawn once per Wahlkreis and applies to both votes,
    so a party strong in a Wahlkreis is strong in both; ``profile`` then sets single
    Wahlkreise (a local stronghold, an Einzelbewerber).
    """
    rng = random.Random(name)
    rows = []
    for wk in range(1, WAHLKREISE + 1):
        unit = f"mock.{name}.wk.{wk:03d}"
        strength = {key: rng.lognormvariate(0, sigma) for key in zweit}
        one = {key: value * strength.get(key, 1.0) for key, value in erst.items()}
        two = {key: value * strength.get(key, 1.0) for key, value in zweit.items()}
        if profile:
            one, two = profile(wk, one, two)
        rate = min(0.95, max(0.1, rng.gauss(turnout, 0.04)))
        by_post = min(0.85, max(0.05, rng.gauss(brief, 0.05)))
        postal = 0
        for wbz in range(1, WAHLBEZIRKE + 1):
            eligible = round(rng.uniform(4_500, 7_500))
            voters = round(eligible * rate)
            postal += round(voters * by_post)
            shares = {ERST: noisy(one, rng, 0.05), ZWEIT: noisy(two, rng, 0.05)}
            urne = cast(voters - round(voters * by_post), 0.015, shares, rng)
            rows += unit_rows(f"{unit}.wbz.{wbz:02d}", eligible, {URNE: urne}, "wahlbezirk")
        shares = {ERST: one, ZWEIT: two}
        rows += unit_rows(f"{unit}.bwb.01", None,
                              {BRIEF: cast(postal, 0.008, shares, rng, brief_tilt)}, "briefwahlbezirk")
    return rows


def fix_zweitstimmen(rows: list[tuple[str, ...]], hundredths: dict[str, int],
                     sink: str = "a") -> list[tuple[str, ...]]:
    """Make the Zweitstimmen exact: a valid total that is a multiple of 10 000, and each
    party ``hundredths`` of a percent of it.

    Votes move only between a party and ``sink`` (or the invalid votes) within one
    Wahlbezirk or Briefwahlbezirk, so voters and Erststimmen stay as they are.
    """
    assert sum(hundredths.values()) == 10_000
    table = [list(r) for r in rows]
    index = {(r[0], r[2], r[5]): position for position, r in enumerate(table) if r[3] == ZWEIT}
    places = sorted({r[0] for r in table if r[3] == ZWEIT})
    sink_party = f"party-{sink}"

    def count(unit: str, kind: str, who: str) -> int:
        return int(table[index[unit, kind, who]][8])

    def add(unit: str, kind: str, who: str, delta: int) -> None:
        cell = table[index[unit, kind, who]]
        cell[8] = str(int(cell[8]) + delta)

    def move(source: tuple[str, str], target: tuple[str, str], amount: int) -> None:
        for unit in places:
            if amount == 0:
                return
            step = min(amount, count(unit, *source))
            add(unit, *source, -step)
            add(unit, *target, step)
            amount -= step
        assert amount == 0, "not enough votes to move"

    def total(who: str) -> int:
        return sum(count(unit, "votes", who) for unit in places)

    valid = sum(int(r[8]) for r in table if r[3] == ZWEIT and r[2] == "votes")
    move(("votes", sink_party), ("invalid", ""), valid % 10_000)
    valid -= valid % 10_000
    for letter, share in hundredths.items():
        who = f"party-{letter}"
        if who == sink_party:
            continue
        gap = valid * share // 10_000 - total(who)
        if gap > 0:
            move(("votes", sink_party), ("votes", who), gap)
        else:
            move(("votes", who), ("votes", sink_party), -gap)
    assert total(sink_party) == valid * hundredths[sink] // 10_000
    return [tuple(r) for r in table]


def landtag_typical() -> list[tuple[str, ...]]:
    # Six parties above five percent, three below; few overhang seats if any.
    return landtag("landtag-typical",
                   parties({"a": 0.33, "b": 0.27, "c": 0.12, "d": 0.09, "e": 0.07, "f": 0.05,
                            "g": 0.03, "h": 0.02, "i": 0.02}),
                   parties({"a": 0.29, "b": 0.24, "c": 0.13, "d": 0.10, "e": 0.08, "f": 0.06,
                            "g": 0.04, "h": 0.03, "i": 0.03}),
                   turnout=0.62, brief=0.30, brief_tilt={party("c"): 1.15, party("b"): 0.9})


def landtag_overhang() -> list[tuple[str, ...]]:
    # A wins nearly every Wahlkreis with a third of the Zweitstimmen.
    return landtag("landtag-overhang",
                   parties({"a": 0.42, "b": 0.21, "c": 0.13, "d": 0.09, "e": 0.07, "f": 0.04,
                            "g": 0.02, "h": 0.02}),
                   parties({"a": 0.33, "b": 0.21, "c": 0.15, "d": 0.11, "e": 0.08, "f": 0.06,
                            "g": 0.03, "h": 0.03}),
                   turnout=0.60, brief=0.35, sigma=0.12)


def landtag_split_wins() -> list[tuple[str, ...]]:
    # A dominates the first half of the Wahlkreise, B the second: both win many.
    def profile(wk: int, one: dict[Recipient, float], two: dict[Recipient, float]):
        strong, weak = (party("a"), party("b")) if wk <= 20 else (party("b"), party("a"))
        for weights in (one, two):
            weights[strong] *= 1.45
            weights[weak] *= 0.6
        return one, two
    return landtag("landtag-split-wins",
                   parties({"a": 0.28, "b": 0.27, "c": 0.12, "d": 0.10, "e": 0.08, "f": 0.06,
                            "g": 0.05, "h": 0.04}),
                   parties({"a": 0.26, "b": 0.25, "c": 0.13, "d": 0.11, "e": 0.09, "f": 0.07,
                            "g": 0.05, "h": 0.04}),
                   turnout=0.66, brief=0.28, sigma=0.15, profile=profile)


def landtag_threshold_edge() -> list[tuple[str, ...]]:
    # Zweitstimmen: E 5.01 %, F exactly 5.00 %, G 4.99 %; 15.5 % lost below five percent.
    hundredths = {"a": 2950, "b": 2200, "c": 1400, "d": 900, "e": 501, "f": 500, "g": 499,
                  "h": 450, "i": 300, "j": 300}
    zweit = parties({letter: value / 10_000 for letter, value in hundredths.items()})
    rows = landtag("landtag-threshold-edge", zweit, zweit, turnout=0.64, brief=0.30, sigma=0.15)
    return fix_zweitstimmen(rows, hundredths)


def landtag_bare_majority() -> list[tuple[str, ...]]:
    # A has 46.2 % of the Zweitstimmen, but 50.1 % of those for parties above five percent.
    hundredths = {"a": 4620, "b": 2000, "c": 1200, "d": 800, "e": 600, "f": 300, "g": 250,
                  "h": 230}
    zweit = parties({letter: value / 10_000 for letter, value in hundredths.items()})
    erst = parties({"a": 0.50, "b": 0.22, "c": 0.11, "d": 0.07, "e": 0.05, "f": 0.02,
                    "g": 0.02, "h": 0.01})
    rows = landtag("landtag-bare-majority", erst, zweit, turnout=0.63, brief=0.30, sigma=0.15)
    return fix_zweitstimmen(rows, hundredths)


def landtag_grundmandat() -> list[tuple[str, ...]]:
    # G has some three percent of the Zweitstimmen but wins three Wahlkreise.
    def profile(wk: int, one: dict[Recipient, float], two: dict[Recipient, float]):
        if wk in (5, 18, 31):
            one, two = boost(one, party("g"), 0.40), boost(two, party("g"), 0.10)
        return one, two
    return landtag("landtag-grundmandat",
                   parties({"a": 0.32, "b": 0.27, "c": 0.13, "d": 0.10, "e": 0.08, "f": 0.05,
                            "g": 0.02, "h": 0.03}),
                   parties({"a": 0.29, "b": 0.25, "c": 0.14, "d": 0.11, "e": 0.08, "f": 0.06,
                            "g": 0.025, "h": 0.035}),
                   turnout=0.61, brief=0.32, sigma=0.15, profile=profile)


def landtag_einzelbewerber() -> list[tuple[str, ...]]:
    # An Einzelbewerber wins Wahlkreis 17; another stands in Wahlkreis 30 and loses.
    name = "landtag-einzelbewerber"
    strength = {17: 0.41, 30: 0.15}
    def profile(wk: int, one: dict[Recipient, float], two: dict[Recipient, float]):
        if wk in strength:
            one = boost(one, ("candidate", f"mock.{name}.wk.{wk:03d}.einzelbewerber"), strength[wk])
        return one, two
    return landtag(name,
                   parties({"a": 0.31, "b": 0.27, "c": 0.13, "d": 0.11, "e": 0.08, "f": 0.05,
                            "g": 0.03, "h": 0.02}),
                   parties({"a": 0.28, "b": 0.25, "c": 0.14, "d": 0.12, "e": 0.09, "f": 0.06,
                            "g": 0.03, "h": 0.03}),
                   turnout=0.60, brief=0.30, sigma=0.15, profile=profile)


def landtag_fragmented() -> list[tuple[str, ...]]:
    # Twelve parties, the largest under a fifth, seven above five percent.
    weights = parties({"a": 0.19, "b": 0.17, "c": 0.15, "d": 0.11, "e": 0.09, "f": 0.07,
                       "g": 0.06, "h": 0.045, "i": 0.04, "j": 0.03, "k": 0.02, "l": 0.01})
    return landtag("landtag-fragmented", weights, weights, turnout=0.58, brief=0.30, sigma=0.16)


def landtag_briefwahl_heavy() -> list[tuple[str, ...]]:
    # Most vote by post, and postal voters lean to A while the Urne leans to B.
    return landtag("landtag-briefwahl-heavy",
                   parties({"a": 0.26, "b": 0.33, "c": 0.13, "d": 0.10, "e": 0.08, "f": 0.05,
                            "g": 0.03}),
                   parties({"a": 0.24, "b": 0.30, "c": 0.14, "d": 0.11, "e": 0.09, "f": 0.07,
                            "g": 0.04}),
                   turnout=0.48, brief=0.60, sigma=0.12,
                   brief_tilt={party("a"): 1.3, party("b"): 0.8})


LANDTAG: dict[str, Callable[[], list[tuple[str, ...]]]] = {
    "landtag-typical": landtag_typical,
    "landtag-overhang": landtag_overhang,
    "landtag-split-wins": landtag_split_wins,
    "landtag-threshold-edge": landtag_threshold_edge,
    "landtag-bare-majority": landtag_bare_majority,
    "landtag-grundmandat": landtag_grundmandat,
    "landtag-einzelbewerber": landtag_einzelbewerber,
    "landtag-fragmented": landtag_fragmented,
    "landtag-briefwahl-heavy": landtag_briefwahl_heavy,
}


ELECTION = """\
schema = 2

[source]
publisher = "wahlwerk"
title = "Synthetic election: {name}"
url = "{url}"
licence = "Apache-2.0"
attribution = "Synthetic data generated by wahlwerk (tests/mock/make_mock.py); no real election."
retrieved = {generated}
sha256 = "{sha256}"

[levels]
{levels}
"""

LEVELS = "whole = 2\nunit = 3"
LANDTAG_LEVELS = "land = 2\nwahlkreis = 4\nwahlbezirk = 6\nbriefwahlbezirk = 6"


def write(name: str, rows: list[tuple[str, ...]], sha256: str, levels: str = LEVELS) -> None:
    folder = HERE / name
    folder.mkdir(exist_ok=True)
    text = ELECTION.format(name=name, url=URL, generated=GENERATED, sha256=sha256, levels=levels)
    (folder / "election.toml").write_text(text, encoding="utf-8", newline="\n")
    with (folder / "tally.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(COLUMNS)
        writer.writerows(rows)


def main() -> None:
    sha256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    for name, make in SCENARIOS.items():
        write(name, make(), sha256)
    first, second = two_round()
    write("two-round-first", first, sha256)
    write("two-round-second", second, sha256)
    for name, make in LANDTAG.items():
        write(name, make(), sha256, LANDTAG_LEVELS)


if __name__ == "__main__":
    main()
