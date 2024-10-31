from units import ureg, Q_


class Player:
    def __init__(self, player_id):
        self.id = player_id
        self.troves = 0 * ureg.gram
        # Initialize body parts in a dictionary
        self.body = {'torso': Torso(
            mass=30 * ureg.kilogram,  # Average torso weight
            base=None,  # Torso is the central base part of the body
            length=0.50 * ureg.meter,  # Average torso length from waist to shoulder
            width=0.40 * ureg.meter,  # Average shoulder-to-shoulder width
            circumference=0.85 * ureg.meter,  # Average waist circumference
            shape='anthro',  # A basic body shape
        )}

        # Create the head
        self.body['head'] = Head(
            mass=5 * ureg.kilogram,  # Average head weight
            base=self.body['torso'],  # The head attaches to the torso
            length=0.20 * ureg.meter,  # Average head length from chin to top
            width=0.15 * ureg.meter,  # Average width from ear to ear
            circumference=0.58 * ureg.meter  # Average head circumference
        )

        # Create the neck
        self.body['neck'] = Neck(
            mass=1 * ureg.kilogram,  # Average neck weight
            base=self.body['torso'],  # Neck attaches to the torso
            length=0.10 * ureg.meter,  # Average neck length
            width=0.12 * ureg.meter,  # Average neck width
            circumference=0.38 * ureg.meter  # Average neck circumference
        )

        # Create arms (left and right as mirrored limbs)
        self.body['left_arm'] = Limb(
            mass=3 * ureg.kilogram,  # Average arm weight
            base=self.body['torso'],  # Arm attaches to torso at shoulder
            length=0.60 * ureg.meter,  # Average arm length from shoulder to wrist
            wide_w=0.12 * ureg.meter,  # Width at shoulder
            wide_c=0.30 * ureg.meter,  # Circumference at shoulder
            narrow_w=0.08 * ureg.meter,  # Width at wrist
            narrow_c=0.20 * ureg.meter,  # Circumference at wrist
            prehensile=1.0  # Arms are fully prehensile
        )

        self.body['right_arm'] = Limb(
            mass=3 * ureg.kilogram,
            base=self.body['torso'],
            length=0.60 * ureg.meter,
            wide_w=0.12 * ureg.meter,
            wide_c=0.30 * ureg.meter,
            narrow_w=0.08 * ureg.meter,
            narrow_c=0.20 * ureg.meter,
            prehensile=1.0,
            mirror=self.body['left_arm']  # Mirror of left_arm
        )

        self.body['left_arm'].mirror = self.body['right_arm']  # Set mirror for left_arm

        # Create legs (left and right as mirrored limbs)
        self.body['left_leg'] = Limb(
            mass=8 * ureg.kilogram,  # Average leg weight
            base=self.body['torso'],  # Leg attaches to torso at hip
            length=0.90 * ureg.meter,  # Average leg length from hip to ankle
            wide_w=0.20 * ureg.meter,  # Width at hip
            wide_c=0.50 * ureg.meter,  # Circumference at thigh
            narrow_w=0.10 * ureg.meter,  # Width at ankle
            narrow_c=0.25 * ureg.meter  # Circumference at ankle
        )

        self.body['right_leg'] = Limb(
            mass=8 * ureg.kilogram,
            base=self.body['torso'],
            length=0.90 * ureg.meter,
            wide_w=0.20 * ureg.meter,
            wide_c=0.50 * ureg.meter,
            narrow_w=0.10 * ureg.meter,
            narrow_c=0.25 * ureg.meter,
            mirror=self.body['left_leg']  # Mirror of left_leg
        )

        self.body['left_leg'].mirror = self.body['right_leg']  # Set mirror for left_leg

        # Create additional accessories: eyes, nose, ears, and mouth
        self.body['left_eye'] = Eye(mass=0.02 * ureg.kilogram, base=self.body['head'], width=0.025 * ureg.meter)
        self.body['right_eye'] = Eye(mass=0.02 * ureg.kilogram, base=self.body['head'], width=0.025 * ureg.meter,
                                     mirror=self.body['left_eye'])
        self.body['left_eye'].mirror = self.body['right_eye']  # Set mirror for left_eye

        self.body['nose'] = Nose(mass=0.05 * ureg.kilogram, base=self.body['head'])

        self.body['left_ear'] = Ear(mass=0.02 * ureg.kilogram, base=self.body['head'], length=0.06 * ureg.meter)
        self.body['right_ear'] = Ear(mass=0.02 * ureg.kilogram, base=self.body['head'], length=0.06 * ureg.meter,
                                     mirror=self.body['left_ear'])
        self.body['left_ear'].mirror = self.body['right_ear']  # Set mirror for left_ear

        self.body['maw'] = Maw(mass=0.1 * ureg.kilogram, base=self.body['head'], width=0.08 * ureg.meter,
                               depth=0.02 * ureg.meter, teeth=0.01 * ureg.meter)

    def get_height(self):
        # Define max_leg_length and height_components to store lengths in consistent units
        max_leg_length = 0 * ureg.meter  # Initialize with ureg meter
        height_components = []

        for part_name, part in self.body.items():
            if hasattr(part, 'length'):
                try:
                    # Convert all lengths to meters using the main ureg instance
                    part_length = part.length.to(ureg.meter)

                    if 'leg' in part_name:
                        max_leg_length = max(max_leg_length, part_length)
                    elif part_name in ['torso', 'neck', 'head']:
                        height_components.append(part_length)
                except Exception as e:
                    print(f"Error with {part_name} length: {e}")

        # Sum heights and add the longest leg length
        total_height = ureg.Quantity(sum(height_components), ureg.meter) + max_leg_length
        return total_height

    def get_mass(self):
        total_weight = 0 * ureg.kilogram  # Initialize total weight in kilograms
        for part_name, part in self.body.items():
            if isinstance(part, Body):  # Check if the part is an instance of Body
                try:
                    # Convert part.mass to kilograms if necessary
                    total_weight += part.mass.to(ureg.kilogram)
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

    def feed(self, amount):
        mass_before = self.get_mass()
        mass_after = mass_before + amount
        factor = (mass_after / mass_before) ** (1 / 3)
        # Filter for all torso instances in the player's body
        torsos = [part for part in self.body.values() if isinstance(part, Torso)]
        if len(torsos) > 0:
            weight_per_torso = amount / len(torsos)
        else:
            weight_per_torso = 0
        self.scale_all_body_parts(factor)
        for torso in torsos:
            torso.stomach_content += amount

    def digest(self):
        torsos = [part for part in self.body.values() if isinstance(part, Torso)]
        for torso in torsos:
            torso.stomach_content -= self.get_mass() / 51 / 12
            if torso.stomach_content < 0:
                torso.stomach_content = 0

    def can_eat(self, amount):
        torsos = [part for part in self.body.values() if isinstance(part, Torso)]
        leftover_capacity = 0 * ureg.kilogram
        for torso in torsos:
            leftover_capacity += torso.stomach_capacity.to(ureg.kilogram) - torso.stomach_content.to(ureg.kilogram)
        if leftover_capacity < amount:
            return False
        else:
            return True


class Body:
    # the main class for body parts. Contains generic stats that all body parts will have regardless of type.
    def __init__(self, mass, base, mirror=None):
        self.mass = mass  # the weight of the body part
        self.base = base  # the body part that this body part attaches to
        self.mirror = mirror  # the body part that is a mirror of this body part. (EX: left & right arms)

    def scale(self, scale_factor):
        scale_factor = float(scale_factor)

        # Iterate through other attributes of the body part
        for attr in dir(self):
            if not attr.startswith("__") and hasattr(self, attr):
                value = getattr(self, attr)
                if isinstance(value, ureg.Quantity):  # Check if it's a Pint Quantity
                    # Check the dimension of the quantity
                    if value.dimensionality == ureg.kilogram.dimensionality:  # Mass
                        new_value = value * (scale_factor ** 3)  # Cubed for mass
                    elif value.dimensionality == (ureg.meter ** 3).dimensionality:  # Volume
                        new_value = value * (scale_factor ** 3)  # Cubed for volume
                    elif value.dimensionality == (ureg.meter ** 2).dimensionality:  # Area
                        new_value = value * (scale_factor ** 2)  # Squared for area
                    elif value.dimensionality == ureg.meter.dimensionality:  # Length
                        new_value = value * scale_factor  # Direct for lengths
                    else:
                        new_value = value  # Unchanged if it's an unsupported dimension

                    setattr(self, attr, new_value)  # Set the new scaled value


class Torso(Body):
    def __init__(self, mass, base, length, width, circumference, shape, mirror=None):
        self.length = length  # length from waist to shoulder
        self.shoulder_w = width  # width from shoulder to shoulder
        self.waist_c = circumference  # circumference of the waist
        super().__init__(mass, base, mirror)
        self.base = self
        self.muscle_mass = (self.mass * 0.5) * ureg.kilogram
        self.fat_mass = (self.mass * 0.5) * ureg.kilogram
        self.stomach_capacity = 5 * ureg.kilogram
        self.stomach_content = 0 * ureg.kilogram


class Head(Body):
    def __init__(self, mass, base, length, width, circumference, mirror=None):
        self.length = length  # length of head from chin to top
        self.forehead_w = width  # width of head from ear to ear
        self.forehead_c = circumference  # circumference of head
        super().__init__(mass, base, mirror)


class Limb(Body):
    def __init__(self, mass, base, length, wide_w, wide_c, narrow_w, narrow_c, mirror=None, prehensile=0.0):
        self.prehensile = prehensile
        self.length = length
        self.wide_w = wide_w
        self.wide_c = wide_c
        self.narrow_w = narrow_w
        self.narrow_c = narrow_c
        super().__init__(mass, base, mirror)


class Prehensile(Body):
    def __init__(self, mass, base, width, length, mirror=None, prehensile=0.0):
        self.prehensile = prehensile
        self.width = width
        self.length = length
        super().__init__(mass, base, mirror)


class Neck(Body):
    def __init__(self, mass, base, length, width, circumference, mirror=None):
        self.width = width
        self.circumference = circumference
        self.length = length
        super().__init__(mass, base, mirror)


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


import pickle


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
