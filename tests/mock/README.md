# Mock bundles: synthetic elections for testing laws

Made-up elections in the bundle format (schema 2), so a law can be run against
situations that real data has rarely or never produced. They are not from any real
election, and they are read with `read_bundle` like any other bundle.
[`test_mock_bundles.py`](test_mock_bundles.py) checks that each one adds up and still
has the property it was made for.

## Conventions

Everything is generic, and its meaning is left to the law under test:

| Field | Values | Played as |
|---|---|---|
| `unit` | `mock.<scenario>.district01`, … | a district (Wahlkreis, constituency, state) |
| `level` | `district` (depth 3); `whole` (depth 2) is declared for summing | |
| `section` | `type1`, `type2` | a ballot or vote type: candidate and list vote, first and second round |
| `channel` | `channel1`, `channel2`, blank where not recorded | in person, by post |
| `party` | `party-a` … `party-y` | |
| `candidate` | `mock.<scenario>.district04.indep1` | an independent, with no party |
| `option` | `option1`, `option2` | the answers in a referendum |

Every voter casts one vote in every section, so per district, section and channel the
valid and invalid votes add up to the voters. Postal ballots have fewer invalid votes
and lean slightly towards some parties.

## Scenarios

| Bundle | Districts | Parties | Turnout | Sections | Postal | What it is for |
|---|---|---|---|---|---|---|
| `two-party-close` | 20 | 3 | 65 % | 1 | yes | two parties within a fraction of a point; postal votes lean to B |
| `two-party-landslide` | 20 | 4 | 56 % | 1 | | 61 % to 37 %; wasted votes, winner's bonus |
| `two-party-inverted` | 15 | 2 | 58 % | 1 | | A wins 56 % of the votes but loses most districts (A is packed into five) |
| `electoral-college` | 15, 50 000 to 900 000 eligible | 4 | 62 % | 1 | | A wins the votes and only the three largest districts |
| `fptp-regional` | 30 | 7 | 66 % | 1 | | D has under 5 % overall but wins districts where it is concentrated |
| `two-round-first` | 12 | 8 | 50 % | 1 | | a fragmented first round; district02 is decided, district05 has a majority of votes but under a quarter of the eligible, district08 has three strong parties |
| `two-round-second` | 11 | 2 to 3 each | 47 % | 1 | | the runoffs of `two-round-first` (rule in `make_mock.py`), three parties in district08 |
| `mixed-member` | 15 | 7 | 76 % | 2 | yes | A wins most districts on `type1` with under 30 % of `type2`: overhang |
| `basic-mandate` | 15 | 8 | 73 % | 2 | yes | G has under 5 % of `type2` but wins three districts on `type1` |
| `threshold-edge` | 10 | 9 | 71 % | 1 | | of exactly 100 000 valid votes, E has 5.01 %, F 5.00 %, G 4.99 %, H 3.00 % |
| `fragmented` | 10 | 25 | 61 % | 1 | | the largest party has 14 %, seven have under 1 %: methods diverge |
| `few-big` | 15 | 6 | 72 % | 1 | yes | four parties between 21 % and 27 % |
| `dominant` | 15 | 9 | 67 % | 1 | | A has exactly 50.2 % of the valid votes, the rest is scattered |
| `low-turnout` | 20 | 6 | 17 % | 1 | yes, half | low turnout, 4 % invalid |
| `high-turnout` | 20 | 5 | 93 % | 1 | yes | high turnout, 3.5 % invalid |
| `referendum` | 10 | `option1`, `option2` | 36 % | 1 | yes | option1 wins 56 % of the votes, yet fewer than a quarter of the eligible |
| `independent-winner` | 12 | 5 + 2 independents | 69 % | 2 | | an independent wins district04, another loses district09 |
| `pathological` | 6 | 4 | | 1 | | written by hand: A and B tie in district01; nobody votes in district02; every vote is invalid in district03; one eligible in district04; A and B tie overall (6 000 each, C 3 000, D 0), so quotients tie under D'Hondt and Sainte-Laguë |

Seats, district magnitudes, district weights (`electoral-college`), thresholds and quorums
are parameters of the law, not of the vote, so they are not in the bundles.

## Landtag scenarios

Bundles named `landtag-*` are built like the real Landtag bundles, so the Landtag laws
run on them unchanged and can be compared on the same votes: sections `erststimme` and
`zweitstimme`, levels `land` (`mock.<scenario>`), `wahlkreis` (`.wk.001`), `wahlbezirk`
(`.wk.001.wbz.01`, channel `urne`) and `briefwahlbezirk` (`.wk.001.bwb.01`, channel
`brief`, with no `eligible` row, since its voters are counted among the Wahlbezirke's
eligible). Each has 40 Wahlkreise of three Wahlbezirke and one Briefwahlbezirk; parties
stay `party-a` and so on. A party's regional strength applies to both votes.

The seats are what `LWG_2021` (Sachsen-Anhalt, at least 83) and `LKWG_2011`
(Mecklenburg-Vorpommern, at least 71) make of each, for orientation only; the tests check
that both laws form a chamber, not these numbers.

| Bundle | Zweitstimmen | Brief | What it is for | Seats ST / MV |
|---|---|---|---|---|
| `landtag-typical` | A 28 %, B 23 %, four more above 5 % | 30 % | a baseline; A wins 29 Wahlkreise, some overhang | 91 / 91 |
| `landtag-overhang` | A 33 % | 34 % | A wins all 40 Wahlkreise: Mehrsitze against Ausgleich | 112 / 113 |
| `landtag-split-wins` | A 26 %, B 26 % | 27 % | A wins the first 20 Wahlkreise, B the rest; no overhang | 83 / 71 |
| `landtag-threshold-edge` | E 5.01 %, F 5.00 %, G 4.99 % exactly | 30 % | the threshold; 15.5 % of votes lost below it | 102 / 103 |
| `landtag-bare-majority` | A 46.2 % exactly, 50.1 % of the votes counted | 30 % | the majority clause; A wins every Wahlkreis | 83 / 79 |
| `landtag-grundmandat` | G 3.1 % | 32 % | G wins three Wahlkreise below the threshold | 104 / 105 |
| `landtag-einzelbewerber` | | 30 % | an Einzelbewerber wins Wahlkreis 17, another loses Wahlkreis 30 | 98 / 99 |
| `landtag-fragmented` | 12 parties, largest 19 %, seven above 5 % | 30 % | many parties in the Landtag | 107 / 99 |
| `landtag-briefwahl-heavy` | A 28 %, B 26 % | 60 % | turnout 48 %; Brief leans to A, Urne to B, so Brief flips 27 Wahlkreise | 97 / 95 |

Not modelled by either law yet (see their docstrings): that the Zweitstimmen of voters who
elected an Einzelbewerber are not counted, which the tally cannot express.

## Making them

```bash
uv run python tests/mock/make_mock.py
```

The script seeds a generator per scenario, so a rerun writes the same files; it
overwrites every bundle here. Each `election.toml` carries the script's SHA-256 and a
fixed date. Change the script, rerun it, and commit the script and the bundles together.

## Licence

Synthetic, the engine's own work: Apache-2.0, like the rest of this repository.
