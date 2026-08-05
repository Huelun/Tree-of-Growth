from typing import TYPE_CHECKING

import player
import util
from effect import EffectType

if TYPE_CHECKING:
    import player


class Item:
    def __init__(self, name: str, value: float, emoji: str = "", nsfw: bool = False, creator_id: int | str = None):
        self.name = name
        self.emoji = emoji
        self.value = value
        self.nsfw = nsfw
        self.creator_id = creator_id

    @property
    def full_name(self) -> str:
        """Returns the basic combination of emoji and name."""
        return f"{self.emoji} {self.name}"

    @property
    def full_name_with_article(self) -> str:
        """
        Returns the complete name with the correct article placed AFTER the emoji.
        Delegates the logic to util.py.
        """
        return util.get_food_name_with_article(self.name, self.emoji)

    def get_description(self) -> str:
        description = f"**Item:** {self.name}"
        if self.nsfw:
            description += "\n[NSFW Content]"
        return description

    def get_inventory_line(self, index: int, player_units="Metric") -> str:
        safe_name = self.name if len(self.name) <= 24 else self.name[:21] + "..."
        return safe_name.ljust(24)

    def get_market_line(self, price: float, player_units="Metric") -> str:
        safe_name = self.name if len(self.name) <= 24 else self.name[:21] + "..."
        name_col = safe_name.ljust(24)

        formatted_price = util.format_quantity(
            price * util.ureg.kg,
            player_units,
            show_alternative=False
        )

        line2 = f"Price: {formatted_price}"

        return f"{name_col}\n{line2}"


class Consumable(Item):
    """Base class for consumable items like Food and Potions."""

    def __init__(self, name: str, value: float, size: float, tier: int, emoji: str = "", nsfw: bool = False, creator_id: int | str = None):
        super().__init__(name, value, emoji, nsfw=nsfw, creator_id=creator_id)
        self.size = size  # Prevents zero-sized items
        self.tier = tier  # Ensures tier is at least 1

    def use(self, user):
        """This method should be overridden by child classes."""
        raise NotImplementedError("use() must be implemented in subclasses.")


class Food(Consumable):
    """Represents food that players can consume."""

    def __init__(self, name: str, value: float, size: float, tier: int, protein: float, fat: float, emoji: str = "", nsfw: bool = False, creator_id: int | str = None):
        super().__init__(name, value, size, tier, emoji, nsfw=nsfw, creator_id=creator_id)
        self.protein = protein
        self.fat = fat

    @property
    def mass(self):
        return self.size + self.protein + self.fat

    @property
    def energy_value(self):
        """
        Calculates the total energy content in Joules (J).
        Size is treated as carbohydrates.
        Values: 17 MJ/kg for proteins/carbs, 37 MJ/kg for fats.
        """
        # Energy in Megajoules first, then converted to Joules
        # 17 MJ = 17,000,000 J
        p_energy = self.protein * 17_000_000
        c_energy = self.size * 17_000_000
        f_energy = self.fat * 37_000_000

        return p_energy + c_energy + f_energy

    def get_description(self, unit_system: 'player.UnitSystem' = None) -> str:
        import player
        ureg = util.ureg

        if unit_system is None:
            unit_system = player.UnitSystem.METRIC

        total_mass = (self.size + self.protein + self.fat) * ureg.kg
        energy_qty = self.energy_value * ureg.joule

        p_str = util.format_quantity(self.protein * ureg.kg, unit_system)
        c_str = util.format_quantity(self.size * ureg.kg, unit_system)
        f_str = util.format_quantity(self.fat * ureg.kg, unit_system)
        e_str = util.format_quantity(energy_qty, unit_system)

        description = super().get_description()
        description += f"\n**Total Mass:** {util.format_quantity(total_mass, unit_system)}"
        description += f"\n**Tier:** {self.tier}"
        description += f"\n**Nutrients:** 🥩 {p_str} | 🍞 {c_str} | 🧈 {f_str} | ⚡ {e_str}"

        return description

    def get_inventory_line(self, index: int, player_units="Metric") -> str:
        safe_name = self.name if len(self.name) <= 16 else self.name[:13] + "..."
        name_col = safe_name.ljust(16)
        tier_col = f"T{self.tier}".ljust(3)

        formatted_mass = util.format_quantity(
            self.mass * util.ureg.kg,
            player_units,
            show_alternative=False
        )

        return f"{name_col} | {tier_col} | Wg: {formatted_mass}"

    def get_market_line(self, price: float, player_units="Metric") -> str:
        safe_name = self.name if len(self.name) <= 24 else self.name[:21] + "..."
        name_col = safe_name.ljust(24)

        tier_col = f"T{self.tier}"

        formatted_mass = util.format_quantity(
            self.mass * util.ureg.kg,
            player_units,
            show_alternative=False
        )
        formatted_price = util.format_quantity(
            price * util.ureg.kg,
            player_units,
            show_alternative=False
        )

        line2 = f"{tier_col} | Wg: {formatted_mass} | Price: {formatted_price}"

        return f"{name_col}\n{line2}"

    def use(self, grower: 'player.Player'):
        """
        Handles consuming food items.
        Reports physical changes only if the player has an active GROWTH effect.
        """
        ureg = util.ureg

        # 1. Capacity check
        if not grower.can_eat(self.size + self.protein + self.fat):
            return "You are too full to eat this."

        # 2. Record state before feeding for delta calculations
        mass_before = grower.get_mass()
        height_before = grower.get_height()

        # Body fat ratio calculation before feeding
        total_fat_before = sum(p.fat_mass for p in grower.body.values() if hasattr(p, 'fat_mass'))
        fat_ratio_before = total_fat_before / mass_before if mass_before > 0 else 0

        # 3. Handle Food of the Day mechanics
        valid_food_emojis = [e for e in self.emoji if e in util.food_of_the_day._food_emojis_dict.keys()]
        primary_food_emoji = valid_food_emojis[0] if valid_food_emojis else None
        daily_food = util.food_of_the_day.choose_if_missing(grower.universe)

        food_of_the_day_discovered = False
        if primary_food_emoji == daily_food:
            self.tier += 1
            util.food_of_the_day.reroll(grower.universe)
            food_of_the_day_discovered = True

        # 4. Apply nutrients to the player
        grower.feed(self.protein, self.size, self.fat, self.tier)

        # 5. Record state after feeding
        mass_after = grower.get_mass()
        height_after = grower.get_height()

        # Body fat ratio calculation after feeding
        total_fat_after = sum(p.fat_mass for p in grower.body.values() if hasattr(p, 'fat_mass'))
        fat_ratio_after = total_fat_after / mass_after if mass_after > 0 else 0

        # 6. Cleanup and basic response preparation
        grower.remove_item(self)
        article_name = self.full_name_with_article
        response_parts = [f"You have eaten {article_name}."]

        if food_of_the_day_discovered:
            response_parts.append("✨ You discovered the Food of the Day! Its tier has increased!")

        growth_report = util.get_growth_report(
            mass_before, mass_after,
            height_before, height_after,
            fat_ratio_before, fat_ratio_after,
            grower.units
        )

        if growth_report:
            response_parts.append(growth_report)

        return "\n".join(response_parts)


class Potion(Consumable):
    """Represents magical potions that create Effect objects upon consumption."""

    def __init__(self, name: str, value: float, size: float, tier: int, effects_data: dict, emoji: str = "",
                 nsfw: bool = False, creator_id: int | str = None, min_portion_pct: float = 0.01):
        super().__init__(name, value, size, tier, emoji, nsfw=nsfw, creator_id=creator_id)
        self.mass = size
        self.protein = 0.0
        self.fat = 0.0
        # effects_data format: {EffectType.STAMINA_SURGE: duration_in_seconds}
        self.effects_data = effects_data
        self.min_portion_pct = min_portion_pct

    def use(self, grower: 'player.Player'):
        """
        Consumes the potion, applies the configured effects to the player,
        generates a growth report if applicable, removes the item from inventory,
        and returns a descriptive string result.
        """
        # 1. Capacity check
        if not grower.can_eat(self.size):
            return "You are too full to drink this."

        player_mass = grower.get_mass()
        required_size = player_mass * self.min_portion_pct
        required_size_formatted = util.format_quantity(required_size * util.ureg.liter, grower.units)

        if self.size < required_size:
            return f"This portion of {self.full_name_with_article} is too small for your massive body! You need at " \
                   f"least {required_size_formatted} of this substance for it to take effect. "

        scale_factor = self.size / required_size if required_size > 0 else 1.0

        m_before = player_mass
        h_before = grower.get_height()

        total_fat_before = sum(p.fat_mass for p in grower.body.values() if hasattr(p, 'fat_mass'))
        fat_ratio_before = total_fat_before / m_before if m_before > 0 else 0.0

        for eff_type, duration in self.effects_data.items():
            adjusted_duration = duration * scale_factor if duration is not None else None

            grower.add_effect(
                effect_type=eff_type,
                duration=adjusted_duration,
                power=float(self.tier)
            )

        torsos = [part for part in grower.body.values() if hasattr(part, 'add_chyme')]
        if torsos and self.size > 0:
            chyme_per_torso = self.size / len(torsos)
            for t in torsos:
                t.add_chyme(chyme_per_torso)

        m_after = grower.get_mass()
        h_after = grower.get_height()

        total_fat_after = sum(p.fat_mass for p in grower.body.values() if hasattr(p, 'fat_mass'))
        fat_ratio_after = total_fat_after / m_after if m_after > 0 else 0.0

        grower.remove_item(self)

        article_name = self.full_name_with_article
        msg_parts = [f"You have drunk {article_name}."]

        if scale_factor > 2.0:
            msg_parts.append(
                f"(You consumed a larger portion, extending the effect's duration by a factor of {scale_factor:.2f}.)")

        growth_report = util.get_growth_report(
            m_before, m_after,
            h_before, h_after,
            fat_ratio_before, fat_ratio_after,
            grower.units
        )

        if growth_report:
            msg_parts.append(growth_report)

        return "\n".join(msg_parts)

    def get_description(self, unit_system: 'player.UnitSystem' = None) -> str:
        import player
        ureg = util.ureg

        if unit_system is None:
            unit_system = player.UnitSystem.METRIC

        volume_qty = self.size * ureg.liter
        volume_str = util.format_quantity(volume_qty, unit_system)

        effect_text = ", ".join([
            f"{key.display_name} (Power: {self.tier}, Duration: {value}s)"
            for key, value in self.effects_data.items()
        ])

        return (super().get_description() +
                f"\n**Size:** {volume_str}" +
                f"\n**Tier:** {self.tier}" +
                f"\n**Effects:** {effect_text if effect_text else 'None'}")

    def get_inventory_line(self, index: int, player_units="Metric") -> str:
        safe_name = self.name if len(self.name) <= 16 else self.name[:13] + "..."
        name_col = safe_name.ljust(16)
        tier_col = f"T{self.tier}".ljust(3)

        formatted_volume = util.format_quantity(
            self.size * util.ureg.liter,
            player_units,
            show_alternative=False
        )

        return f"{name_col} | {tier_col} | Vol: {formatted_volume}"

    def get_market_line(self, price: float, player_units="Metric") -> str:
        safe_name = self.name if len(self.name) <= 24 else self.name[:21] + "..."
        name_col = safe_name.ljust(24)

        tier_col = f"T{self.tier}"

        formatted_volume = util.format_quantity(
            self.size * util.ureg.liter,
            player_units,
            show_alternative=False
        )
        formatted_price = util.format_quantity(
            price * util.ureg.kg,
            player_units,
            show_alternative=False
        )

        line2 = f"{tier_col} | Vol: {formatted_volume} | Price: {formatted_price}"

        return f"{name_col}\n{line2}"


# Create a potion instance that applies the stamina surge effect upon consumption.
# Parameters: name, value (in troves), size (in liters), tier, effects_data dictionary, emoji
stamina_potion = Potion(
    name="Stamina Potion",
    value=15.0,
    size=0.5,  # 0.5 liters
    tier=1,
    effects_data={
        EffectType.STAMINA_SURGE: 0.0
    },
    emoji="🧪"
)
# 1. Fat Potion - Increases fat mass or triggers fat accumulation effects
fat_potion = Potion(
    name="Fat Potion",
    value=20.0,
    size=0.5,
    tier=1,
    effects_data={
        EffectType.FAT_GROWTH: 86400.0,
    },
    emoji="🧪"
)

# 2. Muscle Potion - Boosts muscle growth and physical power
muscle_potion = Potion(
    name="Muscle Potion",
    value=25.0,
    size=0.5,
    tier=1,
    effects_data={
        EffectType.MUSCLE_GROWTH: 86400.0,
    },
    emoji="🧪"
)

# 3. Fitness Potion - Enhances overall fitness and physical efficiency
fitness_potion = Potion(
    name="Fitness Potion",
    value=30.0,
    size=0.5,
    tier=1,
    effects_data={
        EffectType.FITNESS_GROWTH: 86400.0,
    },
    emoji="🧪"
)

# 4. Specific Growth Potion - Accelerates general physical growth rate
breast_growth_potion = Potion(
    name="Breast Growth Potion",
    value=40.0,
    size=0.5,
    tier=2,
    effects_data={
        EffectType.BREAST_GROWTH: 86400.0,
    },
    emoji="🧪",
    nsfw=True
)

# 5. Inspired Cooking Potion - Temporarily boosts culinary prowess
inspired_cooking_potion = Potion(
    name="Inspired Cooking Potion",
    value=35.0,
    size=0.5,
    tier=1,
    effects_data={
        EffectType.INSPIRED_COOKING: None,
    },
    emoji="🧪"
)

# 6. Ravenous Potion - Stimulates extreme appetite and eating capacity
ravenous_potion = Potion(
    name="Ravenous Potion",
    value=25.0,
    size=0.5,
    tier=1,
    effects_data={
        EffectType.RAVENOUS: 86400.0,
    },
    emoji="🧪"
)
