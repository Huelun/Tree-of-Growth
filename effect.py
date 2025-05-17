from enum import Enum


class EffectType(Enum):
    """Different types of effects that can be applied to a player."""
    ENERGIZED = "Energized"
    BELLY_RUBBED = "Belly rubbed"
    HUGGED = "Hugged"


class Effect:
    """Represents an effect that can be applied to a player."""

    def __init__(self, effect_type: EffectType, power: float, duration: float = None,
                 stackable: bool = False):
        """
        :param effect_type: Type of effect
        :param power: Strength of the effect (can represent tier or intensity)
        :param duration: How long the effect lasts in seconds (None = infinite duration)
        :param stackable: If True, allows multiple instances of this effect
        """
        self.effect_type = effect_type
        self.power = power
        self.duration = duration  # None means infinite
        self.stackable = stackable  # Determines if duplicates stack

    def remaining_time(self) -> float:
        """Returns remaining time for the effect in seconds, or None if infinite."""
        if self.duration is None:
            return None
        return self.duration

    def __str__(self):
        """String representation of the effect for debugging."""
        duration_str = f"{self.remaining_time():.1f}s" if self.duration is not None else "∞"
        return f"{self.effect_type.value} | Power: {self.power} | Duration: {duration_str} | {'Stackable' if self.stackable else 'Unique'} "

    def refresh(self, new_power: float = None, new_duration: float = None):
        """
        Refreshes the effect's timer and optionally updates power.
        :param new_power: If given, updates the effect's power.
        :param new_duration: If given, resets duration to this new value.
        """
        if new_power is not None:
            self.power = new_power
        if new_duration is not None:
            self.duration = new_duration

    def tick(self):
        self.duration -= 1
