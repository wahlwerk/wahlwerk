# Golden fixture: Landtag Mecklenburg-Vorpommern, 26 September 2021

The input and the official result for the golden test
[`tests/golden/test_de_landtag_mv.py`](../test_de_landtag_mv.py), committed so the test
runs offline and never reads wahlwerk-data. This is the election where Sec. 58 (6) acted: the SPD won 34 Wahlkreise against an entitlement of 31 of 71 seats. Hare/Niemeyer first covers its 34 seats in a house of 78 (4 Ausgleichsmandate, within twice the Überhang); 78 is even, so the house is 79, which gives the CDU one seat more.

| File | What | Source |
|---|---|---|
| `election.toml`, `tally.csv` | a bundle (schema 2): the valid Erst- and Zweitstimmen per Wahlkreis and party, Urne and Brief summed; 1176 rows | the Wahlbezirk file, via wahlwerk-data `elections/de/landtag/mv/2021` |
| `mandate.csv` | the official Mandate der Parteien, per Wahlkreis and for the Land, byte for byte (ISO-8859-1, `;`) | the Landeswahlleitung's `L_Mandate.csv` |

## Sources

- **Votes:** Die Landeswahlleiterin Mecklenburg-Vorpommern, *Wahl zum Landtag von Mecklenburg-Vorpommern am 26. September 2021: endgültiges Ergebnis der Wahlbezirke (04.10.2021, 14:19:48 Uhr)*,
  <https://www.laiv-mv.de/static/LAIV/Wahlen/2-Landtagswahlen/2021/Ergebnisse/l_wahlbezirke.csv>, retrieved 2026-09-27, SHA-256 `dc4db0acbd78fc750c8c5b553f6848af12622b99a60aa2fc3471d1d9cef1e23c`.
  The full attribution is in `election.toml`.
- **Seats:** Die Landeswahlleiterin Mecklenburg-Vorpommern, *Mandate der Parteien*, endgültiges Ergebnis
  computed on 4 October 2021, <https://www.laiv-mv.de/static/LAIV/Wahlen/2-Landtagswahlen/2021/Ergebnisse/l_mandate.csv>, retrieved 2026-09-27, SHA-256
  `5d4b46333503d57ef2721455c8c4820a6c6396abf94b709b42c6fd9cf63b5076`. The result: SPD 34, AfD 14, CDU 12, DIE LINKE 9, GRÜNE 5, FDP 5; 79 seats, 36 of them from Wahlkreise; SPD 3 Überhangmandate; Ausgleichsmandate AfD 1, CDU 2, DIE LINKE 1, FDP 1.

No licence is stated for either file, only the publisher's name. The votes were changed:
reshaped into a long table and summed per Wahlkreis over Urnen- and Briefwahl. The seat
file is unchanged.

## The law

The election was held under the LKWG M-V (`wahlwerk.law.de.mv.lkwg.LKWG_2011`), whose
Sec. 54 (2), 57 and 58 are unchanged since 1 January 2011: at least 71 seats, 36
Wahlkreise, Hare/Niemeyer with a majority clause, and the Ausgleich of Sec. 58 (6).

## How `tally.csv` was made

As for Sachsen-Anhalt (see `../de.landtag.st.2026/README.md`), from the wahlwerk-data bundle:

```python
vote = PopularVote.from_key("de.landtag.mv.2021", "../wahlwerk-data")
votes = vote.tally.filter(kind="votes").sum_to("wahlkreis")
votes.sum_by("unit", "section", "party", "candidate")  # one row each, channel left blank
```

Invalid votes, Wahlberechtigte and Wähler are left out: the seat allocation does not use
them.
