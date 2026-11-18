from enum import Enum


def apply_stamina_boost(player, effect=None):
    if hasattr(player, 'max_stamina') and hasattr(player, 'stamina') and hasattr(player, 'workout_cost'):
        power = effect.power if effect else 1.0
        bonus_jules = power * player.workout_cost
        player.stamina += bonus_jules


class EffectType(Enum):
    """
    Central database of all effect types in the game.
    Tuple structure: (display_name, emoji, default_power, default_duration, description_template)
    """
    BREAST_GROWTH = (
        "Breast growth",
        "🍈🍈",
        1.0,
        86400.0,
        True,
        "Redirects all fat gain into boobs."
    )
    FITNESS_GROWTH = (
        "Fitness growth",
        "✨",
        1.0,
        86400.0,
        True,
        "Increases all fitness gains by **{power_pct}**%."
    )
    MUSCLE_GROWTH = (
        "Muscle growth",
        "💪",
        1.0,
        86400.0,
        True,
        "Increases all muscle gains by **{power_pct}**%."
    )
    FAT_GROWTH = (
        "Fat growth",
        "🛡️",
        1.0,
        86400.0,
        True,
        "Increases all fat gains by **{power_pct}**%."
    )
    BELLY_RUBBED = (
        "Belly rubbed",
        "🫳",
        0.1,
        7200.0,
        False,
        "Digestion rate increased by **{power_pct}**%."
    )
    ENERGETIC = (
        "Energetic",
        "⚡",
        1.0,
        86400.0,
        False,
        "Stamina regenerates **{power_pct}**% faster."
    )
    HUGGED = (
        "Hugged",
        "🤗",
        2.0,
        3600.0,
        False,
        "You received some affection."
    )
    RAVENOUS = (
        "Ravenous",
        "🍽",
        1.0,
        86400.0,
        False,
        "Digestion rate increased by **{power_pct}%**."
    )
    INSPIRED_COOKING = (
        "Inspired cooking",
        "🥘",
        1.0,
        None,
        True,
        "Next meal you cook will be **{power}** tier higher than normal."
    )
    GOOD_FORTUNE = (
        "Good fortune",
        "🥠",
        2.0,
        259200.0,
        False,
        "Whenever you find troves you find **{power}** times as much."
    )
    RESTLESS = (
        "Restless",
        "🔋",
        0.15,
        259200.0,
        False,
        "**+{power_pct}%** to fitness.",
        None,  # on_apply
        None  # on_expire
    )
    RESERVE_BOOST = (
        "Reserve boost",
        "⧇",
        0.0,
        None,  # Permanent until expansion or failure
        False,  # Do not stack
        "**+{power_pct}%** to max size reserve.",  # Format matching RESTLESS logic
        None,
        None
    )
    STAMINA_SURGE = (
        "Stamina Surge",
        "⚡",
        2.0,
        86400.0,
        False,
        "Increases stamina by **{power}** bars.",
        apply_stamina_boost,
        None
    )

    def __init__(self, display_name: str, emoji: str, default_power: float,
                 default_duration: float, stackable: bool, desc_template: str,
                 on_apply=None, on_expire=None):
        self.display_name = display_name
        self.emoji = emoji
        self.default_power = default_power
        self.default_duration = default_duration
        self.stackable = stackable
        self.desc_template = desc_template
        self.on_apply = on_apply
        self.on_expire = on_expire

    @classmethod
    def _missing_(cls, value):
        """
        Interceptors invalid values passed during pickle/unpickle operations.
        Maps old/corrupted structures back to the correct Enum members by name.
        """
        # If the value is a string (old format, e.g., "Energetic")
        if isinstance(value, str):
            for member in cls:
                if member.name.upper() == value.upper():
                    return member

        # If the value is a tuple (the exact issue from the log)
        # We look at the first element, which is the display name (e.g., "Energetic")
        if isinstance(value, tuple) and len(value) > 0:
            name_to_check = str(value[0]).upper()
            for member in cls:
                if member.name.upper() == name_to_check:
                    return member

        # If everything fails, default to a safe member to prevent the bot from crashing
        return cls.HUGGED


class Effect:
    """Represents an effect that can be applied to a player."""

    def __init__(self, effect_type: EffectType, power: float = None, duration: float = None,
                 stackable: bool = None, creator_id: int = None, target=None):
        """
        :param effect_type: Type of effect
        :param power: Strength of the effect
        :param duration: How long the effect lasts in seconds (None = infinite)
        :param stackable: If True, allows multiple instances of this effect
        :param creator_id: The ID of the player who applied this effect
        :param target: The player object to apply callbacks on
        """
        self.effect_type = effect_type
        # If custom power/duration is not provided, fallback to the Enum's defaults
        self.power = power if power is not None else effect_type.default_power
        self.duration = duration if duration is not None else effect_type.default_duration
        self.stackable = stackable if stackable is not None else effect_type.stackable
        self.creator_id = creator_id
        self.target = target

        if self.effect_type.on_apply is not None:
            try:
                self.effect_type.on_apply(self)
            except Exception as e:
                print(f"Error in on_apply for {self.effect_type.name}: {e}")

        # --- PICKLE MIGRATION SAFETY NET ---

    def __setstate__(self, state):
        saved_type = state.get('effect_type')
        if saved_type and not isinstance(saved_type, EffectType):
            type_name = getattr(saved_type, 'name', None) or str(saved_type)
            if "." in type_name:
                type_name = type_name.split(".")[-1]
            try:
                state['effect_type'] = EffectType[type_name.upper()]
            except KeyError:
                state['effect_type'] = EffectType.HUGGED

        if 'target' not in state:
            state['target'] = None

        resolved_type = state.get('effect_type')
        if 'power' not in state or state.get('power') is None:
            state['power'] = resolved_type.default_power if resolved_type else 0.0
        elif state.get('power', 0) <= 0 < resolved_type.default_power and resolved_type:
            print(f"[MIGRATION WARNING] {resolved_type.name} miał power=0 w starym zapisie, "
                  f"przywracam default_power={resolved_type.default_power}")
            state['power'] = resolved_type.default_power

        self.__dict__.update(state)

    @property
    def emoji(self) -> str:
        return self.effect_type.emoji

    @property
    def description(self) -> str:
        """Dynamically formats the description template based on the power representation."""
        # Check if power is a float and represents a whole number, or if it's already an int
        if isinstance(self.power, float) and self.power.is_integer():
            power_display = int(self.power)
        elif isinstance(self.power, float):
            power_display = self.power  # Keep original float representation if it has decimals (e.g., 1.5)
        else:
            power_display = self.power  # It's already an int, safely keep it as is

        # Calculate percentage display cleanly based on the numeric value
        power_pct_display = round(power_display * 100)

        return self.effect_type.desc_template.format(
            power=power_display,
            power_pct=power_pct_display
        )

    def remaining_time(self) -> float:
        """Returns remaining time for the effect in seconds, or None if infinite."""
        if self.duration is None:
            return None
        return self.duration

    def __str__(self):
        """String representation of the effect for debugging."""
        duration_str = f"{self.remaining_time():.1f}s" if self.duration is not None else "∞"
        creator_str = f" | Creator: {self.creator_id}" if self.creator_id else ""
        return f"{self.effect_type.value} | Power: {self.power} | Duration: {duration_str} | " \
               f"{'Stackable' if self.stackable else 'Unique'}{creator_str}"

    def refresh(self, new_power: float = None, new_duration: float = None):
        """
        Refreshes the effect's timer and optionally updates power.
        Only updates duration if the new duration is longer than the current one.
        """
        if new_power is not None:
            self.power = new_power

        if new_duration is not None:
            # Update duration only if the new one is greater
            if self.duration is None or new_duration > self.duration:
                self.duration = new_duration

    def tick(self):
        """Decrease duration by 1 second if not infinite."""
        if self.duration is not None:
            self.duration -= 1

            if self.duration <= 0 and self.effect_type.on_expire is not None:
                try:
                    self.effect_type.on_expire(self)
                except Exception as e:
                    print(f"Error in on_expire for {self.effect_type.name}: {e}")
