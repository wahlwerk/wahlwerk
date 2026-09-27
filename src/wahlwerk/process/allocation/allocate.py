"""The process itself: a popular vote and an electoral law in, a chamber out."""

from __future__ import annotations

import logging

from wahlwerk.process.allocation.base import (
    Allocation,
    AllocationProtocol,
    check_protocol,
)
from wahlwerk.state.chamber import Chamber
from wahlwerk.state.term import Term
from wahlwerk.vote.popular.popular_vote import PopularVote

__all__ = ["allocate", "derive"]

logger = logging.getLogger(__name__)


def derive(vote: PopularVote, protocol: AllocationProtocol) -> Allocation:
    """Apply ``protocol`` to the tally of ``vote``, step by step; return the whole
    working record, every fact the law established on the way.

    Checks the protocol first (:func:`~wahlwerk.process.allocation.base.check_protocol`),
    so a law in the wrong order fails before any step runs.
    """
    check_protocol(protocol)
    allocation = Allocation(tally=vote.tally)
    for step in protocol:
        allocation = step.apply(allocation)
    logger.debug("derived %s", sorted(allocation.facts))
    return allocation


def allocate(
    vote: PopularVote, protocol: AllocationProtocol, *, term: Term | None = None
) -> Chamber:
    """The chamber that ``protocol`` forms from ``vote``, sitting in ``term`` if given.

    The term (body, dates) is a fact about the election, not the law, so it is passed
    here rather than being a step. Raises ``ValueError`` if the protocol never forms a
    chamber, e.g. because it lacks a
    :class:`~wahlwerk.process.allocation.chamber.FormChamber` step.
    """
    if "chamber" not in check_protocol(protocol):
        raise ValueError("the protocol forms no chamber; end it with FormChamber")
    chamber = derive(vote, protocol).chamber
    if chamber is None:  # every step checks its writes, so this cannot happen
        raise ValueError("the protocol formed no chamber")
    if term is None:
        return chamber
    return Chamber.model_validate({**dict(chamber), "term": term})
