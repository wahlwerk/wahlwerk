"""What a vote recorded: input to processes, never replaced by them.

Two cases, told apart by who votes, each in its own subpackage:

- A *popular vote* (:mod:`wahlwerk.vote.popular`) is cast by the electorate, secretly,
  and recorded as counts per unit (:class:`TallyRow`: votes, invalid votes, and the
  people eligible and voting), which are then aggregated into larger units.
- A *chamber vote* (:mod:`wahlwerk.vote.chamber`) is cast by the members of a body (a
  chamber or a committee): the Bundeskanzlerwahl, a vote on a law. Not modelled yet.

This package exposes the two subpackages but not their contents, so the split stays
visible: ``wahlwerk.vote.popular.TallyRow``.
"""

from __future__ import annotations

from wahlwerk.vote import chamber, popular

__all__ = ["chamber", "popular"]
