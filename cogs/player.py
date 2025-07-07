from enum import Enum
import pickle
from typing import List

from cogs import item, effect


class UnitSystem(Enum):
    METRIC = "Metric"
    US_CUSTOMARY = "US Customary"


class Player:
    def __init__(self, player_id):
        self.id = player_id
        self.troves = 0
        self.inventory: List[item.Item] = []  # Every item is stored individually
        self.effects: List[effect.Effect] = []
        self.units = UnitSystem.METRIC  # Default to Metric
        # Initialize body parts in a dictionary
        self.body = {'torso': Torso(
            mass=30,  # Average torso weight
            base=None,  # Torso is the central base part of the body
            length=0.50,  # Average torso length from waist to shoulder
            width=0.40,  # Average shoulder-to-shoulder width
            circumference=0.85,  # Average waist circumference
            shape='anthro',  # A basic body shape
        )}

        # Create the head
        self.body['head'] = Head(
            mass=5,  # Average head weight
            base=self.body['neck'],  # The head attaches to the neck
            length=0.20,  # Average head length from chin to top
            width=0.15,  # Average width from ear to ear
            circumference=0.58  # Average head circumference
        )

        # Create the neck
        self.body['neck'] = Neck(
            mass=1,  # Average neck weight
            base=self.body['torso'],  # Neck attaches to the torso
            length=0.10,  # Average neck length
            width=0.12,  # Average neck width
            circumference=0.38  # Average neck circumference
        )

        # Create arms (left and right as mirrored limbs)
        self.body['left_arm'] = Limb(
            mass=3,  # Average arm weight
            base=self.body['torso'],  # Arm attaches to torso at shoulder
            length=0.60,  # Average arm length from shoulder to wrist
            wide_w=0.12,  # Width at shoulder
            wide_c=0.30,  # Circumference at shoulder
            narrow_w=0.08,  # Width at wrist
            narrow_c=0.20,  # Circumference at wrist
            prehensile=1.0  # Arms are fully prehensile
        )

        self.body['right_arm'] = Limb(
            mass=3,
            base=self.body['torso'],
            length=0.60,
            wide_w=0.12,
            wide_c=0.30,
            narrow_w=0.08,
            narrow_c=0.20,
            prehensile=1.0,
            mirror=self.body['left_arm']  # Mirror of left_arm
        )

        self.body['left_arm'].mirror = self.body['right_arm']  # Set mirror for left_arm

        # Create legs (left and right as mirrored limbs)
        self.body['left_leg'] = Limb(
            mass=8,  # Average leg weight
            base=self.body['torso'],  # Leg attaches to torso at hip
            length=0.90,  # Average leg length from hip to ankle
            wide_w=0.20,  # Width at hip
            wide_c=0.50,  # Circumference at thigh
            narrow_w=0.10,  # Width at ankle
            narrow_c=0.25  # Circumference at ankle
        )

        self.body['right_leg'] = Limb(
            mass=8,
            base=self.body['torso'],
            length=0.90,
            wide_w=0.20,
            wide_c=0.50,
            narrow_w=0.10,
            narrow_c=0.25,
            mirror=self.body['left_leg']  # Mirror of left_leg
        )

        self.body['left_leg'].mirror = self.body['right_leg']  # Set mirror for left_leg

        # Create additional accessories: eyes, nose, ears, and mouth
        self.body['left_eye'] = Eye(mass=0.02, base=self.body['head'], width=0.025)
        self.body['right_eye'] = Eye(mass=0.02, base=self.body['head'], width=0.025, mirror=self.body['left_eye'])
        self.body['left_eye'].mirror = self.body['right_eye']  # Set mirror for left_eye

        self.body['nose'] = Nose(mass=0.05, base=self.body['head'])

        self.body['left_ear'] = Ear(mass=0.02, base=self.body['head'], length=0.06)
        self.body['right_ear'] = Ear(mass=0.02, base=self.body['head'], length=0.06,
                                     mirror=self.body['left_ear'])
        self.body['left_ear'].mirror = self.body['right_ear']  # Set mirror for left_ear

        self.body['maw'] = Maw(mass=0.1, base=self.body['head'], width=0.08, depth=0.02, teeth=0.01)

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
        # Define max_leg_length and height_components to store lengths in consistent units
        max_leg_length = 0  # Initialize with ureg meter
        height_components = []

        for part_name, part in self.body.items():
            if hasattr(part, 'length'):
                try:
                    # Convert all lengths to meters using the main ureg instance
                    part_length = part.length

                    if 'leg' in part_name:
                        max_leg_length = max(max_leg_length, part_length)
                    elif part_name in ['torso', 'neck', 'head']:
                        height_components.append(part_length)
                except Exception as e:
                    print(f"Error with {part_name} length: {e}")

        # Sum heights and add the longest leg length
        total_height = sum(height_components) + max_leg_length
        return total_height

    def get_mass(self):
        total_weight = 0  # Initialize total weight in kilograms
        for part_name, part in self.body.items():
            if isinstance(part, Body):  # Check if the part is an instance of Body
                try:
                    # Convert part.mass to kilograms if necessary
                    total_weight += part.mass
                except ValueError as e:
                    print(f"Error with part {part_name}: {e}")  # Print an error if conversion fails
                    continue  # Skip this part if conversion fails
        return total_weight

    def scale_all_body_parts(self, factor):
        """
        Scales all body parts by the given factor.
        """
        for part_name, part in self.body.items():
            if isinstance(part, Body):  # Ensure the part is of type Body or its subclasses
                part.scale(factor)  # Call the scale method of the body part

    def feed(self, amount, tier=0):
        mass_before = self.get_mass()
        # mass_after = mass_before + amount * 0.1 * 10 ** tier #TODO: make it use tier once professions are added
        mass_after = mass_before + amount
        factor = (mass_after / mass_before) ** (1 / 3)
        # Filter for all torso instances in the player's body
        torsos = [part for part in self.body.values() if isinstance(part, Torso)]
        if len(torsos) > 0:
            weight_per_torso = amount / len(torsos)
        else:
            weight_per_torso = amount
        self.scale_all_body_parts(factor)
        for torso in torsos:
            torso.stomach_content += weight_per_torso

    def digest(self):
        torsos = [part for part in self.body.values() if isinstance(part, Torso)]
        for torso in torsos:
            if self.has_effect(effect.EffectType.BELLY_RUBBED):
                digestion_factor = 1.1
            else:
                digestion_factor = 1.0
            torso.stomach_content -= self.get_mass() / 51 / 12 * digestion_factor
            if torso.stomach_content < 0:
                torso.stomach_content = 0

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
        for e in self.effects:
            e.tick()
            if e.remaining_time() <= 0:
                print(f"Remaining time: {e.remaining_time()}")
                self.remove_effect(e)

    def remove_effect(self, e: effect.Effect):
        self.effects.remove(e)

    def add_effect(self, new_effect: effect.Effect):
        """Adds an effect with proper stacking behavior."""
        if new_effect.stackable:
            # If the effect is stackable, always keep both
            self.effects.append(new_effect)
            return

        for e in self.effects:
            if e.effect_type == new_effect.effect_type:
                # Rule 1: If same type & power, keep the one with the longest duration
                if e.power == new_effect.power:
                    if new_effect.remaining_time() > e.remaining_time():
                        e.refresh(new_duration=new_effect.duration)
                    return

                # Rule 2: If different power but same remaining time, use the stronger power
                if e.remaining_time() == new_effect.remaining_time():
                    e.refresh(new_power=max(e.power, new_effect.power))
                    return

                # Rule 3: If different power and different remaining time, keep both
                break

        # If no merging happened, add the new effect
        self.effects.append(new_effect)

    def has_effect(self, effect_type: effect.EffectType):
        for e in self.effects:
            if e.effect_type == effect_type:
                return True
        return False


class Body:
    # the main class for body parts. Contains generic stats that all body parts will have regardless of type.
    def __init__(self, mass, base, mirror=None):
        self.mass = mass  # the weight of the body part
        self.base = base  # the body part that this body part attaches to
        self.mirror = mirror  # the body part that is a mirror of this body part. (EX: left & right arms)

    def scale(self, scale_factor, _scaling_in_progress=None):
        # If this is the first time calling scale, initialize the flag
        if _scaling_in_progress is None:
            _scaling_in_progress = set()

        # Avoid recursion: Check if the object is already being scaled
        if self in _scaling_in_progress:
            return  # Avoid recursion

        # Mark the object as being scaled
        _scaling_in_progress.add(self)

        scale_factor = float(scale_factor)

        # Iterate through other attributes of the body part
        for attr in dir(self):
            if not attr.startswith("__") and hasattr(self, attr):
                value = getattr(self, attr)  # Get current value before modifying

                # If value is a number, scale it
                if isinstance(value, (int, float)):
                    if attr.endswith(("mass", "capacity", "content")):
                        new_value = value * (scale_factor ** 3)  # Volume scaling
                    else:
                        new_value = value * scale_factor  # Length scaling
                    setattr(self, attr, new_value)  # Set the new scaled value


class Torso(Body):
    def __init__(self, mass, base, length, width, circumference, shape=0.8, mirror=None):
        self.length = length  # length from waist to shoulder
        self.shoulder_w = width  # width from shoulder to shoulder
        self.waist_c = circumference  # circumference of the waist
        super().__init__(mass, base, mirror)
        self.base = self
        self.muscle_mass = (self.mass * 0.5)
        self.fat_mass = (self.mass * 0.5)
        self.stomach_capacity = 5
        self.stomach_content = 0


class Head(Body):
    def __init__(self, mass, base, length, width, circumference, mirror=None):
        self.length = length  # length of head from chin to top
        self.forehead_w = width  # width of head from ear to ear
        self.forehead_c = circumference  # circumference of head
        super().__init__(mass, base, mirror)


class Limb(Body):
    def __init__(self, mass, base, length, wide_w, wide_c, narrow_w, narrow_c, mirror=None, shape=0.8, prehensile=0.0):
        self.prehensile = prehensile
        self.length = length
        self.wide_w = wide_w
        self.wide_c = wide_c
        self.narrow_w = narrow_w
        self.narrow_c = narrow_c
        super().__init__(mass, base, mirror)
        self.muscle_mass = (self.mass * (shape - 0.05)) * ureg.kilogram
        self.fat_mass = (self.mass * (1.0 - shape)) * ureg.kilogram


class Prehensile(Body):
    def __init__(self, mass, base, width, length, mirror=None, shape=0.8, prehensile=0.0):
        self.prehensile = prehensile
        self.width = width
        self.length = length
        super().__init__(mass, base, mirror)
        self.muscle_mass = (self.mass * (shape - 0.05)) * ureg.kilogram
        self.fat_mass = (self.mass * (1.0 - shape)) * ureg.kilogram


class Neck(Body):
    def __init__(self, mass, base, length, width, circumference, shape=0.8, mirror=None):
        self.width = width
        self.circumference = circumference
        self.length = length
        super().__init__(mass, base, mirror)
        self.muscle_mass = (self.mass * (shape - 0.05)) * ureg.kilogram
        self.fat_mass = (self.mass * (1.0 - shape)) * ureg.kilogram


class Genital(Body):
    def __init__(self, mass, base, length, width, circumference, mirror=None):
        self.length = length
        self.width = width
        self.circumference = circumference
        super().__init__(mass, base, mirror)


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


class Horn(Accessory):
    def __init__(self, mass, base, length, width, mirror=None):
        self.length = length
        self.width = width
        super().__init__(mass, base, mirror)


class Eye(Accessory):
    def __init__(self, mass, base, width, mirror=None):
        self.width = width
        super().__init__(mass, base, mirror)


class Maw(Accessory):
    def __init__(self, mass, base, width, depth, teeth, mirror=None):
        self.width = width  # width from corner to corner of mouth
        self.depth = depth  # length of base to tip
        self.teeth = teeth  # length of teeth
        super().__init__(mass, base, mirror)


class Ear(Accessory):
    def __init__(self, mass, base, length, mirror=None):
        self.length = length  # length from lobe to tip or whatever is equivalent
        super().__init__(mass, base, mirror)


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


# Create player instance
player_instance = Player(1)
check_serializability(player_instance)
