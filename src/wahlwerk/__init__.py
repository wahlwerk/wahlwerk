"""wahlwerk -- Electoral and parliamentary systems as rules-as-code.

A deterministic engine parameterised by an electoral law, so that small changes to the
law can be evaluated against real historical votes.

The root exposes the packages for interactive use (``import wahlwerk as ww``), plus
``setup_logger``: ``ww.state.Chamber``, ``ww.vote.popular.TallyRow``, ``ww.io.read_*``,
``ww.process.caucus.Caucus*``, ``ww.apportionment.divisor.SainteLague``. No model is
flattened into the root.

``ww.calc`` is wahlwerk-calc (``wahlwerk_calc``), the formulas the engine computes
with: plain numbers or numpy arrays in and out, ``ww.calc.divisor.sainte_lague(votes, 10)``,
``ww.calc.fragmentation.effective_number(seats)``. It depends on nothing of wahlwerk.
"""

from __future__ import annotations

import logging

import wahlwerk_calc as calc
from wahlwerk import apportionment, io, law, party, process, state, vote
from wahlwerk.log import LOGGER_NAME, setup_logger

__version__ = "0.1.0"

# Silent until the user calls setup_logger(): a library does not configure logging.
logging.getLogger(LOGGER_NAME).addHandler(logging.NullHandler())

__all__ = [
    "apportionment",
    "calc",
    "io",
    "law",
    "party",
    "process",
    "setup_logger",
    "state",
    "vote",
]
