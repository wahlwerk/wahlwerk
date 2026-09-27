"""Geschäftsordnung des Deutschen Bundestages (GO-BT): how the Bundestag's Fraktionen form.

Sec. 10 (1) GO-BT: Fraktionen are associations of at least five per cent of the members
of the Bundestag who belong to the same party, or to parties that, having the same
political aims, do not compete with each other in any Land. The only such pair is CDU and
CSU, whose members form one Fraktion, the Union.

Not modelled: the five per cent minimum (a party below it forms no Fraktion but may be
recognised as a Gruppe, Sec. 10 (4)), and members who leave their Fraktion. So a party
with any seats forms a caucus here.
"""

from __future__ import annotations

from wahlwerk.process.caucus import CaucusOfParties, CaucusPerParty, CaucusProtocol

__all__ = ["CAUCUS_PROTOCOL"]

CAUCUS_PROTOCOL: CaucusProtocol = (
    CaucusOfParties(parties=("cdu", "csu"), id="union"),  # Sec. 10 (1)
    CaucusPerParty(),
)
"""CDU and CSU form the caucus ``union``; every other party forms its own."""
