# Golden fixture: Landtag Mecklenburg-Vorpommern, 4 September 2016

The input and the official result for the golden test
[`tests/golden/test_de_landtag_mv.py`](../test_de_landtag_mv.py), committed so the test
runs offline and never reads wahlwerk-data. There is no Überhang: the SPD won 26 Wahlkreise, exactly its entitlement, the CDU 7 and the AfD 3.

| File | What | Source |
|---|---|---|
| `election.toml`, `tally.csv` | a bundle (schema 2): the valid Erst- and Zweitstimmen per Wahlkreis and party, Urne and Brief summed; 874 rows | the Wahlbezirk file, via wahlwerk-data `elections/de/landtag/mv/2016` |
| `mandate.csv` | the official Mandate der Parteien, per Wahlkreis and for the Land, byte for byte (ISO-8859-1, `;`) | the Landeswahlleitung's `L_Mandate.csv` |

## Sources

- **Votes:** Landesamt für innere Verwaltung Mecklenburg-Vorpommern, *Wahl zum Landtag von Mecklenburg-Vorpommern am 4. September 2016: endgültiges Ergebnis der Wahlbezirke (09.09.2016, 10:44:53 Uhr)*,
  <https://www.laiv-mv.de/static/LAIV/Wahlen/2-Landtagswahlen/2016/Ergebnisseite/L_Wahlbezirke.csv>, retrieved 2026-09-27, SHA-256 `e0abd1b86ca2b8539691387ae081529521692417f5d334492a72f4dd8db6b13c`.
  The full attribution is in `election.toml`.
- **Seats:** Landesamt für innere Verwaltung Mecklenburg-Vorpommern, *Mandate der Parteien*, endgültiges Ergebnis
  computed on 9 September 2016, <https://www.laiv-mv.de/static/LAIV/Wahlen/2-Landtagswahlen/2016/Ergebnisseite/L_Mandate.csv>, retrieved 2026-09-27, SHA-256
  `c4e07d0ce8d31835e49b947608070f3233b7182c2cc9536ea1062d1d23035f0d`. The result: SPD 26, AfD 18, CDU 16, DIE LINKE 11; 71 seats, 36 of them from Wahlkreise; no Überhang.

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
vote = PopularVote.from_key("de.landtag.mv.2016", "../wahlwerk-data")
votes = vote.tally.filter(kind="votes").sum_to("wahlkreis")
votes.sum_by("unit", "section", "party", "candidate")  # one row each, channel left blank
```

Invalid votes, Wahlberechtigte and Wähler are left out: the seat allocation does not use
them.
