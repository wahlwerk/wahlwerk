# Golden fixture: Landtag Sachsen-Anhalt, 6 June 2021

The input and the official result for the golden test
[`tests/golden/test_de_landtag_st.py`](../test_de_landtag_st.py), committed so the test
runs offline and never reads wahlwerk-data. This is the election where Sec. 35 (8) LWG
acted: the CDU won 40 of 41 Wahlkreise, and the house rose from 83 to 97 seats.

| File | What | Source |
|---|---|---|
| `election.toml`, `tally.csv` | a bundle (schema 2): the valid Erst- and Zweitstimmen per Wahlkreis and party, Urne and Brief summed; 1230 rows | `LT2021_WBZ.xlsx`, via wahlwerk-data `elections/de/landtag/st/2021` |
| `sitzverteilung.csv` | the official seat distribution, byte for byte | the Statistisches Landesamt's seat file, via wahlwerk-data |

## Sources

- **Votes:** Statistisches Landesamt Sachsen-Anhalt, *Wahl des 8. Landtages von
  Sachsen-Anhalt am 6. Juni 2021: endgültiges Wahlergebnis*,
  <https://wahlergebnisse.sachsen-anhalt.de/wahlen/lt21/erg/csv/LT2021_WBZ.xlsx>,
  retrieved 2026-09-27, SHA-256 `cf077394b91e75c7c867ccaccc41c81bd001df3496364a3e8522679aa5b90a14`.
  The full attribution is in `election.toml`.
- **Seats:** Statistisches Landesamt Sachsen-Anhalt, *Landtagswahl 2021:
  Sitzverteilung*, described by its Datensatzbeschreibung `LT2021_SITZ.pdf` (31 May
  2021, Dezernat 13); SHA-256
  `5d8b59d9c07dab9f2036906c9d3fbbd5fe943a66508bef0b97cf2bfd64806b65`. Its download URL
  is not on record; the result (CDU 40, AfD 23, DIE LINKE 12, SPD 9, FDP 7, GRÜNE 6;
  97 seats, 41 of them from Wahlkreise) is the published one.

Both under Datenlizenz Deutschland Namensnennung 2.0 (dl-de/by-2-0,
<https://www.govdata.de/dl-de/by-2-0>). The votes were changed: reshaped into a long
table and summed per Wahlkreis over Urnen- and Briefwahl. The seat file is unchanged.

## The law

The election was held under the LWG as last amended on 19 March 2021
(`wahlwerk.law.de.st.lwg.LWG_2021`). Its Sec. 1 and 35 are the same as for 2026: at
least 83 seats, 41 Wahlkreise, and the Mehrsitze rule of Sec. 35 (8), (8a).

## How `tally.csv` was made

As for 2026 (see `../de.landtag.st.2026/README.md`), from the wahlwerk-data bundle:

```python
vote = PopularVote.from_key("de.landtag.st.2021", "../wahlwerk-data")
votes = vote.tally.filter(kind="votes").sum_to("wahlkreis")
votes.sum_by("unit", "section", "party", "candidate")  # one row each, channel left blank
```
