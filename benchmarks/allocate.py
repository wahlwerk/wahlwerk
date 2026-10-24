"""How long an allocation takes, on the golden fixtures and on a tally the size of a
real one.

    uv run python benchmarks/allocate.py            # every golden law, default size
    uv run python benchmarks/allocate.py --units 60 # Wahlbezirke per Wahlkreis

A golden fixture is reduced to votes per Wahlkreis (a few hundred rows). A real bundle
counts per Wahlbezirk: Sachsen-Anhalt 2026 has about 70,000 rows. The second column
splits each Wahlkreis row over ``--units`` Wahlbezirke (the counts divided as evenly as
integers allow, so every sum and every seat stays the same) to time the engine at that
size; the result is checked to equal the fixture's.

Not a test: timings depend on the machine. Run it before and after a change to the
allocation path and compare. Measured on 2026-10-24 for Sachsen-Anhalt 2026, about
70,000 rows: 2.2 s per allocation before a tally was checked once, 0.3 s after.
"""

from __future__ import annotations

import argparse
import statistics
import time
from pathlib import Path

from wahlwerk.io.bundle import read_bundle
from wahlwerk.law.registry import LAWS
from wahlwerk.process.allocation.allocate import allocate
from wahlwerk.vote.popular.popular_vote import PopularVote
from wahlwerk.vote.popular.tally import Level, Tally, TallyRow

GOLDEN = Path(__file__).parents[1] / "tests" / "golden"

# Bundle key in tests/golden, and the law it is replayed under.
CASES = (
    ("de.landtag.st.2021", "de.st.lwg.2021"),
    ("de.landtag.st.2026", "de.st.lwg.2021"),
    ("de.landtag.mv.2011", "de.mv.lkwg.2011"),
    ("de.landtag.mv.2016", "de.mv.lkwg.2011"),
    ("de.landtag.mv.2021", "de.mv.lkwg.2011"),
)


def split(vote: PopularVote, units: int) -> PopularVote:
    """``vote`` with every Wahlkreis row split over ``units`` Wahlbezirke one level
    deeper; sums are unchanged."""
    depth = {level.name: level.depth for level in vote.tally.levels}
    rows: list[TallyRow] = []
    for row in vote.tally.rows:
        if row.level != "wahlkreis":
            rows.append(row)
            continue
        base, extra = divmod(row.count, units)
        for i in range(units):
            rows.append(
                row.model_copy(
                    update={
                        "unit": f"{row.unit}.wbz.{i + 1:03d}",
                        "level": "wahlbezirk",
                        "count": base + (1 if i < extra else 0),
                    }
                )
            )
    levels = (*vote.tally.levels, Level(name="wahlbezirk", depth=depth["wahlkreis"] + 2))
    return vote.model_copy(
        update={"tally": Tally(rows=tuple(rows), levels=levels), "hierarchies": {}}
    )


def timed(vote: PopularVote, law_id: str, repeat: int) -> tuple[float, dict[str, int]]:
    """The median seconds of ``repeat`` allocations, and the seats."""
    protocol = LAWS[law_id].protocol
    times, seats = [], {}
    for _ in range(repeat):
        start = time.perf_counter()
        seats = dict(allocate(vote, protocol).seats_by_party)
        times.append(time.perf_counter() - start)
    return statistics.median(times), seats


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--units", type=int, default=60, help="Wahlbezirke per Wahlkreis")
    parser.add_argument("--repeat", type=int, default=3, help="runs per case, median taken")
    args = parser.parse_args()
    print(f"{'bundle':22} {'law':18} {'rows':>7} {'s':>7}   {'rows':>8} {'s':>7}")
    for key, law_id in CASES:
        vote = read_bundle(GOLDEN / key)
        small, seats = timed(vote, law_id, args.repeat)
        big_vote = split(vote, args.units)
        big, big_seats = timed(big_vote, law_id, args.repeat)
        if big_seats != seats:
            raise SystemExit(f"{key}: the split tally gives other seats: {big_seats} != {seats}")
        print(
            f"{key:22} {law_id:18} {len(vote.tally):>7} {small:>7.3f}   "
            f"{len(big_vote.tally):>8} {big:>7.3f}"
        )


if __name__ == "__main__":
    main()
