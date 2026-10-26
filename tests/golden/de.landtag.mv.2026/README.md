# Golden fixture: Landtag Mecklenburg-Vorpommern, 20 September 2026

The input and the official result for the golden test
[`tests/golden/test_de_landtag_mv.py`](../test_de_landtag_mv.py), committed so the test
runs offline and never reads wahlwerk-data. No Überhang: the AfD won 22 Wahlkreise and the
SPD 14, both within their entitlement of 71 seats; the CDU, without a seat, stayed below
5 %.

| File | What | Source |
|---|---|---|
| `election.toml`, `tally.csv`, `options.csv`, `electoral.csv` | a bundle (schema 4): the valid Erst- and Zweitstimmen per Wahlkreis and option, Urne and Brief summed; 947 rows; the Wahlkreise are the rows, so the electoral hierarchy is the Land alone | the Wahlbezirk file, via wahlwerk-data `elections/de/landtag/mv/2026` |
| `mandate.csv` | the official Mandate der Parteien, per Wahlkreis and for the Land, byte for byte (ISO-8859-1, `;`) | the Landeswahlleiter's `l_mandate.csv` |

## Sources

- **Votes:** Der Landeswahlleiter Mecklenburg-Vorpommern, *Wahl zum Landtag von
  Mecklenburg-Vorpommern am 20. September 2026: endgültiges Ergebnis der Wahlbezirke
  (29.09.2026, 12:11:18 Uhr)*,
  <https://wahlen.mvnet.de/dateien/ergebnisse.2026/landtagswahl/csv/l_wahlbezirke.csv>,
  retrieved 2026-10-27, SHA-256 `5c8cbd3d2874b927747d72d7701ff6e8549c1529417a8ef95b5263db83becda0`.
  The full attribution is in `election.toml`.
- **Seats:** Der Landeswahlleiter Mecklenburg-Vorpommern, *Mandate der Parteien*,
  endgültiges Ergebnis computed on 29 September 2026,
  <https://wahlen.mvnet.de/dateien/ergebnisse.2026/landtagswahl/csv/l_mandate.csv>,
  retrieved 2026-10-27, SHA-256
  `7b80fb3526ba8ddc673bcdbc7fa0231979702ba00f3dd588f133541cabd26f4e`. The result: AfD 32,
  SPD 29, Die Linke 5, GRÜNE 5; 71 seats, 36 of them from Wahlkreise (AfD 22, SPD 14); no
  Überhang- or Ausgleichsmandate.

No licence is stated for either file, only the publisher's name. The votes were changed:
reshaped into a long table and summed per Wahlkreis over Urnen- and Briefwahl. The seat
file is unchanged.

## The law

The election was held under the LKWG M-V (`wahlwerk.law.de.mv.lkwg.LKWG_2011`), whose
Sec. 54 (2), 57 and 58 are unchanged since 1 January 2011: at least 71 seats, 36
Wahlkreise, Hare/Niemeyer with a majority clause, and the Ausgleich of Sec. 58 (6).

## How `tally.csv` was made

From the wahlwerk-data bundle, written with wahlwerk-data-processing's `write_bundle`:

```python
vote = PopularVote.from_key("de.landtag.mv.2026", "../wahlwerk-data")
votes = vote.tally.filter(kind="votes").sum_to("wahlkreis", hierarchy=vote.hierarchy("electoral"))
votes.sum_by("unit", "section", "option")  # one row each, channel left blank
```

Invalid votes, Wahlberechtigte and Wähler are left out: the seat allocation does not use
them.
