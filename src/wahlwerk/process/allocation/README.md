# From a popular vote to a chamber

This is the design for the first *external* process: turning the tally of a popular vote
into a `Chamber`, under an electoral law written as a protocol. Only the first three steps
(`PopularVote`, `Tally`, the hierarchies, and the apportionment methods) exist; everything else here is the plan. The case it is
built against is the Landtag of Sachsen-Anhalt, 2026, under the Wahlgesetz des Landes
Sachsen-Anhalt (LWG LSA) as amended on 6 July 2021.

## The pieces

| Piece | Where | What it is |
|---|---|---|
| `PopularVote` | `vote/popular/` | what the electorate recorded: the `Tally` and its `Source`. Input, holds no law |
| `Tally` | `vote/popular/` | the long table of `TallyRow`s; filters and sums, never stores a sum |
| `Level` | `vote/popular/` | one level of the main hierarchy, and how deep its unit ids are; `Tally.levels`, see below |
| `Hierarchy` | `vote/popular/` | an alternative hierarchy (administrative) as an explicit tree; `PopularVote.hierarchies` |
| thresholds, Ausgleich | `apportionment/threshold.py`, `apportionment/ausgleich.py` | `RelativeThreshold`, `SeatThreshold`, `Exempt`, `AlternativeThresholds`; `overhang`, `Ausgleich` |
| apportionment methods | `apportionment/` | `DHondt`, `SainteLague`, `LinearDivisor` (`divisor.py`), `HareNiemeyer` (`remainder.py`), `MajorityFirst` (`majority.py`): models with no German content; `Tie` in `tie.py` |
| `Allocation` | `process/allocation/base.py` | the working record of one allocation: the tally, totals per level, Wahlkreis results, eligible parties, seat total, entitlement, list seats, overhang |
| `AllocationStep`, `AllocationProtocol` | `process/allocation/base.py` | one rule of the law, and the law as an ordered tuple of them; `check_protocol` refuses a law that reads a fact before it is written |
| steps | `process/allocation/count.py`, `district.py`, `eligibility.py`, `seats.py` | `SumVotes`, `ElectDistricts`, `ApplyThreshold`, `SetSeatTotal`, `ApportionSeats`, `DeductDistrictSeats`; each names the section and level it counts |
| `allocate(vote, protocol)`, `FormChamber` | `process/allocation/allocate.py`, `chamber.py` | the process: applies the protocol, returns a `Chamber` |

The names follow the four terms of the README ("Approach"): the vote is *input*, the
law is a *protocol*, `allocate` is the *process*, the chamber is new *state*. A
counterfactual is the same `PopularVote` under a different protocol.

"Bundle" is only the word for how wahlwerk-data stores a popular vote on disk (a
directory with `election.toml` and `tally.csv`), so it lives on in `io/` as
`read_bundle` and nowhere else.

## Why a popular vote does not build its chamber

Votes are input and `vote/` imports only the foundation. If `PopularVote` formed the
chamber, it would have to own the law, and a counterfactual (the same votes, another
law) would need a second vote object. So the vote stays data, and the process that reads
it lives here. It is an *external* process, since it forms a new unit, so it is a
function in `process/`, not a method on `Chamber`: `state` never imports `vote`.

## From six slots to steps

The earlier design split every law into six fixed slots (tiers, ballots, aggregation,
eligibility, apportionment, assignment), each a typed interface. That split is still a
good map of a law, but Sachsen-Anhalt shows why it cannot be the mechanism:

- apportionment is not one call: § 35 (8) repeats § 35 (4) to (7) in a loop;
- § 35 (6) changes what the apportionment returned;
- the seat total (§ 35 (4)) depends on who won the Wahlkreise (§ 33).

So the process uses the same shape as the caucus steps (`CaucusStep`): **one flat
protocol of steps over one working model**. The six slots survive as the modules the
steps are grouped in, not as types.

- **`Allocation` is the working model.** It holds what the law establishes along the
  way: totals per unit, Wahlkreis winners, the parties past the threshold, the seat
  total, each party's entitlement, and its Wahlkreis and list seats. It sits in
  `process/`, not `state/`, since it exists only while a result is being derived.
- **Each step declares what it reads and what it writes.** A protocol that apportions
  before applying the threshold then fails when the law is written, not in the middle
  of a run.
- **A step may hold a protocol.** § 35 (8) is a step whose field is the sub-protocol it
  repeats; there is no other way to write it without special cases.
- **Apportionment methods have no German content.** Opaque keys, exact weights, a seat
  count in; seats or a `Tie` out. `ApportionSeats(method=SainteLague())` is the whole
  counterfactual.
- **The trace comes for free.** The `Allocation` before and after each step is the
  derivation (the "trace" planned in the README).
- **The last step builds the chamber.** Wahlkreis seats get ids `wk.001` to `wk.041`,
  list seats `list.afd.001`, origin `ELECTION`, and `minimum_mandates=83`. People
  (candidates, Ersatzpersonen) wait for the nominations, which are a separate input.

## The law of Sachsen-Anhalt as a protocol

What the law asks for, section by section:

| § LWG LSA | Rule | What it needs |
|---|---|---|
| 1 (1), 10 | at least 83 seats, 41 Wahlkreise, two votes | the base seat count; units nested Wahlbezirk, Wahlkreis, Land |
| 31, 32 S. 1 | count per Wahlbezirk and Briefwahlbezirk, sum to the Wahlkreis | `Tally.sum_to` |
| 32 S. 2, 35 (2) | drop the Zweitstimmen of voters whose Erststimme elected an Einzelbewerber | a count the tally does not hold (see below) |
| 33 | most Erststimmen wins; lot on a tie | Wahlkreis winners, `Tie` |
| 35 (3) | 5 % of valid Zweitstimmen in the Land; no Grundmandatsklausel | the threshold |
| 35 (4) | 83 minus seats won by Einzelbewerber and by parties under 5 % | a seat total that depends on § 33 |
| 35 (5) | Hare-Niemeyer; lot on equal remainders | the apportionment method |
| 35 (6) | a party with more than half the votes but not more than half the seats gets one seat first | a rule that adjusts the apportionment |
| 35 (7) | entitlement minus Wahlkreis seats gives list seats | the assignment |
| 35 (8), (8a) | Mehrsitze: add twice their number and redistribute, twice; then only while the remaining Mehrsitze exceed half the Fraktion size (the seats a fictitious 5 % party would get) | a loop over a sub-protocol |
| 35 (9), 40, 47 | Ersatzpersonen, Nachrücken | later, as events |
| 39 | recount after a party ban | later |

Sketched as a protocol:

```python
LWG_LSA_2021: AllocationProtocol = (
    SumVotes(level="wahlkreis"),                                    # §§ 31, 32
    ElectDistricts(section="erststimme", level="wahlkreis"),        # § 33
    SumVotes(level="land"),                                         # § 35 (2)
    ApplyThreshold(                                                 # § 35 (3)
        threshold=RelativeThreshold(share="5/100"),
        section="zweitstimme",
        level="land",
    ),
    SetHouse(seats=83),                                             # § 1 (1)
    SetSeatTotal(),                                                 # § 35 (4)
    ApportionSeats(                                                 # § 35 (5), (6)
        method=MajorityFirst(method=HareNiemeyer()),
        section="zweitstimme",
        level="land",
    ),
    DeductDistrictSeats(),                                          # § 35 (7)
    RepeatForMehrsitze(                                             # § 35 (8), (8a)
        protocol=(                                                  # § 35 (4) to (7) again
            SetSeatTotal(),
            ApportionSeats(method=MajorityFirst(method=HareNiemeyer()), ...),
            DeductDistrictSeats(),
        ),
        factor=2,
        full_rounds=2,
        fraktion=FraktionSize(share="5/100", section="zweitstimme", level="land"),
    ),
    FormChamber(minimum_mandates=83),                               # § 1 (1)
)
```

All of it exists; the real protocol is `LWG_2021` in `wahlwerk/law/de/st/lwg.py`,
where the house is set by `SetHouse(seats=83)` before `SetSeatTotal()` and the loop
carries a `FraktionSize` for Sec. 35 (8a).

### What 2026 does and does not test

From the tally: 1,315,282 valid Zweitstimmen; past 5 % are AfD, CDU, SPD, Grüne, Linke
and BSW; the Wahlkreise go AfD 38, Linke 3. Hare-Niemeyer on 83 seats, in exact
fractions, gives AfD 39, CDU 15, SPD 8, Grüne 8, Linke 8, BSW 5 (to be checked
against the official Sitzverteilung). So there are no Mehrsitze, and § 35 (6) does not
apply (AfD has 47 % of the votes that count). The golden test covers the threshold,
Hare-Niemeyer and § 35 (7); § 35 (6) and (8) need small constructed tallies.

### Known gap: § 32 S. 2

The Zweitstimmen to drop are those of voters who gave their Erststimme to a successful
Einzelbewerber. Only the two votes counted together can say how many that is, and the
tally counts them apart. It matters only when an Einzelbewerber wins (not in 2026).
When it does, the number is published by the Landeswahlausschuss and has to enter as
an input of its own, not be guessed from the tally.

## The level structure

A tally's units belong to two hierarchies that cross:

- **electoral**: Land, Wahlkreis, Wahlbezirk. The law counts along it (§ 33 per
  Wahlkreis, § 35 per Land), so it is the *main* hierarchy and the unit ids follow it.
- **administrative**: Land, Kreis, Gemeinde, Wahlbezirk. Useful for analysis, but
  Halle, Magdeburg, Dessau-Roßlau, Leuna and Petersberg each lie in several Wahlkreise,
  so it cannot be read off the ids. It sits beside the main one.

### The main hierarchy: in the ids

The tally names every unit by a dotted id, narrowest scope last:

```
de.st.wk.035.gem.15002000.wbz.000001
└─┬─┘ └──┬─┘ └──────────┬──────────┘
 Land  Wahlkreis      Wahlbezirk
```

The unit a row lies in is a prefix of its id, so rolling up is cutting the id. The
`gem.15002000` pair belongs to the Wahlbezirk's id, because Wahlbezirk numbers are only
unique within a Gemeinde; depth 6 is not a level. How deep each level is is recorded
once, next to the tally, in `election.toml` (schema 2), and read into `Tally.levels`:

```toml
[levels]
land = 2
wahlkreis = 4
wahlbezirk = 8
briefwahlbezirk = 8
```

- `Tally` checks it against the rows: every row's `level` is listed, and every unit
  has exactly the listed number of segments.
- `sum_to` takes the level alone: `tally.sum_to("wahlkreis")`. A schema-1 bundle has no
  `[levels]`, so its tally needs the depth given: `sum_to("wahlkreis", depth=4)`.
- Which levels the *law* counts at stays in the protocol, as `SumVotes(level=...)`:
  the data says what levels exist, the law says which ones it uses.

### Alternative hierarchies: an explicit tree

Each alternative hierarchy is declared in `election.toml` with its own levels, broadest
first, and its tree is a file of its own beside the tally:

```toml
[hierarchies.administrative]
levels = ["land", "kreis", "gemeinde"]
```

```
# administrative.csv
unit,level,parent
de.st,land,
de.st.krs.15002,kreis,de.st
de.st.gem.15002000,gemeinde,de.st.krs.15002
de.st.wk.035.gem.15002000.wbz.000001,wahlbezirk,de.st.gem.15002000
```

- Read into `PopularVote.hierarchies` as a `Hierarchy` (`vote.hierarchy("administrative")`),
  checked to be a tree (every parent one level broader) and to cover every counted unit.
- `tally.sum_to("gemeinde", hierarchy=admin)` sums along it: Halle's Wahlbezirke in four
  Wahlkreise become one Gemeinde. The result records no `levels`, since its units are
  not prefixes of each other.
- For Sachsen-Anhalt 2026 it holds 14 Kreise and 218 Gemeinden, built from the
  workbook's Kreisschlüssel and Gemeindeschlüssel. The generator finds Kreise and
  Gemeinden through it when it checks the 822 published sums, so every published `KRS`
  and `GEM` line checks the file.
- The law is never evaluated along an alternative hierarchy.

What the main hierarchy does not cover, and should not until a case needs it: a
Wahlkreis across a Land border, or a redistricting inside one election. Bayern's
Stimmkreise inside Wahlkreise still nest by prefix.

## Order of work

1. `PopularVote` (renamed from `Bundle`, schema version kept in the reader) and `Tally`
   with `filter`, `sum_to`, `sum_by`, `total`. **Done.**
2. The level structure: `[levels]` in `election.toml` (schema 2), `Level` and
   `Tally.levels`, `sum_to` by level name; the administrative hierarchy beside it as
   `[hierarchies.administrative]` and `administrative.csv`. **Done.**
3. Apportionment methods and `Tie`: `DivisorMethod` (`DHondt`, `SainteLague`,
   `LinearDivisor`) and `LargestRemainder` (`HareNiemeyer`); tested by hand, on the 2026
   numbers, and by properties (house monotonicity, quota rule). **Done.**
4. `Allocation`, `AllocationStep`, `AllocationProtocol`, the read/write check
   (`check_protocol`), and the linear steps: `SumVotes`, `ElectDistricts`,
   `ApplyThreshold`, `SetSeatTotal`, `ApportionSeats`, `DeductDistrictSeats`. **Done**:
   on 2026 they give AfD 38 Wahlkreise, Linke 3, six eligible parties, 83 seats, the
   entitlement AfD 39, CDU 15, SPD 8, Grüne 8, Linke 8, BSW 5, list seats AfD 1 and
   Linke 5, and no overhang. Constructed tallies cover Einzelbewerber, a party under
   5 % winning a Wahlkreis, overhang, a Grundmandatsklausel, and ties that stop the
   next step.
5. `FormChamber` and `allocate(...)` building the `Chamber`; the golden test for
   Sachsen-Anhalt 2026 against the official Sitzverteilung
   (`tests/golden/test_de_landtag_st.py`). **Done**: equal party by party, 41
   Wahlkreis and 42 list seats, 83 in all.
6. `RepeatForMehrsitze` and `FraktionSize`, on constructed tallies (balanced within
   the full rounds, kept after them, further rounds beyond half a Fraktion), then the
   Landtag 2021 as a second golden test. **Done**: 2021 gives 97 seats, CDU 40 (all from
   Wahlkreise), AfD 23, Linke 12, SPD 9, FDP 7, Grüne 6, as published. The law moved to
   `law/de/st/lwg.py`; the 2021 and 2026 elections were held under the same Sec. 1 and
   35 (compared word by word; only an editorial change, "im Lande" to "im Land"). Its law-free
   parts exist: `MajorityFirst` (§ 35 (6)), `RelativeThreshold` (§ 35 (3)), `overhang`
   and `Ausgleich`, all in `wahlwerk.apportionment`, and the measures in `wahlwerk.measure`, all
   after votelib (github.com/simberaj/votelib, MIT), the one outside reference used.
7. Later: the § 32 S. 2 input, nominations, Ersatzpersonen and Nachrücken (§ 35 (9),
   § 40), the recount of § 39.
