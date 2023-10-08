from units import ureg, Q_


class Player:
    def __init__(self):
        self.troves = 0 * ureg.gram
        self.body = {}


class Body:
    # the main class for body parts. Contains generic stats that all body parts will have regardless of type.
    def __init__(self, mass, base, mirror=None):
        self.mass = mass  # the weight of the body part
        self.base = base  # the body part that this body part attaches to
        self.mirror = mirror  # the body part that is a mirror of this body part. (EX: left & right arms)


class Torso(Body):
    def __init__(self, mass, base, length, width, circumference, shape, mirror=None):
        self.length = length  # length from waist to shoulder
        self.shoulder_w = width  # width from shoulder to shoulder
        self.waist_c = circumference  # circumference of the waist
        super().__init__(mass, base, mirror)
        self.base = self
        self.muscle_mass = (self.mass * 0.5) * ureg.kilogram
        self.fat_mass = (self.mass * 0.5) * ureg.kilogram


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