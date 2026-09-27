"""wahlwerk -- Electoral and parliamentary systems as rules-as-code.

A deterministic engine parameterised by an electoral law, so that small changes to the
law can be evaluated against real historical votes.

The root exposes the packages for interactive use (``import wahlwerk as ww``), plus
``setup_logger``: ``ww.state.Chamber``, ``ww.vote.popular.TallyRow``, ``ww.io.read_*``,
``ww.process.caucus.Caucus*``, ``ww.measure.proportionality.*``, ``ww.apportionment.divisor.SainteLague``. No model is flattened into the root.
"""

from __future__ import annotations

import logging

from wahlwerk import apportionment, io, law, measure, party, process, state, vote
from wahlwerk.log import LOGGER_NAME, setup_logger

__version__ = "0.1.0"

# Silent until the user calls setup_logger(): a library does not configure logging.
logging.getLogger(LOGGER_NAME).addHandler(logging.NullHandler())

__all__ = [
    "apportionment",
    "io",
    "law",
    "measure",
    "party",
    "process",
    "setup_logger",
    "state",
    "vote",
]
