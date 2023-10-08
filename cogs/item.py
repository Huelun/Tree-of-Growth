class Item:
    def __init__(self, name, value):
        self.name = name
        self.price = value

    def get_description(self):
        return f"Item: {self.name}\nPrice: ${self.price:.2f}"


class Consumable(Item):
    def __init__(self, name, value, usage):
        super().__init__(name, value)
        self.usage = usage

    def get_description(self):
        return super().get_description() + f"\nUsage: {self.usage}"


class Material(Item):
    def __init__(self, name, value, material_type):
        super().__init__(name, value)
        self.material_type = material_type

    def get_description(self):
        return super().get_description() + f"\nMaterial Type: {self.material_type}"


class Wearable(Item):
    def __init__(self, name, value, size):
        super().__init__(name, value)
        self.size = size

    def get_description(self):
        return super().get_description() + f"\nSize: {self.size}"


class Wieldable(Item):
    def __init__(self, name, value, damage):
        super().__init__(name, value)
        self.damage = damage

    def get_description(self):
        return super().get_description() + f"\nDamage: {self.damage} points"
