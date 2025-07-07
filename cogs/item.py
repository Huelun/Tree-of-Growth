import player
import util
from util import format_quantity
from units import ureg, Q_

class Item:
    def __init__(self, name: str, value: float, emoji: str = ""):
        self.name = name
        self.emoji = emoji
        self.value = value  # Ensures value is properly formatted

    @property
    def full_name(self) -> str:
        return f"{self.emoji} {self.name}"

    def get_description(self) -> str:
        return f"Item: {self.name}\nValue: {self.value:.2f} troves"


class Consumable(Item):
    """Base class for consumable items like Food and Potions."""

    def __init__(self, name: str, value: float, size: float, tier: int, emoji: str = ""):
        super().__init__(name, value, emoji)
        self.size = size  # Prevents zero-sized items
        self.tier = tier  # Ensures tier is at least 1

    def use(self, user):
        """This method should be overridden by child classes."""
        raise NotImplementedError("use() must be implemented in subclasses.")


class Food(Consumable):
    """Represents food that players can consume."""

    def __init__(self, name: str, value: float, size: float, tier: int, protein: float, fat: float, emoji: str = ""):
        super().__init__(name, value, size, tier, emoji)
        self.protein = protein
        self.fat = fat

    def get_description(self, unit_system: player.UnitSystem = player.UnitSystem.METRIC) -> str:
        return (super().get_description() +
                f"\nMeal Size: {format_quantity((self.size + self.protein + self.fat) * ureg.kg, unit_system)}" +
                f"\nTier: {self.tier}" +
                f"\nFat: {format_quantity(self.fat * ureg.kg, unit_system)}" +
                f"\nProtein: {format_quantity(self.protein * ureg.kg, unit_system)}")

    def use(self, grower: player.Player):
        """Feed the player based on size, tier, and balance."""
        if not grower.can_eat(self.size):
            return "You are too full to eat this."
        mass_before = grower.get_mass()
        height_before = grower.get_height()
        grower.feed(self.size, self.tier)
        delta_w = format_quantity((grower.get_mass() - mass_before) * ureg.kg, grower.units)
        delta_h = format_quantity((grower.get_height() - height_before) * ureg.m, grower.units)
        grower.remove_item(self)
        article_name = util.get_article(self.full_name)
        return f"You have eaten {article_name}. You have grown {delta_h} in height and became {delta_w} more massive."


class Potion(Consumable):
    """Represents magical potions with effects."""

    def __init__(self, name: str, value: float, size: float, tier: int, effects: dict):
        super().__init__(name, value, size, tier)
        self.effects = effects  # A dictionary of effect types and values

    def get_description(self) -> str:
        effect_text = ", ".join([f"{key}: {value}" for key, value in self.effects.items()])
        return (super().get_description() +
                f"\nSize: {self.size} doses" +
                f"\nTier: {self.tier}" +
                f"\nEffects: {effect_text}")

    def use(self, grower):
        """Apply potion effects to the player."""
        for effect, value in self.effects.items():
            grower.apply_effect(effect, value * self.tier)  # Scale effect with tier
        return f"{grower.name} drank {self.name} and gained effects: {self.effects}!"
