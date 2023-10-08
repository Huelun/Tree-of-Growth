class Item:
    def __init__(self, name, value):
        self.name = name
        self.value = value

    def get_description(self):
        return f"Item: {self.name}\nValue: {self.value:.2f} troves"


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


consumable_item = Consumable("Health Potion", 5.99, "Restores 50 HP")
material_item = Material("Iron Ingot", 1.99, "Metal")
wearable_item = Wearable("Leather Armor", 39.99, "Medium")
wieldable_item = Wieldable("Sword", 29.99, 20)

print(consumable_item.get_description())
print("\n")
print(material_item.get_description())
print("\n")
print(wearable_item.get_description())
print("\n")
print(wieldable_item.get_description())