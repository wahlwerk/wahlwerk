"""How long an allocation takes, on the golden fixtures and on a tally the size of a
real one.

    uv run python benchmarks/allocate.py            # every golden law, default size
    uv run python benchmarks/allocate.py --units 60 # Wahlbezirke per Wahlkreis

A golden fixture is reduced to votes per Wahlkreis (a few hundred rows). A real bundle
counts per Wahlbezirk: Sachsen-Anhalt 2026 has about 70,000 rows. The second column
splits each Wahlkreis row over ``--units`` Wahlbezirke (the counts divided as evenly as
integers allow, so every sum and every seat stays the same) to time the engine at that
size; the result is checked to equal the fixture's.

Two times per case: **cold**, the first allocation of an election (its tally summed for
the first time), and **warm**, every further law on the same election (a tally keeps
its sums, so a sweep or an editor pays the summing once).

Not a test: timings depend on the machine. Run it before and after a change to the
allocation path and compare. Measured on 2026-10-24, Sachsen-Anhalt 2026 per Wahlbezirk
(about 70,000 rows): 2.2 s per allocation; 0.3 s once a tally was checked once; then
about 0.15 s cold and a few milliseconds warm once sums were kept and the Land summed
from the Wahlkreise. Unchanged on 2026-10-26 with schema 4, counted along the
``electoral`` hierarchy instead of the ids (about 0.1 s cold, 10 ms warm).
"""

from __future__ import annotations

import argparse
import statistics
import time
from pathlib import Path

from wahlwerk.io.bundle import read_bundle
from wahlwerk.law.registry import LAWS
from wahlwerk.process.allocation.allocate import allocate
from wahlwerk.vote.popular.hierarchy import Hierarchy, HierarchyUnit
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
    """``vote`` with every Wahlkreis row split over ``units`` Wahlbezirke in it; sums are
    unchanged. Along its electoral hierarchy (schema 4), the Wahlbezirke join it; a
    vote whose ids spell the hierarchy (schema 3) gets a level one id pair deeper."""
    rows: list[TallyRow] = []
    placed: list[HierarchyUnit] = []
    for row in vote.tally.rows:
        if row.level != "wahlkreis":
            rows.append(row)
            continue
        base, extra = divmod(row.count, units)
        for i in range(units):
            unit = f"{row.unit}.wbz.{i + 1:03d}"
            rows.append(
                row.model_copy(
                    update={"unit": unit, "level": "wahlbezirk", "count": base + (1 if i < extra else 0)}
                )
            )
            placed.append(HierarchyUnit(unit=unit, level="wahlbezirk", parent=row.unit))
    electoral = vote.hierarchy("electoral") if any(h.name == "electoral" for h in vote.hierarchies) else None
    if electoral is not None:
        # The Wahlkreise were the rows, a level below the hierarchy's own; now the
        # Wahlbezirke are, so the Wahlkreis becomes a level of it.
        levels = electoral.levels if "wahlkreis" in electoral.levels else (*electoral.levels, "wahlkreis")
        tree = Hierarchy(name=electoral.name, levels=levels, units=(*electoral.units, *dict.fromkeys(placed)))
        tally = Tally(rows=tuple(rows), options=vote.tally.options, kinds=vote.tally.kinds)
        return vote.model_copy(update={"tally": tally, "hierarchies": (tree,)})
    depth = {level.name: level.depth for level in vote.tally.levels}
    levels = (*vote.tally.levels, Level(name="wahlbezirk", depth=depth["wahlkreis"] + 2))
    tally = Tally(rows=tuple(rows), levels=levels, options=vote.tally.options, kinds=vote.tally.kinds)
    return vote.model_copy(update={"tally": tally, "hierarchies": ()})


def timed(vote: PopularVote, law_id: str, repeat: int) -> tuple[float, float, dict[str, int]]:
    """Seconds for the first allocation of ``vote`` (cold: nothing summed yet), the
    median of ``repeat`` more (warm: the tally's sums are kept), and the seats."""
    protocol = LAWS[law_id].protocol
    start = time.perf_counter()
    seats = dict(allocate(vote, protocol).seats_by_party)
    cold = time.perf_counter() - start
    warm = []
    for _ in range(repeat):
        start = time.perf_counter()
        allocate(vote, protocol)
        warm.append(time.perf_counter() - start)
    return cold, statistics.median(warm), seats


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--units", type=int, default=60, help="Wahlbezirke per Wahlkreis")
    parser.add_argument("--repeat", type=int, default=3, help="runs per case, median taken")
    args = parser.parse_args()
    print(f"{'':41} {'fixture':>17}   {'real size':>26}")
    print(f"{'bundle':22} {'law':18} {'rows':>6} {'cold':>5} {'warm':>5}   {'rows':>7} {'cold':>6} {'warm':>6}")
    for key, law_id in CASES:
        vote = read_bundle(GOLDEN / key)
        small_cold, small_warm, seats = timed(vote, law_id, args.repeat)
        big_vote = split(vote, args.units)
        big_cold, big_warm, big_seats = timed(big_vote, law_id, args.repeat)
        if big_seats != seats:
            raise SystemExit(f"{key}: the split tally gives other seats: {big_seats} != {seats}")
        print(
            f"{key:22} {law_id:18} {len(vote.tally):>6} {small_cold:>5.3f} {small_warm:>5.3f}   "
            f"{len(big_vote.tally):>7} {big_cold:>6.3f} {big_warm:>6.3f}"
        )

if __name__ == "__main__":
    main()
