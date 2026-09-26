"""wahlwerk -- Electoral and parliamentary systems as rules-as-code.

A deterministic engine parameterised by an electoral law, so that small changes to the
law can be evaluated against real historical votes.
"""

from __future__ import annotations
from wahlwerk.model import Model, Count, Seats, Share, SlotModel
from wahlwerk.ids import Slug

from wahlwerk.state import Chamber, Caucus, Term
import wahlwerk.ids as ids


__version__ = "0.1.0"

__all__ = [
    "Model",
    "Count",
    "Seats",
    "Share",
    "SlotModel",
    "Slug",
    "Chamber",
    "Caucus",
    "Term",
    "ids"
]