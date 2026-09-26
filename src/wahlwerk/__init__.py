"""wahlwerk -- Electoral and parliamentary systems as rules-as-code.

A deterministic engine parameterised by an electoral law, so that small changes to the
law can be evaluated against real historical votes.
"""

from __future__ import annotations

import logging

from wahlwerk import ids
from wahlwerk.log import LOGGER_NAME, disable_logging, setup_logger
from wahlwerk.model import Count, Model, Seats, Share
from wahlwerk.party import Party, PartyRegistry
from wahlwerk.process import (
    CaucusPerParty,
    CaucusProtocol,
    CaucusStep,
    GroupParties,
    ProtocolWarning,
)
from wahlwerk.state import (
    NON_ATTACHED,
    Caucus,
    Chamber,
    Mandate,
    MandateOrigin,
    MandateSource,
    Term,
)
from wahlwerk.vote import TallyKind, TallyRow

__version__ = "0.1.0"

# Silent until the user calls setup_logger(): a library does not configure logging.
logging.getLogger(LOGGER_NAME).addHandler(logging.NullHandler())

__all__ = [
    "NON_ATTACHED",
    "Caucus",
    "CaucusPerParty",
    "CaucusProtocol",
    "CaucusStep",
    "Chamber",
    "Count",
    "GroupParties",
    "Mandate",
    "MandateOrigin",
    "MandateSource",
    "Model",
    "Party",
    "PartyRegistry",
    "ProtocolWarning",
    "Seats",
    "Share",
    "TallyKind",
    "TallyRow",
    "Term",
    "disable_logging",
    "ids",
    "setup_logger",
]
