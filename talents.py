from enum import Enum, auto
from typing import Dict, List, Optional, Tuple, Union


class RequirementType(Enum):
    """Defines the logical evaluation type for talent prerequisites."""
    ALL_OF = auto()  # Requires all specified talents
    ONE_OF = auto()  # Requires at least one of the specified talents


class Talent:
    """Represents an individual talent, its tiers, and dependency rules."""

    def __init__(
            self,
            talent_id: str,
            name: str,
            description: str = "",
            max_tier: int = 1,
            prerequisites: Optional[List[Union[str, Tuple[str, int]]]] = None,
            req_type: RequirementType = RequirementType.ALL_OF
    ):
        self.talent_id = talent_id
        self.name = name
        self.description = description
        self.max_tier = max_tier
        self.prerequisites = prerequisites or []
        self.req_type = req_type


class TalentTree:
    """Manages the master catalog of available talents and validates player unlocks."""

    def __init__(self):
        self.talents: Dict[str, Talent] = {}

    def register_talent(self, talent: Talent) -> None:
        """Registers a talent into the global tree definition."""
        self.talents[talent.talent_id] = talent

    def can_unlock(self, player_talents: Dict[str, int], talent_id: str, target_tier: int) -> bool:
        if talent_id not in self.talents:
            return False

        talent = self.talents[talent_id]
        current_tier = player_talents.get(talent_id, 0)

        if target_tier != current_tier + 1 or target_tier > talent.max_tier:
            return False

        return self.meets_prerequisites(player_talents, talent_id, target_tier)

    def meets_prerequisites(self, player_talents: Dict[str, int], talent_id: str, tier: int) -> bool:
        """
        Checks only whether the prerequisites for holding `tier` in `talent_id`
        are satisfied given player_talents — without the tier-progression gate
        used by can_unlock (which assumes a +1 purchase step).
        """
        talent = self.talents[talent_id]

        if tier <= 0:
            return True

        if not talent.prerequisites:
            return True

        if talent.req_type == RequirementType.ALL_OF:
            for req in talent.prerequisites:
                req_id, req_tier = (req, 1) if isinstance(req, str) else req
                if player_talents.get(req_id, 0) < req_tier:
                    return False
            return True

        elif talent.req_type == RequirementType.ONE_OF:
            for req in talent.prerequisites:
                req_id, req_tier = (req, 1) if isinstance(req, str) else req
                if player_talents.get(req_id, 0) >= req_tier:
                    return True
            return False

        return False

    def can_refund(self, current_tiers: dict, talent_id: str) -> bool:
        hypothetical_tier = current_tiers.get(talent_id, 0) - 1
        hypothetical_tiers = dict(current_tiers)
        hypothetical_tiers[talent_id] = hypothetical_tier

        for other_id, other_tier in current_tiers.items():
            if other_id == talent_id or other_tier <= 0:
                continue
            other_talent = self.talents[other_id]
            if not other_talent.prerequisites:
                continue
            if not self.meets_prerequisites(hypothetical_tiers, other_id, other_tier):
                return False
        return True


# Global master catalog instance
talent_tree = TalentTree()

# --- TALENT REGISTRATION ---

# 1. Cook (3 tiers)
talent_tree.register_talent(Talent(
    talent_id="cook",
    name="Cook",
    description="Cook meals of higher tiers at the cost of stamina",
    max_tier=3
))

talent_tree.register_talent(Talent(
    talent_id="alchemist",
    name="Alchemist",
    description="Prepare various potions",
    max_tier=1
))

# 2. Food Grower (3 tiers)
talent_tree.register_talent(Talent(
    talent_id="food_grower",
    name="Food Grower",
    description="Grow from eating food",
    max_tier=3
))

# 3. Hoard Grower (multi-tier or single-tier, let's assume 3 tiers for consistency)
talent_tree.register_talent(Talent(
    talent_id="hoard_grower",
    name="Hoard Grower",
    description="Grow passively from the troves in your hoard",
    max_tier=3
))

# 4. Growth Spurt (requires at least tier 1 of either Food Grower or Hoard Grower)
talent_tree.register_talent(Talent(
    talent_id="growth_spurt",
    name="Growth Spurt",
    description="Hold back your growth only to grow even bigger in an explosive growth spurt",
    max_tier=1,
    prerequisites=[("food_grower", 1), ("hoard_grower", 1)],
    req_type=RequirementType.ONE_OF
))
