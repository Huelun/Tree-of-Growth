import math
import pickle
import random
from enum import Enum
from typing import List, TYPE_CHECKING, Dict
from typing import Optional

import effect
import item

# We use TYPE_CHECKING to avoid circular imports, as Universe likely imports Player.
# One must avoid such messy entanglements in polite society.
if TYPE_CHECKING:
    import universe


class UnitSystem(Enum):
    PRUSSIAN = "Prussian"
    METRIC = "Metric"
    US_CUSTOMARY = "US Customary"


class BodyType(str, Enum):
    ANTHRO_MALE = "Anthro male"
    ANTHRO_FEMALE = "Anthro female"
    SNAKE_MALE = "Snake male"
    SNAKE_FEMALE = "Snake female"
    DRAGON_MALE = "Dragon"
    DRAGON_FEMALE = "Dragoness"
    NAGA_MALE = "Naga male"
    NAGA_FEMALE = "Naga female"


def get_body_preset(preset: BodyType, owner=None):
    """
    Generates a dictionary of body parts based on the BodyType Enum.
    """
    body = {}

    if preset == BodyType.ANTHRO_MALE:
        body['torso'] = Torso(mass=15.75, base=None, owner=owner)
        body['torso'].muscle_limit_frac = (0.80, 5.00)
        body['torso'].fat_limit_frac = (0.15, 10.00)

        body['neck'] = Neck(mass=1.00, base=body['torso'], owner=owner)
        body['head'] = Head(mass=4.00, base=body['neck'], owner=owner)

        body['penis'] = Penis(mass=0.15, base=body['torso'], owner=owner)
        body['testes'] = Testes(mass=0.05, base=body['torso'], owner=owner)

        for side in ['left', 'right']:
            body[f'{side}_arm'] = Limb(mass=1.80, base=body['torso'], owner=owner, l_factor=0.55, wide_c_factor=1.70)
            body[f'{side}_leg'] = Limb(mass=5.40, base=body['torso'], owner=owner, wide_c_factor=1.35)
        # 3. Apply mirroring for symmetrical calculation logic
        body['right_arm'].mirror = body['left_arm']
        body['left_arm'].mirror = body['right_arm']
        body['right_leg'].mirror = body['left_leg']
        body['left_leg'].mirror = body['right_leg']

    elif preset == BodyType.ANTHRO_FEMALE:
        body['torso'] = Torso(mass=10.0, base=None, owner=owner, l_factor=0.20, chest_c_factor=1.05,
                              waist_c_factor=0.75)
        body['torso'].muscle_limit_frac = (0.60, 4.00)
        body['torso'].fat_limit_frac = (0.20, 15.00)

        body['left_breast'] = Breast(mass=0.3, base=body['torso'], owner=owner)
        body['right_breast'] = Breast(mass=0.3, base=body['torso'], owner=owner, mirror=body['left_breast'])
        body['left_breast'].mirror = body['right_breast']

        body['neck'] = Neck(mass=0.8, base=body['torso'], owner=owner)
        body['head'] = Head(mass=3.5, base=body['neck'], owner=owner)

        for side in ['left', 'right']:
            body[f'{side}_arm'] = Limb(mass=1.2, base=body['torso'], owner=owner, l_factor=0.55, wide_c_factor=1.30)
            body[f'{side}_leg'] = Limb(mass=4.0, base=body['torso'], owner=owner, l_factor=0.46, wide_c_factor=1.55)
        # 3. Apply mirroring for symmetrical calculation logic
        body['right_arm'].mirror = body['left_arm']
        body['left_arm'].mirror = body['right_arm']
        body['right_leg'].mirror = body['left_leg']
        body['left_leg'].mirror = body['right_leg']

    elif preset == BodyType.SNAKE_MALE:
        body['torso'] = Torso(mass=12.0, base=None, owner=owner, l_factor=1.15,
                              chest_c_factor=0.95, waist_c_factor=1.05)
        body['neck'] = Neck(mass=1.0, base=body['torso'], l_factor=0.6, c_factor=0.85)
        body['head'] = Head(mass=0.8, base=body['neck'], l_factor=0.15)
        body['tail'] = Tail(mass=15.0, base=body['torso'], owner=owner, l_factor=1.10, c_factor=0.90)
        body['penis'] = Penis(mass=0.11, base=body['torso'], owner=owner)
        body['testes'] = Testes(mass=0.04, base=body['torso'], owner=owner)
        for part in body.values():
            part.muscle_limit_frac = (1.00, 15.00)
            part.set_point_frac = (8.00, 0.50)

    elif preset == BodyType.SNAKE_FEMALE:
        body['torso'] = Torso(mass=12.0, base=None, owner=owner, l_factor=1.15,
                              chest_c_factor=0.95, waist_c_factor=1.15)
        body['neck'] = Neck(mass=1.0, base=body['torso'], l_factor=0.6, c_factor=0.85)
        body['head'] = Head(mass=0.8, base=body['neck'], l_factor=0.15)
        body['tail'] = Tail(mass=15.0, base=body['torso'], owner=owner, l_factor=1.10, c_factor=0.95)
        for part in body.values():
            part.muscle_limit_frac = (1.00, 15.00)
            part.set_point_frac = (8.00, 0.50)

    elif preset == BodyType.DRAGON_MALE:
        body['torso'] = Torso(mass=150.0, base=None, owner=owner, l_factor=0.20, chest_c_factor=1.45,
                              waist_c_factor=1.20, chest_muscle_bias=0.8, chest_fat_bias=0.2,
                              waist_muscle_bias=0.3, waist_fat_bias=0.4)
        body['neck'] = Neck(mass=25.0, base=body['torso'], owner=owner, l_factor=0.55, c_factor=1.15)
        body['head'] = Head(mass=15.0, base=body['neck'], owner=owner)
        body['left_wing'] = Wing(mass=40.0, base=body['torso'], owner=owner)
        body['right_wing'] = Wing(mass=40.0, base=body['torso'], owner=owner, mirror=body['left_wing'])
        body['tail'] = Tail(mass=80.0, base=body['torso'], owner=owner, l_factor=1.8, c_factor=1.2)
        body['penis'] = Penis(mass=6.0, base=body['torso'], owner=owner)
        body['testes'] = Testes(mass=3.0, base=body['torso'], owner=owner)
        for pos in ['front_leg_l', 'front_leg_r', 'back_leg_l', 'back_leg_r']:
            body[pos] = Limb(mass=35.0, base=body['torso'], owner=owner, l_factor=0.45, wide_c_factor=1.70)

    elif preset == BodyType.DRAGON_FEMALE:
        body['torso'] = Torso(mass=140.0, base=None, owner=owner, l_factor=0.20, chest_c_factor=1.35,
                              waist_c_factor=1.15, chest_muscle_bias=0.8, chest_fat_bias=0.2,
                              waist_muscle_bias=0.3, waist_fat_bias=0.4)
        body['neck'] = Neck(mass=22.0, base=body['torso'], owner=owner, l_factor=0.55, c_factor=1.15)
        body['head'] = Head(mass=12.0, base=body['neck'], owner=owner)
        body['tail'] = Tail(mass=55.0, base=body['torso'], owner=owner, l_factor=1.7, c_factor=1.10)
        body['left_wing'] = Wing(mass=40.0, base=body['torso'], owner=owner)
        body['right_wing'] = Wing(mass=40.0, base=body['torso'], owner=owner, mirror=body['left_wing'])
        for pos in ['front_leg_l', 'front_leg_r', 'back_leg_l', 'back_leg_r']:
            body[pos] = Limb(mass=30.0, base=body['torso'], owner=owner, l_factor=0.50, wide_c_factor=1.60)

    elif preset == BodyType.NAGA_MALE:
        body['torso'] = Torso(mass=14.0, base=None, owner=owner, l_factor=0.30,
                              chest_c_factor=1.05, waist_c_factor=0.95)
        body['torso'].muscle_limit_frac = (0.75, 5.50)
        body['torso'].fat_limit_frac = (0.15, 11.00)

        body['neck'] = Neck(mass=1.00, base=body['torso'], owner=owner)
        body['head'] = Head(mass=3.80, base=body['neck'], owner=owner)

        body['penis'] = Penis(mass=0.15, base=body['torso'], owner=owner)
        body['testes'] = Testes(mass=0.05, base=body['torso'], owner=owner)

        for side in ['left', 'right']:
            body[f'{side}_arm'] = Limb(mass=1.60, base=body['torso'], owner=owner, l_factor=0.55, wide_c_factor=1.60)

        body['right_arm'].mirror = body['left_arm']
        body['left_arm'].mirror = body['right_arm']

        body['tail'] = Tail(mass=19.0, base=body['torso'], owner=owner, l_factor=1.20, c_factor=2.2)
        body['tail'].muscle_limit_frac = (1.00, 15.00)
        body['tail'].set_point_frac = (8.00, 0.50)

    elif preset == BodyType.NAGA_FEMALE:
        body['torso'] = Torso(mass=11.0, base=None, owner=owner, l_factor=0.30,
                              chest_c_factor=1.00, waist_c_factor=0.80)
        body['torso'].muscle_limit_frac = (0.65, 4.50)
        body['torso'].fat_limit_frac = (0.20, 14.00)

        body['left_breast'] = Breast(mass=0.3, base=body['torso'], owner=owner)
        body['right_breast'] = Breast(mass=0.3, base=body['torso'], owner=owner, mirror=body['left_breast'])
        body['left_breast'].mirror = body['right_breast']

        body['neck'] = Neck(mass=0.90, base=body['torso'], owner=owner)
        body['head'] = Head(mass=3.50, base=body['neck'], owner=owner)

        for side in ['left', 'right']:
            body[f'{side}_arm'] = Limb(mass=1.30, base=body['torso'], owner=owner, l_factor=0.55, wide_c_factor=1.40)

        body['right_arm'].mirror = body['left_arm']
        body['left_arm'].mirror = body['right_arm']

        body['tail'] = Tail(mass=17.0, base=body['torso'], owner=owner, l_factor=1.20, c_factor=1.8)
        body['tail'].muscle_limit_frac = (1.00, 15.00)
        body['tail'].set_point_frac = (8.00, 0.50)

    return body


class PlayerTalentProgress:
    def __init__(self, tier: int = 0, exp: int = 0):
        self.tier = tier
        self.exp = exp


def add_fat(grower, amount: float):
    targeted_effects = grower.get_effects(effect.EffectType.BREAST_GROWTH)

    if targeted_effects:
        target_parts = [part for part in grower.body.values() if isinstance(part, Breast)]
        if target_parts:
            amount_per_part = amount / len(target_parts)
            for part in target_parts:
                part.fat_mass += amount_per_part
            return
    grower.add_fat_mass(amount)


class Player:
    def __init__(self, player_id: int, universe_instance: "universe.Universe"):
        # Basic identity and universe link
        self.id = player_id
        self._universe = universe_instance
        self.units = UnitSystem.METRIC  # Default unit system

        # Resource and state initialization
        self.troves = 0
        self.stamina = 0
        self.inventory: List[item.Item] = []
        self.effects: List[effect.Effect] = []
        self.talent_points = 0  # Points available to spend on unlocking or upgrading talents
        self.talent_refund_points = 0
        self.talents: Dict[str, PlayerTalentProgress] = {}

        self._fitness = 0.0

        self._size_reserve = 0.0

        # Set default body type
        self.body_type = BodyType.ANTHRO_MALE

        # Anatomy generation via factory
        # Pass self as owner so body parts can reference the player
        self.body = get_body_preset(self.body_type, owner=self)

        # Initialize stamina to max capacity based on the new body
        self.stamina = self.max_stamina

    @property
    def experience(self) -> int:
        return sum(progress.exp for progress in self.talents.values())

    @property
    def max_stamina(self) -> float:
        return self.get_muscle_mass() * 100000.0 * 24

    # --- FITNESS ---
    @property
    def fitness(self) -> float:
        """
        Returns the player's current fitness level in kilograms.
        Applies a dynamic temporary boost based on the RESTLESS effect's power (defaults to 15%).
        """
        base_fitness = self._fitness

        # Fetch the active RESTLESS effect instance
        restless_eff = self.get_effect(effect.EffectType.RESTLESS)

        if restless_eff:
            # Safely read the power attribute; fall back to 0.15 if it is missing or falsy
            bonus_factor = getattr(restless_eff, 'power', 0.15)
            if not bonus_factor:
                bonus_factor = 0.15

            # Apply the dynamic multiplier (e.g., 1.0 + 0.15 = 1.15x)
            base_fitness *= (1.0 + bonus_factor)

        # Ensure the boosted fitness never completely breaks the scale
        total_mass = self.get_mass()
        return max(0.1, min(base_fitness, total_mass * 0.99))

    @fitness.setter
    def fitness(self, value_kg: float):
        """Sets the raw base fitness level in kg, hard-capped below total body mass."""
        total_mass = self.get_mass()
        self._fitness = max(0.1, min(value_kg, total_mass * 0.99))

    @property
    def fitness_ratio(self) -> float:
        """
        Calculates the percentage ratio of fitness mass relative to (total mass + fitness mass).
        Using self.fitness handles both base values and temporary buff multipliers dynamically.
        This asymptotic formula strictly prevents the ratio from ever reaching or exceeding 1.0 (100%).
        """
        total_mass = self.get_mass()
        current_fitness = self.fitness  # Automatically includes RESTLESS effect power bonus

        denominator = total_mass + current_fitness
        if denominator <= 0:
            return 0.0

        return current_fitness / denominator

    # --- SIZE RESERVE ---
    @property
    def size_reserve(self) -> float:
        """Returns the player's current size reserve value."""
        return self._size_reserve

    @size_reserve.setter
    def size_reserve(self, value: float):
        """Sets the size reserve, ensuring it never drops below zero."""
        self._size_reserve = max(0.0, value)

    def modify_size_reserve(self, amount: float) -> float:
        """
        Safely increases or decreases the player's size reserve.
        Returns the actual delta applied.
        """
        old_reserve = self._size_reserve
        self.size_reserve = self._size_reserve + amount
        return self._size_reserve - old_reserve

    @property
    def energy_efficiency_multiplier(self) -> float:
        """
        Calculates the energy efficiency factor based on the fitness-to-mass ratio.
        If fitness is 50% of body mass, the multiplier becomes 2.0x.
        """
        return 1.0 / (1.0 - self.fitness_ratio)

    def train_cardio(self, intensity_fraction: float = 0.01):
        """
        Advances fitness mass (kg) by a fraction of the remaining weight gap
        between current fitness and total body mass. Default is 1% (0.01).
        """
        total_mass = self.get_mass()
        remaining_gap_kg = total_mass - self._fitness

        fitness_gain_kg = intensity_fraction * remaining_gap_kg
        self.fitness = self._fitness + fitness_gain_kg

    @property
    def stomach_content(self) -> float:
        """Sums up the current stomach content across all existing torsos."""
        # We grab the actual part object 'p' instead of its length
        torsos = [p for n, p in self.body.items() if 'torso' in n]
        return sum(part.stomach_content for part in torsos)

    @property
    def universe(self) -> "universe.Universe":
        """
        Return the player's universe, with a polite check for its existence.
        """
        if not hasattr(self, '_universe') or self._universe is None:
            # This is a dire situation indeed. We must handle the missing link.
            # Perhaps return a default universe or raise a custom error.
            raise AttributeError("Player exists in a void! The '_universe' reference is missing.")
        return self._universe

    def add_item(self, thing):
        """Adds a unique item to the inventory."""
        self.inventory.append(thing)

    def remove_item(self, thing):
        """Removes a specific item instance from inventory."""
        if thing in self.inventory:
            self.inventory.remove(thing)
        print(f"Item {thing} removed")

    def remove_item_by_index(self, index):
        self.remove_item(self.inventory[index])

    def get_inventory(self) -> list:
        return self.inventory

    def set_unit_preference(self, unit: UnitSystem):
        """Sets the player's preferred unit system."""
        self.units = unit

    def get_height(self):
        """
        Calculates total vertical height.
        Dragon logic: Height = Average Legs + Effective Neck Reach + Head contribution.
        Humanoid logic: Height = Legs + Torso + Neck + Head.
        """
        # 1. Identify legs using updated keywords to support dragon limb naming
        leg_keywords = ['leg']
        legs = [p.length for n, p in self.body.items() if any(k in n for k in leg_keywords)]
        avg_legs = sum(legs) / len(legs) if legs else 0

        # 2. Identify necks and find the longest one
        necks = [(p, p.length) for n, p in self.body.items() if 'neck' in n]

        max_neck_len = 0
        head_h = 0
        effective_neck_h = 0

        if necks:
            longest_neck_obj, max_neck_len = max(necks, key=lambda x: x[1])

            # 3. Find the head attached to this specific neck
            found_head = False
            for name, part in self.body.items():
                if 'head' in name:
                    # Check if this head is attached to the longest neck
                    if hasattr(part, 'base') and part.base == longest_neck_obj:
                        # For dragons: neck and head are rarely vertical (S-curve)
                        # Using 70% of neck and 30% of head for vertical contribution
                        head_h = part.length * 0.3
                        effective_neck_h = max_neck_len * 0.7
                        found_head = True
                        break

            # Failsafe if no head is directly linked to the longest neck
            if not found_head:
                all_heads = [p.length for n, p in self.body.items() if 'head' in n]
                if all_heads:
                    head_h = all_heads[0] * 0.3
                    effective_neck_h = max_neck_len * 0.7
        else:
            # Fallback if no neck exists
            effective_neck_h = 0

        # Logic for Dragons (ignore torso as it's horizontal)
        if "dragon" in self.body_type.value.lower():
            return avg_legs + effective_neck_h + head_h

        # Check if body type contains naga to apply correct coiled/reared height calculation
        if "naga" in self.body_type.value.lower():
            # Nagas rear up, meaning part of their tail contributes to standing height (typically estimated as
            # one-third of total length)
            total_length = self.get_full_length()
            return total_length / 3.0

        # Logic for Humanoids (torso adds vertical height)
        torsos = [p.length for n, p in self.body.items() if 'torso' in n]
        avg_torsos = sum(torsos) / len(torsos) if torsos else 0

        # For humans, neck and head are mostly vertical
        human_head_h = (head_h / 0.3) * 0.9 if head_h > 0 else 0
        human_neck_h = (effective_neck_h / 0.7) if effective_neck_h > 0 else 0

        return avg_legs + avg_torsos + human_neck_h + human_head_h

    def get_mass(self):
        return sum(part.total_mass for part in self.body.values() if isinstance(part, Body))

    def get_base_mass(self):
        return sum(part.mass for part in self.body.values() if isinstance(part, Body))

    def get_fat_mass(self):
        return sum(part.fat_mass for part in self.body.values() if isinstance(part, Body))

    def get_muscle_mass(self):
        return sum(part.muscle_mass for part in self.body.values() if isinstance(part, Body))

    @property
    def stomach_capacity(self) -> float:
        """Calculates the total stomach capacity across all torsos."""
        torsos = [part for part in self.body.values() if isinstance(part, Torso)]
        if not torsos:
            return 0.0
        return sum(t.stomach_capacity for t in torsos)

    @property
    def stomach_content_quality_avg(self) -> float:
        """Calculates the average stomach quality across all torsos."""
        torsos = [part for part in self.body.values() if isinstance(part, Torso)]
        if not torsos:
            return 0.0
        total_quality = sum(t.stomach_content_tier_avg for t in torsos)
        return total_quality / len(torsos)

    @property
    def workout_cost(self):
        """
        Calculates the energy cost of a workout, adjusted downward by the player's energy efficiency.
        """
        base_cost = 12000 * 24 * self.get_mass()
        return base_cost / self.energy_efficiency_multiplier

    def scale_all_body_parts(self, factor):
        """
        Scales all body parts by the given factor.
        """
        for part_name, part in self.body.items():
            if isinstance(part, Body):  # Ensure the part is of type Body or its subclasses
                part.scale(factor)  # Call the scale method of the body part

    def grow_all_body_parts(self, factor):
        for part_name, part in self.body.items():
            if isinstance(part, Body):  # Ensure the part is of type Body or its subclasses
                part.grow(factor)  # Call the growth method of the body part

    def apply_proportional_growth(self, total_mass_gain):
        body_parts = [part for part in self.body.values() if isinstance(part, Body)]

        # We use only structural base for distribution to keep it stable
        current_base_sum = sum(p.mass for p in body_parts)

        if current_base_sum <= 0:
            return

        for part in body_parts:
            # Relative share of the total gain for this body part
            part_share_of_total = part.mass / current_base_sum
            part_gain = part_share_of_total * total_mass_gain

            # English: Ratios relative to BASE MASS (e.g., 0.2 = 20% of base)
            r_muscle = part.set_point_frac[0]
            r_fat = part.set_point_frac[1]

            # 1: What fraction of the PART GAIN is the structural base?
            # Logic: Total = Base + (Base * r_m) + (Base * r_f) = Base * (1 + r_m + r_f)
            # So: Base_fraction = 1 / (1 + r_m + r_f)
            denominator = 1.0 + r_muscle + r_fat
            b_fraction = 1.0 / denominator

            # 3. Apply the growth
            # We slice the gain into Base, Muscle, and Fat portions
            added_base = part_gain * b_fraction

            part.mass += added_base
            part.muscle_mass += added_base * r_muscle
            part.fat_mass += added_base * r_fat

    def add_fat_mass(self, fat_gain):
        initial = self.get_fat_mass()
        target = max(0.001, initial + fat_gain)
        factor = (target / initial) ** (1 / 3)

        for part in self.body.values():
            if isinstance(part, Body):
                part.fatten(factor)

        return self.get_fat_mass() - initial

    def add_muscle_mass(self, muscle_gain):
        initial = self.get_muscle_mass()
        target = max(0.001, initial + muscle_gain)
        factor = (target / initial) ** (1 / 3)

        for part in self.body.values():
            if isinstance(part, Body):
                part.bulk_up(factor)

        return self.get_muscle_mass() - initial

    # --- SIZE RESERVE PROCESSING METHODS ---
    def execute_growth(self) -> tuple[float, float]:
        """
        Core growth processor with active boost inspection.
        """
        raw_gain = self.size_reserve
        print(f"\n[DEBUG GROWTH START] Processing reserve absorption...")
        print(f"  -> Raw Reserve to absorb: {raw_gain}")

        if raw_gain <= 0:
            print("  -> [ABORT] Reserve is empty.")
            return 0.0, 0.0

        # Inspect what effects are actually active right now
        active_boosts = self.get_effects(effect.EffectType.RESERVE_BOOST)
        boost_power = sum(e.power for e in active_boosts)
        print(f"  -> Found {len(active_boosts)} RESERVE_BOOST effects. Total combined power: {boost_power}")

        self.apply_proportional_growth(raw_gain)
        self.size_reserve = 0.0

        first_step_chance = 0.0
        if boost_power > 0:
            first_step_chance = 0.75 * (1.0 - (1.0 / (1.0 + boost_power)))

        print(f"  -> Calculated Minigame Chain Chance: {first_step_chance * 100:.2f}%")

        while self.remove_single_effect_by_type(effect.EffectType.RESERVE_BOOST):
            pass
        print("[DEBUG GROWTH END] Effects purged. Returning data to game engine.")

        return raw_gain, first_step_chance

    def apply_chain_growth_bonus(self, original_gain: float, step_count: int) -> float:
        bonus_factor = 0.02 * (step_count ** 3)
        bonus_mass = original_gain * bonus_factor
        self.apply_proportional_growth(bonus_mass)
        return bonus_mass

    @property
    def max_size_reserve(self) -> float:
        """
        Returns the total maximum size reserve.
        The base capacity is calculated as exactly 1/6th of the player's body mass.
        Then, any active percentage-based RESERVE_BOOST effects are applied.
        """
        # Calculate dynamic base capacity: 1/6 of the character's body mass
        # (Using self.body.mass as a reference to your anatomy preset)
        base_max = self.get_base_mass() / 6.0

        # Gather all active stretch/boost effects using your helper method
        active_boosts = self.get_effects(effect.EffectType.RESERVE_BOOST)

        # Sum their percentage powers (e.g., 1.20 = 120% bonus)
        total_boost_pct = sum(e.power for e in active_boosts)

        # Final capacity = base_max * (1 + total_boost_percent)
        return base_max * (1.0 + total_boost_pct)

    def execute_resistance(self) -> tuple[bool, float, float, float]:
        """
        English: Processes the attempt to resist growth with heavy debug logging.
        """
        base_max = self.get_base_mass() / 6
        current_reserve = self.size_reserve

        print(f"\n[DEBUG RESIST START] Player: {self.id}")
        print(f"  -> Current Reserve: {current_reserve} | Base Max Capacity: {base_max}")
        print(f"  -> Max Reserve (With Buffs): {self.max_size_reserve}")

        has_reserve_boost = bool(self.get_effects(effect.EffectType.RESERVE_BOOST))

        if not has_reserve_boost and current_reserve <= (base_max * 1.5):
            success_chance = 1.0
        elif current_reserve <= base_max:
            success_chance = 1.0
        else:
            total_max_with_effects = self.max_size_reserve
            upper_bound = total_max_with_effects * 2.0

            if current_reserve >= upper_bound:
                success_chance = 0.0
            else:
                success_chance = 1.0 - ((current_reserve - base_max) / (upper_bound - base_max))
                success_chance = max(0.0, min(1.0, success_chance))

        roll = random.random()
        print(f"  -> Success Chance: {success_chance * 100:.2f}% | Dice Roll: {roll * 100:.2f}%")

        if roll <= success_chance:
            current_boost = sum(e.power for e in self.get_effects(effect.EffectType.RESERVE_BOOST))
            print(f"  -> [DEBUG SUCCESS] Existing current_boost sum: {current_boost}")

            l_current = base_max * (1 + current_boost)
            print(f"  -> [DEBUG SUCCESS] l_current (base_max * (1 + current_boost)): {l_current}")

            overflow_amount = max(0.0, (current_reserve - l_current) / base_max)
            print(f"  -> [DEBUG SUCCESS] calculated overflow_amount: {overflow_amount}")

            new_boost_power = current_boost + overflow_amount * 2.0
            print(f"  -> [DEBUG SUCCESS] calculated new_boost_power: {new_boost_power}")

            print(
                f"  -> [OUTCOME: SUCCESS] Overflow: {overflow_amount:.2f} | Generated Boost Power: {new_boost_power:.4f}")

            if new_boost_power > 0.0:
                while self.remove_single_effect_by_type(effect.EffectType.RESERVE_BOOST):
                    pass
                new_boost_effect = effect.Effect(
                    effect_type=effect.EffectType.RESERVE_BOOST,
                    power=new_boost_power,
                    duration=None,
                    stackable=False,
                    creator_id=self.id
                )
                self.add_effect_instance(new_boost_effect)
                print(f"  -> [DEBUG SUCCESS] Successfully added new effect with power: {new_boost_power}")
            else:
                print(f"  -> [DEBUG WARNING] new_boost_power is <= 0.0! Effect was NOT added.")

            return True, 0.0, 0.0, new_boost_power
        else:
            active_boosts = self.get_effects(effect.EffectType.RESERVE_BOOST)
            existing_boost_power = sum(e.power for e in active_boosts)
            print(
                f"  -> [DEBUG FAILURE] active_boosts count: {len(active_boosts)} | existing_boost_power sum: {existing_boost_power}")

            original_gain, chain_chance = self.execute_growth()

            print(f"  -> [GROWTH RESULT FROM FAILURE] Gained: {original_gain} | Final Chain Chance: {chain_chance}")
            return False, original_gain, chain_chance, existing_boost_power

    def get_biological_limits(self):
        """
        Calculates the absolute minimum and maximum muscle/fat mass
        based on the current body parts and their specific limits.
        """
        limits = {
            'min_m': 0.0, 'max_m': 0.0,
            'min_f': 0.0, 'max_f': 0.0
        }

        for part in self.body.values():
            # Minimum muscle = base mass * lower limit fraction
            limits['min_m'] += part.mass * part.muscle_limit_frac[0]
            # Maximum muscle = base mass * upper limit fraction
            limits['max_m'] += part.mass * part.muscle_limit_frac[1]

            # Same logic for fat limits
            limits['min_f'] += part.mass * part.fat_limit_frac[0]
            limits['max_f'] += part.mass * part.fat_limit_frac[1]

        return limits

    def get_potential_ratios(self):
        """
        Returns the percentage (0.0 to 1.0) of used potential
        for muscle and fat relative to current biological limits.
        """
        limits = self.get_biological_limits()
        curr_m = self.get_muscle_mass()
        curr_f = self.get_fat_mass()

        # Calculate how far the player is from min (0.0) to max (1.0)
        # Muscle potential ratio
        m_range = limits['max_m'] - limits['min_m']
        m_ratio = (curr_m - limits['min_m']) / m_range if m_range > 0 else 0.0

        # Fat potential ratio
        f_range = limits['max_f'] - limits['min_f']
        f_ratio = (curr_f - limits['min_f']) / f_range if f_range > 0 else 0.0

        # Clamp values between 0.0 and 1.0 to handle edge cases
        return max(0.0, min(1.0, m_ratio)), max(0.0, min(1.0, f_ratio))

    def distribute_leftovers_to_stomach(self, proteins, carbohydrates, fats, growth_mass, tier):
        """
        Distributes remaining nutrients to all available torsos.
        Adds metabolic chyme based on the mass that was successfully converted to body growth.
        """
        torsos = [part for part in self.body.values() if isinstance(part, Torso)]
        num_torsos = len(torsos)

        if num_torsos == 0:
            return

        # Calculate shares per torso
        p_share = proteins / num_torsos
        c_share = carbohydrates / num_torsos
        f_share = fats / num_torsos

        # The growth_mass is the 'raw' mass taken from the meal to build the body.
        # In Tier 0, growth_mass equals gained body mass.
        # In higher Tiers, gained body mass is larger, but chyme is based on raw intake.
        chyme_share = growth_mass / num_torsos

        for t in torsos:
            # Update Nutrient Quality (weighted average)
            if (t.protein_content + p_share) > 0:
                t.protein_quality = (t.protein_content * t.protein_quality + p_share * tier) / (
                        t.protein_content + p_share)
            t.protein_content += p_share

            if (t.fat_content + f_share) > 0:
                t.fat_quality = (t.fat_content * t.fat_quality + f_share * tier) / (t.fat_content + f_share)
            t.fat_content += f_share

            if (t.carbohydrates_content + c_share) > 0:
                t.carbo_quality = (t.carbohydrates_content * t.carbo_quality + c_share * tier) / (
                        t.carbohydrates_content + c_share)
            t.carbohydrates_content += c_share

            # Add metabolic chyme (the 'processed' mass that now fills the stomach)
            t.metabolic_chyme += chyme_share

    def feed(self, proteins, carbohydrates, fats, chyme=0.0, tier=0):
        torsos = [part for part in self.body.values() if hasattr(part, 'protein_content')]
        if not torsos:
            print("[DEBUG feed] No valid torsos found!")
            return

        from universe import SizeReserveRule

        # Jawne chyme przekazane do funkcji (np. z mikstur) od razu trafia do żołądka
        if chyme > 0:
            num_t = len(torsos)
            for t in torsos:
                t.add_chyme(chyme / num_t)

        fg_data = self.talents.get("food_grower")
        fg_tier = getattr(fg_data, "tier", 0) if fg_data is not None else 0

        if fg_tier <= 0:
            num_t = len(torsos)
            for t in torsos:
                if proteins > 0:
                    t.add_proteins(proteins / num_t, tier)
                if carbohydrates > 0:
                    t.add_carbs(carbohydrates / num_t, tier)
                if fats > 0:
                    t.add_fats(fats / num_t, tier)
            return

        current_rule = self._universe.rules.get("size_reserve", SizeReserveRule.ENABLED)

        size_reserve_active = False
        if current_rule == SizeReserveRule.ENABLED:
            size_reserve_active = True
        elif current_rule == SizeReserveRule.TALENT_REQUIRED:
            gs_data = self.talents.get("growth_spurt")
            has_growth_spurt = gs_data is not None and getattr(gs_data, "tier", 0) > 0
            size_reserve_active = bool(has_growth_spurt)

        RATIO_P, RATIO_C, RATIO_F = 1.0, 1.1, 0.6
        chyme_mass_h = 0.0

        units_p = proteins / RATIO_P if proteins > 0 else 0
        units_c = carbohydrates / RATIO_C if carbohydrates > 0 else 0
        units_f = fats / RATIO_F if fats > 0 else 0

        growth_units = min(units_p, units_c, units_f)

        if growth_units > 0:
            used_p = growth_units * RATIO_P
            used_c = growth_units * RATIO_C
            used_f = growth_units * RATIO_F

            consumed_base_mass = used_p + used_c + used_f

            if not size_reserve_active:
                total_mass_gain = consumed_base_mass * fg_tier * (1.0 + tier)
                self.apply_proportional_growth(total_mass_gain)
            else:
                reserve_mass_gain = consumed_base_mass * fg_tier * (1.0 + tier)
                if hasattr(self, 'add_size_reserve'):
                    self.add_size_reserve(reserve_mass_gain)
                elif hasattr(self, 'size_reserve'):
                    self.size_reserve += reserve_mass_gain
                else:
                    self._size_reserve = getattr(self, '_size_reserve', 0.0) + reserve_mass_gain

            # To jest masa, która uległa spożytkowaniu na wzrost/rezerwę i zamienia się w żołądku w chyme
            chyme_mass_h = consumed_base_mass

            proteins -= used_p
            carbohydrates -= used_c
            fats -= used_f

        # Dodajemy do żołądka tylko to, co faktycznie zużyto na wzrost/rezerwę jako chyme
        if chyme_mass_h > 0:
            num_t = len(torsos)
            for t in torsos:
                t.add_chyme(chyme_mass_h / num_t)

        # Reszta niezużytych makroskładników trafia normalnie do żołądka jako budulec
        num_t = len(torsos)
        for t in torsos:
            if proteins > 0:
                t.add_proteins(proteins / num_t, tier)
            if carbohydrates > 0:
                t.add_carbs(carbohydrates / num_t, tier)
            if fats > 0:
                t.add_fats(fats / num_t, tier)

    def grow_from_troves(self, dt: float):
        hg_data = self.talents.get("hoard_grower")
        tier = getattr(hg_data, "tier", 0) if hg_data is not None else 0

        if tier <= 0:
            return

        troves_kg = getattr(self, "troves", 0.0)

        if troves_kg <= 0 or dt <= 0:
            return

        growth_rate_per_second = (10.0 / (51.0 * 86400.0))

        mass_gain = troves_kg * growth_rate_per_second * dt * tier

        if mass_gain <= 0:
            return

        # Check size reserve rule and player talent requirements
        from universe import SizeReserveRule
        current_rule = self._universe.rules.get("size_reserve", SizeReserveRule.ENABLED)

        size_reserve_active = False
        if current_rule == SizeReserveRule.ENABLED:
            size_reserve_active = True
        elif current_rule == SizeReserveRule.TALENT_REQUIRED:
            gs_data = self.talents.get("growth_spurt")
            has_growth_spurt = gs_data is not None and getattr(gs_data, "tier", 0) > 0
            size_reserve_active = bool(has_growth_spurt)

        if not size_reserve_active:
            if hasattr(self, "apply_proportional_growth"):
                self.apply_proportional_growth(mass_gain)
        else:
            if hasattr(self, 'add_size_reserve'):
                self.add_size_reserve(mass_gain)
            elif hasattr(self, 'size_reserve'):
                self.size_reserve += mass_gain
            else:
                self._size_reserve = getattr(self, '_size_reserve', 0.0) + mass_gain

    def digest(self, delta_time=1.0):
        """
        Processes nutrients across all torsos step-by-step using a limited tick power.
        Biologically Realistic Order of Operations:
        1. Stamina Regeneration (First priority: burns carbs/fats to fill the energy deficit)
        2. Remaining Unbalanced Leftovers (Final priority: converts remaining single macros to fat mass)
        """
        import effect

        torsos = [part for part in self.body.values() if isinstance(part, Torso)]
        if not torsos:
            return

        # --- 0. CHECK IF STOMACH WAS NON-EMPTY BEFORE DIGESTION ---
        was_stomach_not_empty = any(
            t.protein_content > 0 or t.carbohydrates_content > 0 or t.fat_content > 0 or t.metabolic_chyme > 0
            for t in torsos
        )

        # --- 1. CALCULATE DIGESTION POWER FOR THIS TICK ---
        total_mass_context = sum(t.fat_mass + t.mass for t in torsos)
        base_rate = (total_mass_context / 16 / 24 / 12 / 300) * delta_time

        can_stack = True
        if self._universe:
            can_stack = self._universe.rules.get("belly_rubs_stack", True)

        if can_stack:
            active_rubbing_effects = self.get_effects(effect.EffectType.BELLY_RUBBED)
            bonus_power = sum(e.power for e in active_rubbing_effects)
        else:
            strongest_effect = self.get_effect(effect.EffectType.BELLY_RUBBED)
            bonus_power = strongest_effect.power if strongest_effect else 0.0

        ravenous_effects = self.get_effects(effect.EffectType.RAVENOUS)
        ravenous_bonus = sum(e.power for e in ravenous_effects)

        digestion_factor = 1.0 + bonus_power + ravenous_bonus

        metabolic_multiplier = 1.0
        if self._universe:
            metabolic_multiplier = self._universe.rules.get("metabolic_rate", 1.0)

        # Strict physical processing limit for this tick
        total_power = base_rate * digestion_factor * metabolic_multiplier

        # Digestion efficiencies
        efficiency = {
            "chyme": 1.0,
            "protein": 0.91,
            "carbs": 1.45,
            "fat": 0.36
        }

        # --- FAT GROWTH MULTIPLIER (Effect integration) ---
        fat_growth_effects = self.get_effects(effect.EffectType.FAT_GROWTH)
        fat_growth_power_sum = sum(e.power for e in fat_growth_effects)
        fat_growth_multiplier = 1.0 + fat_growth_power_sum

        # --- 2. STEP ONE: STAMINA REGENERATION (Absolute priority for survival) ---
        stamina_deficit = self.max_stamina - self.stamina
        energetic_effects = self.get_effects(effect.EffectType.ENERGETIC)
        stamina_speed_mod = 1 + sum(e.power for e in energetic_effects)

        if stamina_deficit > 0 and total_power > 0:
            # A. Burn Carbs for Stamina first
            for t in torsos:
                if stamina_deficit <= 0 or total_power <= 0: break
                if t.carbohydrates_content > 0:
                    carbo_energy_multiplier = 1 + t.carbo_quality
                    base_carbo_energy = 17000000
                    dynamic_carbo_energy = base_carbo_energy * carbo_energy_multiplier

                    needed_kg = stamina_deficit / dynamic_carbo_energy
                    max_carbs_processing = total_power * efficiency["carbs"] * stamina_speed_mod
                    can_process = min(t.carbohydrates_content, max_carbs_processing, needed_kg)

                    t.carbohydrates_content -= can_process
                    self.stamina += can_process * dynamic_carbo_energy
                    total_power -= (can_process / (efficiency["carbs"] * stamina_speed_mod))
                    stamina_deficit = self.max_stamina - self.stamina

            # B. Burn Fats for Stamina second
            for t in torsos:
                if stamina_deficit <= 0 or total_power <= 0: break
                if t.fat_content > 0:
                    fat_energy_multiplier = 1 + t.fat_quality
                    base_fat_energy = 37000000
                    dynamic_fat_energy = base_fat_energy * fat_energy_multiplier

                    needed_kg = stamina_deficit / dynamic_fat_energy
                    max_fats_processing = total_power * efficiency["fat"] * stamina_speed_mod
                    can_process = min(t.fat_content, max_fats_processing, needed_kg)

                    t.fat_content -= can_process
                    self.stamina += can_process * dynamic_fat_energy
                    total_power -= (can_process / (efficiency["fat"] * stamina_speed_mod))
                    stamina_deficit = self.max_stamina - self.stamina

        # --- 3. STEP TWO: REMAINING UNBALANCED LEFT-OVERS ---
        if total_power > 0:
            power_per_torso = total_power / len(torsos)

            for t in torsos:
                current_power = power_per_torso

                # A. CHYME (Old processed structural matter)
                if t.metabolic_chyme > 0 and current_power > 0:
                    can_process = current_power * efficiency["chyme"]
                    removed = min(t.metabolic_chyme, can_process)
                    t.metabolic_chyme -= removed
                    current_power -= (removed / efficiency["chyme"])

                # B. REMAINING CARBOHYDRATES
                if t.carbohydrates_content > 0 and current_power > 0:
                    can_process = current_power * efficiency["carbs"]
                    removed = min(t.carbohydrates_content, can_process)
                    t.carbohydrates_content -= removed
                    fat_to_add = removed * 0.8 * (1 + t.carbo_quality) * fat_growth_multiplier
                    add_fat(self, fat_to_add)
                    current_power -= (removed / efficiency["carbs"])

                # C. REMAINING FAT
                if t.fat_content > 0 and current_power > 0:
                    can_process = current_power * efficiency["fat"]
                    removed = min(t.fat_content, can_process)
                    t.fat_content -= removed
                    fat_to_add = removed * (1 + t.fat_quality) * fat_growth_multiplier
                    add_fat(self, fat_to_add)
                    current_power -= (removed / efficiency["fat"])

                # D. PROTEIN
                if t.protein_content > 0 and current_power > 0:
                    can_process = current_power * efficiency["protein"]
                    removed = min(t.protein_content, can_process)

                    stamina_gap = self.max_stamina - self.stamina

                    if stamina_gap > 0:
                        energy_from_protein = removed * 17000000
                        if energy_from_protein <= stamina_gap:
                            self.stamina += energy_from_protein
                            leftover_for_fat = 0
                        else:
                            self.stamina = self.max_stamina
                            used_for_stamina = stamina_gap / 17000000
                            leftover_for_fat = removed - used_for_stamina
                    else:
                        leftover_for_fat = removed

                    if leftover_for_fat > 0:
                        fat_to_add = leftover_for_fat * 0.6 * (1 + t.protein_quality) * fat_growth_multiplier
                        add_fat(self, fat_to_add)

                    t.protein_content -= removed
                    current_power -= (removed / efficiency["protein"])

        # --- 5. CHECK IF STOMACH BECAME EMPTY AFTER DIGESTION ---
        is_stomach_empty_now = not any(
            t.protein_content > 0 or t.carbohydrates_content > 0 or t.fat_content > 0 or t.metabolic_chyme > 0
            for t in torsos
        )

        main_channel_id = self.universe.get_main_channel()
        if was_stomach_not_empty and is_stomach_empty_now and main_channel_id:
            self.universe.send_to_main_channel(f"<@{self.id}>, your stomach is now empty! You are hungry.")

    def can_eat(self, amount):
        torsos = [part for part in self.body.values() if isinstance(part, Torso)]
        leftover_capacity = 0
        for torso in torsos:
            leftover_capacity += torso.stomach_capacity - torso.stomach_content
        if leftover_capacity < amount:
            return False
        else:
            return True

    def tick_effects(self):
        """Safely ticks down active effects and removes expired ones, handling permanent effects."""
        # 1. Use list(self.effects) to create a shallow copy for safe mid-loop removal
        for e in list(self.effects):
            e.tick()
            rem_time = e.remaining_time()
            # 2. Check if remaining time is not None before performing the check
            # If rem_time is None, it means the effect is permanent and should never expire
            if rem_time is not None and rem_time <= 0:
                print(f"Effect expired! Remaining time: {rem_time}")
                self.remove_effect(e)

    def remove_effect(self, e):
        if e in self.effects:
            if e.effect_type.on_expire:
                try:
                    e.effect_type.on_expire(self, e)
                except Exception as err:
                    print(f"Error in on_expire for {e.effect_type.name}: {err}")
            self.effects.remove(e)

    def remove_single_effect_by_type(self, effect_type: effect.EffectType) -> bool:
        """
        Removes only the first encountered active effect of a specific EffectType.
        Returns True if an effect was found and removed, False otherwise.
        """
        for e in self.effects:
            if e.effect_type == effect_type:
                self.effects.remove(e)
                return True  # Stop immediately after removing the first match

        return False  # Return False if no matching effect was found

    def add_effect(self, effect_type, power=None, duration=None, creator_id=None):
        """
        Adds a new effect to the player or refreshes/updates an existing one.
        Ensures that power correctly falls back to the default power of the EffectType Enum.
        """
        existing_effect = next((e for e in self.effects if e.effect_type == effect_type), None)

        # Resolve target power, safely handling cases where effect_type might be an Effect instance or an EffectType
        # enum
        base_effect_type = effect_type.effect_type if hasattr(effect_type, 'effect_type') else effect_type
        default_p = getattr(base_effect_type, 'default_power', 1.0)
        target_power = power if power is not None else default_p

        if existing_effect:
            if existing_effect.power != target_power:
                if base_effect_type.on_expire:
                    base_effect_type.on_expire(self, existing_effect)

                existing_effect.power = target_power
                existing_effect.refresh(new_power=target_power, new_duration=duration)

                if base_effect_type.on_apply:
                    base_effect_type.on_apply(self, existing_effect)
            else:
                existing_effect.refresh(new_duration=duration)
        else:
            new_effect = effect.Effect(effect_type=base_effect_type, power=target_power, duration=duration,
                                       creator_id=creator_id)
            self.effects.append(new_effect)

            if base_effect_type.on_apply:
                base_effect_type.on_apply(self, new_effect)

    def add_effect_instance(self, new_effect: 'effect.Effect'):
        """Dodaje już gotowy obiekt Effect, respektując jego power/duration/stackable/creator_id."""
        existing_effect = next(
            (e for e in self.effects if e.effect_type == new_effect.effect_type), None
        )
        base_effect_type = new_effect.effect_type

        if existing_effect and not new_effect.stackable:
            if existing_effect.power != new_effect.power:
                if base_effect_type.on_expire:
                    base_effect_type.on_expire(self, existing_effect)
                existing_effect.power = new_effect.power
                existing_effect.refresh(new_power=new_effect.power, new_duration=new_effect.duration)
                if base_effect_type.on_apply:
                    base_effect_type.on_apply(self, existing_effect)
            else:
                existing_effect.refresh(new_duration=new_effect.duration)
        else:
            self.effects.append(new_effect)
            if base_effect_type.on_apply:
                base_effect_type.on_apply(self, new_effect)

    def get_effects(self, effect_type: effect.EffectType) -> list[effect.Effect]:
        """
        Returns all active effects of a specific type.
        English: Essential for calculating stacked bonuses from multiple creators.
        """
        return [e for e in self.effects if e.effect_type == effect_type]

    def get_effect(self, effect_type: effect.EffectType) -> effect.Effect:
        """
        Returns the strongest effect of a specific type.
        English: Returns the one with the highest power for single-check logic.
        """
        effects = self.get_effects(effect_type)
        if not effects:
            return None
        return max(effects, key=lambda e: e.power)

    def get_fat_ratio(self) -> float:
        """
        Calculates the global body fat ratio (0.0 to 1.0).
        English comments as requested.
        """
        total_mass = self.get_mass()
        if total_mass <= 0:
            return 0.0

        # Summing fat mass from all body parts that have it
        total_fat_mass = sum(
            part.fat_mass for part in self.body.values()
            if hasattr(part, 'fat_mass')
        )

        return total_fat_mass / total_mass

    def get_height_at_withers(self):
        """
        Calculates height at the highest point of the back/shoulders.
        """
        if "dragon" in self.body_type.value.lower():
            front_legs = [p.length for n, p in self.body.items() if 'front_leg' in n]
            avg_front_leg_h = sum(front_legs) / len(front_legs) if front_legs else 0
            return avg_front_leg_h * 1.2
        else:
            leg_keywords = ['leg', 'front', 'back']
            legs = [p.length for n, p in self.body.items() if any(k in n for k in leg_keywords)]
            avg_leg_h = sum(legs) / len(legs) if legs else 0

            torsos = [p for n, p in self.body.items() if 'torso' in n]
            total_torso_h = sum(t.length for t in torsos)
            return avg_leg_h + total_torso_h

    def get_full_length(self):
        """
        Calculates total length along the longest axial path.
        Uses 'base' reference in Head to ensure anatomical connectivity.
        """
        # 1. Sum up all torso axial segments
        axial_len = sum(part.length for part in self.body.values() if isinstance(part, Torso))

        # 2. Add neck and head length
        necks = [part for part in self.body.values() if isinstance(part, Neck)]
        if necks:
            longest_neck = max(necks, key=lambda n: n.length)
            axial_len += longest_neck.length

            # Find the head attached to this specific neck
            for part in self.body.values():
                if isinstance(part, Head) and part.base == longest_neck:
                    axial_len += part.length
                    break

        # 3. Group and sum tail segments by side or section
        tails_by_side = {}
        for key, part in self.body.items():
            if 'tail' in key:
                # Group chain segments (e.g., 'left_tail_1', 'left_tail_2' -> 'left')
                side = key.split('_')[0] if '_' in key else 'main'
                tails_by_side.setdefault(side, 0)
                tails_by_side[side] += part.length

        # Add the longest identified tail chain to the total axial length
        if tails_by_side:
            axial_len += max(tails_by_side.values())

        return axial_len

    def get_wingspan(self):
        """
        Calculates wingspan based on the largest pair of wings.
        English: Takes the maximum left wing + maximum right wing + torso width.
        """
        # Collect all wing parts
        left_wings = [part.length for key, part in self.body.items() if 'left_wing' in key]
        right_wings = [part.length for key, part in self.body.items() if 'right_wing' in key]

        if not left_wings and not right_wings:
            return 0.0

        # Use the longest single wing from each side to define the span
        max_left = max(left_wings) if left_wings else 0
        max_right = max(right_wings) if right_wings else 0

        # Calculate torso width as the 'bridge' between wings
        torso_width = 0
        torsos = [part for part in self.body.values() if isinstance(part, Torso)]
        if torsos:
            # Approximating width from the largest chest circumference
            torso_width = max(t.chest_c for t in torsos) / math.pi

        return max_left + max_right + torso_width

    def clear_all_effects(self):
        """
        Safely clears all active effects from the player, triggering expiration logic if any.
        """
        while self.effects:
            eff = self.effects[0]
            base_effect_type = eff.effect_type
            if base_effect_type and base_effect_type.on_expire:
                base_effect_type.on_expire(self, eff)
            self.effects.remove(eff)


class Body:
    # the main class for body parts. Contains generic stats that all body parts will have regardless of type.
    # Adjusted densities to account for bone porosity and internal cavities
    DENSITY_BASE = 1150.0  # Structural mass including "hollow" spaces
    DENSITY_MUSCLE = 1060.0
    DENSITY_FAT = 900.0

    def __init__(self, mass, base, owner=None, mirror=None):
        self.mass = mass  # the weight of the body part, excluding muscle and fat
        self.muscle_mass = 0.0
        self.fat_mass = 0.0
        self.base = base  # the body part that this body part attaches to
        self.owner = owner  # Reference to the Player object
        self.mirror = mirror  # the body part that is a mirror of this body part. (EX: left & right arms)

        # Limits expressed as fractions of base_mass
        self.muscle_limit_frac = (0.0, 0.0)  # (min, max)
        self.fat_limit_frac = (0.0, 0.0)  # (min, max)
        self.set_point_frac = (0.0, 0.0)  # (muscle, fat) target ratios

    @property
    def total_mass(self):
        return self.mass + self.fat_mass + self.muscle_mass

    @property
    def volume(self):
        return self.mass / self.DENSITY_BASE + self.muscle_mass / self.DENSITY_MUSCLE + self.fat_mass / self.DENSITY_FAT

    def scale(self, scale_factor):
        scale_factor = float(scale_factor)
        self.mass *= (scale_factor ** 3)
        self.muscle_mass *= (scale_factor ** 3)
        self.fat_mass *= (scale_factor ** 3)

    def grow(self, factor):
        factor = float(factor)
        self.mass *= (factor ** 3)

    def fatten(self, factor):
        factor = float(factor)
        self.fat_mass *= (factor ** 3)

    def bulk_up(self, factor):
        factor = float(factor)
        self.muscle_mass *= (factor ** 3)


class Torso(Body):
    def __init__(self, mass, base, l_factor=0.21, chest_c_factor=1.10, waist_c_factor=0.85, chest_muscle_bias=0.2,
                 chest_fat_bias=0.1, waist_muscle_bias=0.05, waist_fat_bias=0.4, owner=None, mirror=None):
        super().__init__(mass, base, owner, mirror)
        self.waist_c_factor = waist_c_factor
        self.WAIST_MUSCLE_BIAS = waist_muscle_bias
        self.WAIST_FAT_BIAS = waist_fat_bias
        self.CHEST_FAT_BIAS = chest_fat_bias
        self.CHEST_MUSCLE_BIAS = chest_muscle_bias
        self.l_factor = l_factor
        self.chest_c_factor = chest_c_factor

        # Limits expressed as fractions of base_mass
        self.muscle_limit_frac = (0.50, 4.00)  # Lowered minimum
        self.fat_limit_frac = (0.10, 15.00)
        self.set_point_frac = (0.85, 0.45)  # Muscle reduced from 1.80

        self.muscle_mass = (self.mass * self.set_point_frac[0])
        self.fat_mass = (self.mass * self.set_point_frac[1])

        self.protein_content = 0.0
        self.protein_quality = 0.0
        self.carbohydrates_content = 0.0
        self.carbo_quality = 0.0
        self.fat_content = 0.0
        self.fat_quality = 0.0
        self.metabolic_chyme = 0.0

    def add_proteins(self, amount, tier):
        """
        Adjusts protein content. Supports negative amounts for removal.
        Quality is updated only when adding new nutrients.
        """
        if amount == 0:
            return

        total_new_mass = self.protein_content + amount

        if amount > 0:
            if total_new_mass > 0:
                self.protein_quality = ((self.protein_content * self.protein_quality) + (
                        amount * tier)) / total_new_mass
            else:
                self.protein_quality = float(tier)

        if total_new_mass <= 1e-9:
            self.protein_content = 0.0
            if total_new_mass < 0.0001:
                self.protein_quality = 0.0
        else:
            self.protein_content = total_new_mass

    def add_carbs(self, amount, tier):
        """
        Adjusts carbohydrate content. Supports negative amounts for removal.
        Quality is updated only when adding new nutrients.
        """
        if amount == 0:
            return

        total_new_mass = self.carbohydrates_content + amount

        # Case 1: Adding nutrients - update weighted quality
        if amount > 0:
            if total_new_mass > 0:
                self.carbo_quality = ((self.carbohydrates_content * self.carbo_quality) + (
                        amount * tier)) / total_new_mass
            else:
                # If adding to a state that results in zero, set quality to new tier
                self.carbo_quality = float(tier)

        # Case 2: Removing nutrients or perfect depletion
        # Quality remains unchanged when removing mass from a mixture.
        if total_new_mass <= 1e-9:  # Guarding against precision errors
            self.carbohydrates_content = 0.0
            # We keep current quality or reset if completely empty
            if total_new_mass < 0:
                self.carbo_quality = 0.0
        else:
            self.carbohydrates_content = total_new_mass

    def add_fats(self, amount, tier):
        """
        Adjusts fat content. Supports negative amounts for removal.
        Quality is updated only when adding new nutrients.
        """
        if amount == 0:
            return

        total_new_mass = self.fat_content + amount

        # Case 1: Adding nutrients - update weighted quality
        if amount > 0:
            if total_new_mass > 0:
                self.fat_quality = ((self.fat_content * self.fat_quality) + (amount * tier)) / total_new_mass
            else:
                # If adding to an empty state, set quality to new tier
                self.fat_quality = float(tier)

        # Case 2: Removing nutrients or depletion
        # Quality remains unchanged when removing mass from the current mix.
        if total_new_mass <= 1e-9:  # Float precision guard
            self.fat_content = 0.0
            # Reset quality if the stomach is completely empty
            if total_new_mass < 0.0001:
                self.fat_quality = 0.0
        else:
            self.fat_content = total_new_mass

    def add_chyme(self, amount: float) -> None:
        if amount < 0:
            raise ValueError(f"add_chyme: amount must be non-negative, got {amount}")
        self.metabolic_chyme += amount

    @property
    def stomach_capacity(self):
        total_base_mass = self.owner.get_base_mass()
        total_fat_mass = self.owner.get_fat_mass()
        return (total_base_mass + total_fat_mass) / 9

    @property
    def stomach_content(self):
        return self.protein_content + self.carbohydrates_content + self.fat_content + self.metabolic_chyme

    @property
    def stomach_content_tier_avg(self) -> float:
        """Calculates the weighted average quality of the stomach contents."""
        total_content = self.fat_content + self.protein_content + self.carbohydrates_content
        if total_content <= 0:
            return 0.0
        weighted_quality_sum = (
                (self.protein_quality * self.protein_content) +
                (self.fat_quality * self.fat_content) +
                (self.carbo_quality * self.carbohydrates_content)
        )
        return weighted_quality_sum / total_content

    @property
    def torso_surface_area_avg(self):
        # Średni przekrój poprzeczny: V = A * L => A = V / L
        # To kluczowe: jeśli L (mass) stoi w miejscu, a V rośnie, A musi urosnąć drastycznie.
        return self.volume / self.length

    @property
    def chest_c(self):
        # Średni promień wynikający z powierzchni
        r_avg = math.sqrt(self.torso_surface_area_avg / math.pi)

        # Modyfikatory kształtu:
        # Mięśnie zwiększają klatkę bardziej niż talię (V-shape)
        muscle_factor = 1.0 + (self.muscle_mass / self.mass) * self.CHEST_MUSCLE_BIAS
        # Tłuszcz też zwiększa klatkę, ale mniej agresywnie niż brzuch
        fat_factor = 1.0 + (self.fat_mass / self.mass) * self.CHEST_FAT_BIAS

        return 2 * math.pi * r_avg * muscle_factor * self.chest_c_factor

    @property
    def waist_c(self):
        r_avg = math.sqrt(self.torso_surface_area_avg / math.pi)

        # Talia rośnie głównie od tłuszczu
        fat_factor = 1.0 + (self.fat_mass / self.mass) * self.WAIST_FAT_BIAS
        # Mięśnie brzucha (core) też dodają obwodu, ale mniej niż klatka
        muscle_factor = 1.0 + (self.muscle_mass / self.mass) * self.WAIST_MUSCLE_BIAS

        return 2 * math.pi * r_avg * fat_factor * self.waist_c_factor

    @property
    def length(self):
        return (self.mass ** (1 / 3)) * self.l_factor

    @property
    def chest_depth(self):
        return self.chest_c / math.pi


class Head(Body):
    def __init__(self, mass, base, l_factor=0.14, owner=None, mirror=None):
        self.l_factor = l_factor
        super().__init__(mass, base, owner, mirror)
        # Limits expressed as fractions of base_mass
        self.muscle_limit_frac = (0.05, 0.15)  # (min, max)
        self.fat_limit_frac = (0.02, 0.20)  # (min, max)
        self.set_point_frac = (0.10, 0.05)  # (muscle, fat) target ratios

        self.muscle_mass = (self.mass * self.set_point_frac[0])
        self.fat_mass = (self.mass * self.set_point_frac[1])

    @property
    def length(self):
        return self.mass ** (1 / 3) * self.l_factor


class Limb(Body):
    def __init__(self, mass, base, l_factor=0.46, wide_c_factor=1.05, owner=None, mirror=None):
        super().__init__(mass, base, owner, mirror)
        self.l_factor = l_factor
        self.wide_c_factor = wide_c_factor

        # Limits expressed as fractions of base_mass
        self.muscle_limit_frac = (0.40, 8.00)
        self.fat_limit_frac = (0.05, 10.00)
        self.set_point_frac = (1.00, 0.35)  # Muscle reduced from 2.50

        self.muscle_mass = (self.mass * self.set_point_frac[0])
        self.fat_mass = (self.mass * self.set_point_frac[1])

    @property
    def length(self):
        return self.mass ** (1 / 3) * self.l_factor

    @property
    def wide_c(self):
        """
        Calculates circumference based on cylindrical volume.
        Units: meters, cubic meters.
        """
        if self.length <= 0:
            return 0

        geom_c = math.sqrt((4 * math.pi * self.volume) / self.length)

        return geom_c * self.wide_c_factor


class Neck(Body):
    def __init__(self, mass, base, l_factor=0.25, c_factor=0.85, owner=None, mirror=None):
        self.l_factor = l_factor
        self.c_factor = c_factor
        super().__init__(mass, base, owner, mirror)

        # Limits expressed as fractions of base_mass
        self.muscle_limit_frac = (0.40, 3.00)  # (min, max)
        self.fat_limit_frac = (0.05, 2.00)  # (min, max)
        self.set_point_frac = (0.60, 0.20)  # (muscle, fat) target ratios

        self.muscle_mass = (self.mass * self.set_point_frac[0])
        self.fat_mass = (self.mass * self.set_point_frac[1])

    @property
    def length(self):
        # Długość szyi zależy od masy bazowej (szkieletu) i specyficznego l_factor
        return self.mass ** (1 / 3) * self.l_factor

    @property
    def wide_c(self):
        # C = sqrt(4 * PI * V / L) * factor
        if self.length <= 0:
            return 0

        # Obliczamy obwód z geometrii walca, co gwarantuje realizm w metrach
        geom_c = math.sqrt((4 * math.pi * self.volume) / self.length)

        # c_factor dla szyi powinien być mniejszy niż dla uda,
        # zazwyczaj w okolicach 0.7 - 0.9 (szyja jest smuklejsza niż tułów)
        return geom_c * self.c_factor


class Tail(Body):
    """
    A tail for beasts.
    Since base mass is bone, muscle mass can be significantly higher.
    """

    def __init__(self, mass, base, owner=None, l_factor=0.8, c_factor=0.6, mirror=None):
        super().__init__(mass, base, owner, mirror)
        self.l_factor = l_factor
        self.c_factor = c_factor

        # Realism check: A tail is mostly muscle and fat over a thin bone chain
        # Limits relative to base mass (the vertebrae)
        self.muscle_limit_frac = (0.50, 10.00)  # Heavy muscle potential
        self.fat_limit_frac = (0.10, 12.00)  # Reptilian fat storage
        self.set_point_frac = (2.00, 0.40)  # Muscle is 200% of bone mass by default

        # Initialize starting state
        self.muscle_mass = self.mass * self.set_point_frac[0]
        self.fat_mass = self.mass * self.set_point_frac[1]

    @property
    def length(self):
        return self.mass ** (1 / 3) * self.l_factor

    @property
    def wide_c(self):
        if self.length <= 0:
            return 0

        geom_c = math.sqrt((4 * math.pi * self.volume) / self.length)
        return geom_c * self.c_factor

    @property
    def circumference(self):
        return self.wide_c


# Average female height used for relative cup scaling
AVERAGE_FEMALE_HEIGHT = 1.62  # metres

# Cup scale — extends via K+n notation beyond index 12
CUP_SCALE = ["AAA", "AA", "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K"]

# EU standard: AA = 10cm bust-underbust difference, +2.5cm per step
CUP_DIFF_BASE_CM = 10.0  # AA starts here
CUP_DIFF_STEP_CM = 2.5


def _cup_from_diff_cm(diff_cm: float) -> str:
    """Convert a bust-underbust difference (cm) to a cup label."""
    index = int((diff_cm - CUP_DIFF_BASE_CM) / CUP_DIFF_STEP_CM) + 1  # 0 = AAA
    if index <= 0:
        return CUP_SCALE[0]
    if index >= len(CUP_SCALE):
        return f"K+{index - len(CUP_SCALE) + 1}"
    return CUP_SCALE[index]


class Breast(Body):
    """
    A single breast organ. Two instances normally exist on a body.

    Protrusion is derived from volume directly by modelling the breast as
    a hemisphere sitting flush against the chest wall:

        volume = (2/3) * π * r³   →   r = (3V / 2π)^(1/3)

    This gives a geometrically grounded protrusion (= hemisphere radius)
    without needing a tuned empirical factor.

    Circumference contribution accounts for torso curvature: the tape
    measure takes a detour over the breast, but that detour *replaces* a
    portion of the torso arc rather than simply adding to it. On a very
    wide torso the net addition shrinks; on a narrow torso it grows.
    """

    def __init__(self, mass, base, owner=None, mirror=None):
        super().__init__(mass, base, owner, mirror)

        # Physiological limits as fractions of base mass
        self.muscle_limit_frac = (0.01, 0.05)
        self.fat_limit_frac = (0.20, 25.00)
        self.set_point_frac = (0.05, 0.60)

        self.muscle_mass = self.mass * self.set_point_frac[0]
        self.fat_mass = self.mass * self.set_point_frac[1]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @property
    def _torso(self):
        """Return the torso body part, or None if unavailable."""
        if self.owner is None:
            return None
        for part in self.owner.body.values():
            if hasattr(part, 'chest_c'):
                return part
        return None

    @property
    def _underbust(self) -> Optional[float]:
        """Underbust circumference in metres, or None."""
        t = self._torso
        return t.chest_c if t is not None else None

    @property
    def _torso_radius(self) -> Optional[float]:
        """
        Approximate torso cross-section radius at chest level.
        Treats the torso as an ellipse but uses a single circumference,
        so we approximate as a circle. Good enough for arc calculations.
        """
        ub = self._underbust
        return ub / (2 * math.pi) if ub is not None else None

    # ------------------------------------------------------------------
    # Geometry
    # ------------------------------------------------------------------

    @property
    def protrusion(self) -> float:
        """
        Forward projection of the breast in metres.

        Derived from volume by modelling the breast as a hemisphere:
            V = (2/3)πr³  →  r = (3V / 2π)^(1/3)

        On extreme body shapes the hemisphere assumption stays valid because
        it's purely a volume→radius conversion — no empirical factor required.
        """
        return (3 * self.volume / (2 * math.pi)) ** (1 / 3)

    @property
    def circumference_contribution(self) -> float:
        """
        Net length added to chest circumference by this single breast (metres).

        The tape measure follows a semicircular arc of radius = protrusion
        over the breast, but that arc *replaces* a chord of the torso
        circle rather than adding on top of it.

        Three regimes:

        1. No torso data — fall back to bare semicircle arc (π * r).
           Conservative overestimate, same as a flat-wall assumption.

        2. Breast fits on torso (protrusion < torso_radius):
              half_angle        = arcsin(protrusion / torso_radius)
              torso_arc_removed = 2 * half_angle * torso_radius
              breast_arc        = π * protrusion
              net               = breast_arc - torso_arc_removed

        3. Protrusion ≥ torso_radius (very large breast or very narrow torso):
           The breast can't be modelled as a bump on a cylinder — it
           dominates the cross-section. Cap the contribution at the full
           front half of the torso circumference (π * torso_radius), which
           is the physical maximum a single breast can contribute.
        """
        p = self.protrusion
        r = self._torso_radius

        if r is None:
            # Regime 1 — no torso info
            return math.pi * p

        if p < r:
            # Regime 2 — normal: breast is a bump on a curved surface
            half_angle = math.asin(p / r)
            torso_arc_removed = 2 * half_angle * r
            breast_arc = math.pi * p
            return breast_arc - torso_arc_removed

        # Regime 3 — breast dominates: hard cap at half torso circumference
        return math.pi * r

    # ------------------------------------------------------------------
    # Cup sizing
    # ------------------------------------------------------------------

    @property
    def absolute_cup(self) -> str:
        """
        Cup size based on this character's actual proportions.

        Uses the bust-underbust difference produced by both breasts
        (2 × this breast's contribution) converted to centimetres.
        If mirror exists, uses its contribution directly instead of doubling,
        which handles asymmetric cases correctly.
        """
        if self.mirror is not None:
            total_contribution = self.circumference_contribution + self.mirror.circumference_contribution
        else:
            total_contribution = self.circumference_contribution * 2

        diff_cm = total_contribution * 100
        return _cup_from_diff_cm(diff_cm)

    @property
    def relative_cup(self) -> str:
        """
        What cup size would this breast appear to be on an average-height woman?

        Scaling rationale:
        - Volume scales as height³ when body proportions are held constant.
        - Protrusion = (3V/2π)^(1/3), so protrusion scales linearly with height.
        - Torso radius also scales linearly with height.
        - Therefore circumference_contribution (which depends on both p and r)
          scales linearly with height too.

        We scale this breast's contribution by (avg_height / owner_height),
        then apply the same cup logic.
        """
        owner_height = self.owner.get_height() if self.owner is not None else AVERAGE_FEMALE_HEIGHT
        scale = AVERAGE_FEMALE_HEIGHT / owner_height

        # Scale protrusion and torso radius together to preserve their ratio
        scaled_p = self.protrusion * scale
        scaled_r = self._torso_radius * scale if self._torso_radius is not None else None

        # Rerun circumference contribution geometry with scaled values
        if scaled_r is None:
            scaled_contribution = math.pi * scaled_p
        elif scaled_p < scaled_r:
            half_angle = math.asin(scaled_p / scaled_r)
            scaled_contribution = math.pi * scaled_p - 2 * half_angle * scaled_r
        else:
            scaled_contribution = math.pi * scaled_r

        # Mirror scales the same way
        if self.mirror is not None:
            mirror_scale = scale
            mirror_p = self.mirror.protrusion * mirror_scale
            mirror_r = scaled_r  # same torso, same scale
            if mirror_r is None:
                mirror_contribution = math.pi * mirror_p
            elif mirror_p < mirror_r:
                ha = math.asin(mirror_p / mirror_r)
                mirror_contribution = math.pi * mirror_p - 2 * ha * mirror_r
            else:
                mirror_contribution = math.pi * mirror_r
            total_scaled = scaled_contribution + mirror_contribution
        else:
            total_scaled = scaled_contribution * 2

        diff_cm = total_scaled * 100
        return _cup_from_diff_cm(diff_cm)


class Penis(Body):
    # Coefficients to determine the ratio between length and girth
    # A standard factor: length is usually 3-4 times the radius
    shape_factor = 8.0

    @property
    def length(self):
        """
        Calculates length based on volume (mass) assuming a cylindrical shape.
        Formula: Volume = pi * r^2 * h. We use shape_factor to relate r and h.
        """
        # Volume in cm3 (assuming mass is in kg, so * 1000)
        volume_cm3 = self.total_mass * 1000
        # h = (Volume * shape_factor^2 / pi)^(1/3) derived from cylindrical volume
        length_cm = (volume_cm3 * (self.shape_factor ** 2) / 3.14159) ** (1 / 3)
        return length_cm / 100  # Return in meters

    @property
    def girth(self):
        """
        Calculates circumference (girth) based on the calculated length.
        """
        if self.length <= 0: return 0
        volume_cm3 = self.total_mass * 1000
        # Radius r = sqrt(Volume / (pi * h))
        radius_cm = (volume_cm3 / (3.14159 * (self.length * 100))) ** 0.5
        return (2 * 3.14159 * radius_cm) / 100  # Return in meters


class Testes(Body):
    @property
    def diameter(self):
        if self.total_mass <= 0:
            return 0
        #  Mass for the pair -> Volume for one
        volume_single_cm3 = (self.total_mass * 1000) / 2
        # Standard sphere diameter formula
        radius_cm = ((3 * volume_single_cm3) / (4 * 3.14159)) ** (1 / 3)
        return (2 * radius_cm) / 100


class Wing(Limb):
    def __init__(self, mass, base, owner=None, mirror=None):
        super().__init__(mass, base, l_factor=1.5, wide_c_factor=3.0, owner=owner, mirror=mirror)
        self.muscle_limit_frac = (0.30, 4.00)
        self.fat_limit_frac = (0.05, 0.50)
        self.set_point_frac = (0.60, 0.05)


class Accessory(Body):
    def __init__(self, mass, base, mirror=None):
        super().__init__(mass, base, mirror)


class Hair(Accessory):
    def __init__(self, mass, base, length, mirror=None):
        self.length = length
        super().__init__(mass, base, mirror)


class Nose(Accessory):
    def __init__(self, mass, base, mirror=None):
        super().__init__(mass, base, mirror)

        # Limits expressed as fractions of base_mass
        self.muscle_limit_frac = (0.0, 0.0)  # (min, max)
        self.fat_limit_frac = (0.0, 0.0)  # (min, max)
        self.set_point_frac = (0.0, 0.0)  # (muscle, fat) target ratios

        self.muscle_mass = (self.mass * self.set_point_frac[0])
        self.fat_mass = (self.mass * self.set_point_frac[1])


class Horn(Accessory):
    def __init__(self, mass, base, mirror=None):
        super().__init__(mass, base, mirror)


class Eye(Accessory):
    def __init__(self, mass, base, mirror=None):
        super().__init__(mass, base, mirror)


class Maw(Accessory):
    def __init__(self, mass, base, mirror=None):
        super().__init__(mass, base, mirror)

        # Limits expressed as fractions of base_mass
        self.muscle_limit_frac = (0.10, 0.50)  # (min, max)
        self.fat_limit_frac = (0.0, 0.10)  # (min, max)
        self.set_point_frac = (0.20, 0.02)  # (muscle, fat) target ratios

        self.muscle_mass = (self.mass * self.set_point_frac[0])
        self.fat_mass = (self.mass * self.set_point_frac[1])


class Ear(Accessory):
    def __init__(self, mass, base, mirror=None):
        super().__init__(mass, base, mirror)

        # Limits expressed as fractions of base_mass
        self.muscle_limit_frac = (0.0, 0.0)  # (min, max)
        self.fat_limit_frac = (0.0, 0.0)  # (min, max)
        self.set_point_frac = (0.0, 0.0)  # (muscle, fat) target ratios


def is_serializable(obj):
    try:
        pickle.dumps(obj)  # Try to serialize the object
        return True
    except (pickle.PicklingError, TypeError):
        return False


def check_serializability(obj):
    if not is_serializable(obj):
        print(f"{obj.__class__.__name__} is not serializable.")
        # Check attributes for non-serializable types
        for attr in vars(obj):
            value = getattr(obj, attr)
            if not is_serializable(value):
                print(f"  - Attribute '{attr}' of type '{type(value).__name__}' is not serializable.")
