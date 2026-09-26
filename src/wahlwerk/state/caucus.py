from pydantic import Field, model_validator
from datetime import date

from wahlwerk.model import Model, Slug

class Caucus(Model):
    """A grouping over mandates, with its own membership rules.

    Distinct from a party, which is why ``parties`` is a set.
    """

    id: Slug
    name: str = Field(
        default="Unnamed Caucus", 
        description="The name of the caucus."
    )
    #parties: frozenset[PartyId] = frozenset()
    #members: frozenset[CandidateId] = frozenset()

    # @property
    # def is_gemeinschaft(self) -> bool:
    #     """More than one party under one roof."""
    #     return len(self.parties) > 1