import discord
import inflect
import nltk
from nltk.tokenize import word_tokenize
from nltk import pos_tag

import player
from cogs import universe
from player import UnitSystem
import pint
import re

nltk.download('punkt_tab')
nltk.download('averaged_perceptron_tagger')
nltk.download('averaged_perceptron_tagger_eng')
p = inflect.engine()
# Initialize the unit registry
ureg = pint.UnitRegistry()
ureg.default_format = ".3g"  # Ensures three significant digits


def format_quantity(quantity, unit_system: UnitSystem = UnitSystem.METRIC):
    """
    Converts a given quantity to a human-readable string based on the unit system.

    If `unit_system` is UnitSystem.US_CUSTOMARY:
      - Uses US customary units when practical (feet, miles, pounds, ounces, etc.).
      - Falls back to metric if the value is too extreme for common US units.

    Parameters:
      quantity (pint.Quantity): A value with units (e.g., 1.5 * ureg.meter).
      unit_system (UnitSystem): Whether to use Metric or US Customary units.

    Returns:
      str: Formatted string with appropriate units.
    """

    # Ensure quantity is a pint Quantity
    if not isinstance(quantity, pint.Quantity):
        raise ValueError("Input must be a pint.Quantity with units.")

        # Handle Length
    if quantity.check("[length]"):
        if unit_system == UnitSystem.US_CUSTOMARY:
            if quantity < 1 * ureg.inch:  # Too small for US units? Use fractional inches
                inches = quantity.to(ureg.inch).magnitude
                if inches < 0.125:
                    return f"{(inches * 8):.0f}/8\""
                elif inches < 0.25:
                    return f"{(inches * 4):.0f}/4\""
                elif inches < 0.5:
                    return f"{(inches * 2):.0f}/2\""
                return f"{inches:.1f}\""
            elif quantity < 0.5 * ureg.mile:  # Convert to feet & inches
                feet = quantity.to(ureg.foot).magnitude
                inches = quantity.to(ureg.inch).magnitude % 12
                if feet >= 1:
                    return f"{int(feet)}' {inches:.1f}\""
                return f"{inches:.1f}\""
            else:
                return f"{quantity.to(ureg.mile):.3g~P}"  # Use miles
        else:
            # Metric system - Use centimeters for values between 1 cm and 3 m
            if 1 * ureg.cm <= quantity < 3 * ureg.meter:
                return f"{quantity.to(ureg.cm):.3g~P}"
            return f"{quantity.to_compact():.3g~P}"

        # Handle Mass
    elif quantity.check("[mass]"):
        if unit_system == UnitSystem.US_CUSTOMARY:
            if quantity == 1 * ureg.kilogram:  # Special case for exactly 1 kg
                return f"1 kg"
            elif quantity < 1 * ureg.ounce:  # Too small? Use metric (grams)
                return f"{quantity.to_compact():.3g~P}"
            elif quantity < 1 * ureg.pound:  # Use ounces for smaller weights
                return f"{quantity.to(ureg.ounce):.3g~P}"
            elif quantity < 100 * ureg.pound:  # Use both pounds and ounces for weights under 100 lbs
                pounds, remainder = divmod(quantity.to(ureg.ounce).magnitude, 16)  # 1 lb = 16 oz
                if pounds == 0:
                    return f"{remainder:.0f} oz"  # If it's less than 1 lb, just show ounces
                return f"{int(pounds)} lb {remainder:.0f} oz"
            elif quantity < 2000 * ureg.pound:  # Weights between 100 lb and 1 ton (2000 lb)
                return f"{quantity.to(ureg.pound):.3g~P}"  # Show in pounds
            else:
                return f"{quantity.to(ureg.ton).magnitude:.3g} ton"  # Weights greater than 1 ton (in tons)
        else:
            # Default to Metric - use kilograms/grams
            return f"{quantity.to_compact():.3g~P}"

    # Handle Volume
    elif quantity.check("[volume]"):
        if unit_system == UnitSystem.US_CUSTOMARY:
            if quantity < 1 * ureg.teaspoon:  # Too small? Use metric
                return f"{quantity.to_compact():.3g~P}"
            elif quantity < 3 * ureg.teaspoon:  # Use teaspoons
                return f"{quantity.to(ureg.teaspoon):.3g~P}"
            elif quantity < 1 * ureg.fluid_ounce:  # Use tablespoons
                return f"{quantity.to(ureg.tablespoon):.3g~P}"
            elif quantity < 1 * ureg.cup:  # Use fluid ounces
                return f"{quantity.to(ureg.fluid_ounce):.3g~P}"
            elif quantity < 1 * ureg.pint:  # Use cups
                return f"{quantity.to(ureg.cup):.3g~P}"
            elif quantity < 1 * ureg.quart:  # Use pints
                return f"{quantity.to(ureg.pint):.3g~P}"
            elif quantity < 1 * ureg.gallon:  # Use quarts
                return f"{quantity.to(ureg.quart):.3g~P}"
            else:  # Use gallons for larger amounts
                return f"{quantity.to(ureg.gallon):.3g~P}"
        else:
            # Default to Metric
            return f"{quantity.to_compact():.3g~P}"

    # Default: Compact Metric Representation
    return f"{quantity.to_compact():.3g~P}"


def get_player_from_ctx(ctx) -> player.Player:
    # Get the universe based on the channel ID
    this_universe = universe.multiverse_instance.get_universe_from_id(ctx.channel.id)
    if this_universe is None:
        return None  # Universe not found for this channel
    # Retrieve the player based on the author ID
    return this_universe.get_player_by_id(ctx.author.id)


def get_player_from_id(source, grower_id):
    """
    Retrieves a player based on their ID.

    :param source: Either `commands.Context` or `discord.Interaction`
    :param grower_id: The Discord ID of the player
    :return: The corresponding player object or None if not found
    """
    # Determine the universe based on the source type
    channel_id = getattr(source.channel, 'id', None) if hasattr(source, 'channel') else None
    if channel_id is None:
        return None  # Invalid source

    this_universe = universe.multiverse_instance.get_universe_from_id(channel_id)
    if this_universe is None:
        return None  # Universe not found for this channel

    return this_universe.get_player_by_id(grower_id)


def get_player_from_member(source, member: discord.Member) -> player.Player:
    """
    Retrieves a player based on a Discord Member object.

    :param source: Either `commands.Context` or `discord.Interaction`
    :param member: The Discord Member whose player instance to retrieve
    :return: The corresponding player object or None if not found
    """
    return get_player_from_id(source, member.id)


def get_root_word(sentence):
    # Tokenize the sentence
    tokens = word_tokenize(sentence)

    # Get POS tags for the tokens
    pos_tags = pos_tag(tokens)

    # Try to identify the root word (subject or main noun)
    root_word_index = None
    for i, (word, pos) in enumerate(pos_tags):
        # Common approach: Find the first noun or the root verb (subject, noun phrase)
        if pos.startswith('NN'):  # Noun (singular/plural)
            root_word_index = i
            break
        elif pos.startswith('VB'):  # Verb (root verb)
            root_word_index = i
            break

    if root_word_index is not None:
        return root_word_index
    else:
        return None  # Return None if no root is found


def get_article(food_name: str) -> str:
    """Returns the correct article ('a' or 'an') before the food name, preserving emojis and spaces.
       Correctly identifies the main noun of the meal (ignoring ingredients or modifiers).
    """

    # Separate leading emojis and spaces
    match = re.match(r"([\W_]+)?([\w\s-]+)", food_name)
    prefix = match.group(1) or ""  # Capture emojis and spaces
    words = match.group(2) or food_name  # Capture the rest of the phrase

    # Get the index of the root word (main noun) using get_root_word function
    root_word_index = get_root_word(words)

    # If root_word_index is valid, use it to find the noun in the sentence
    words_list = words.split()
    if 0 <= root_word_index < len(words_list):
        main_noun = words_list[root_word_index]
    else:
        main_noun = None

    # Debugging: Print detected main noun and whether it's plural
    if main_noun:
        print(f"Detected Main Word: {main_noun} (Plural: {main_noun.endswith('s')})")
    else:
        print(f"No noun found in: {food_name}")

    # If the main noun is plural, return the phrase as is (no article)
    if main_noun and main_noun.endswith('s'):  # Plural nouns
        return f"{prefix}{words}"

    # Add an article before the first word if needed
    first_word = words.split()[0]
    article_with_first_word = p.a(first_word)

    # Replace only the first word with the version that includes the article
    formatted_phrase = words.replace(first_word, article_with_first_word, 1)

    return f"{prefix}{formatted_phrase}"


def food_to_emoji(food_name: str) -> str:
    """
    Returns emojis corresponding to the provided food name.
    If multiple foods are found in the name, returns multiple emojis.
    If no match is found, returns a generic food emoji.
    """
    food_name = food_name.strip().lower()

    # Dictionary of known food categories and their emojis
    food_emojis = {
        # Fish and seafood
        "fish": "🐟",
        "herring": "🐟",
        "salmon": "🐟",
        "tuna": "🐟",
        "trout": "🐟",
        "shrimp": "🍤",
        "prawn": "🍤",
        "lobster": "🦞",
        "crab": "🦀",
        "sushi": "🍣",
        "octopus": "🐙",
        "scallop": "🦪",

        # Fast food
        "pizza": "🍕",
        "burger": "🍔",
        "hamburger": "🍔",
        "fries": "🍟",
        "chips": "🍟",
        "fast food": "🍟",
        "sandwich": "🥪",
        "hot dog": "🌭",

        # Sweet foods
        "cake": "🍰",
        "cookie": "🍪",
        "ice cream": "🍦",
        "donut": "🍩",
        "chocolate": "🍫",
        "candy": "🍬",
        "sweets": "🍬",
        "cotton candy": "🍭",

        # Fruits
        "apple": "🍎",
        "banana": "🍌",
        "grapes": "🍇",
        "orange": "🍊",
        "watermelon": "🍉",
        "lemon": "🍋",
        "citron": "🍋",
        "strawberry": "🍓",
        "pineapple": "🍍",
        "cherry": "🍒",
        "blueberry": "🫐",
        "peach": "🍑",
        "plum": "🍑",
        "pear": "🍐",

        # Vegetables
        "carrot": "🥕",
        "broccoli": "🥦",
        "tomato": "🍅",
        "potato": "🥔",
        "lettuce": "🥬",
        "onion": "🧅",
        "garlic": "🧄",
        "pepper": "🌶️",
        "corn": "🌽",
        "mushroom": "🍄",
        "eggplant": "🍆",
        "avocado": "🥑",
        "cucumber": "🥒",
        "pea": "🍃",

        # Grains and bread
        "bread": "🍞",
        "cheese": "🧀",
        "butter": "🧈",
        "pasta": "🍝",
        "noodles": "🍜",
        "rice": "🍚",
        "dumplings": "🥟",
        "ravioli": "🥟",  # Ravioli are a type of dumpling
        "pierogi": "🥟",  # Pierogi are also dumplings
        "bao": "🥟",  # Bao is a type of steamed dumpling

        # Drinks
        "milk": "🥛",
        "coffee": "☕",
        "tea": "🍵",
        "juice": "🧃",
        "beer": "🍺",
        "wine": "🍷",
        "cocktail": "🍸",
        "champagne": "🍾",
        "water": "💧",

        # Soups and salads
        "soup": "🍲",
        "salad": "🥗",

        # Other foods
        "meat": "🥩",
        "morsel": "🍖",
        "taco": "🌮",
        "burrito": "🌯",
        "wrap": "🌯",
        "steak": "🥩",
        "chicken": "🍗",
        "pork": "🍖",
        "hotdog": "🌭",
        "ramen": "🍜",
        "spaghetti": "🍝",
        "baguette": "🥖",
        "croissant": "🥐",
        "egg": "🥚",
        "bacon": "🥓",
        "oyster": "🦪",
        "squid": "🦑",
        "grape": "🍇",
        "coconut": "🥥",
        "mango": "🥭",
        "kiwi": "🥝",
        "pumpkin": "🎃",
        "peanut": "🥜",
        "honey": "🍯",
        "whiskey": "🥃",

        # Vehicles 🚗🚕🚙
        "car": "🚗",
        "taxi": "🚕",
        "bus": "🚌",
        "truck": "🚛",
        "tractor": "🚜",
        "scooter": "🛵",
        "motorcycle": "🏍️",
        "bicycle": "🚲",
        "bike": "🚲",
        "ambulance": "🚑",
        "firetruck": "🚒",
        "police car": "🚓",
        "racecar": "🏎️",
        "train": "🚆",
        "tram": "🚊",
        "streetcar": "🚊",
        "trolley": "🚊",
        "subway": "🚇",
        "monorail": "🚝",
        "light rail": "🚈",
        "boat": "⛵",
        "ship": "🚢",
        "ferry": "⛴️",
        "canoe": "🛶",
        "jet ski": "🚤",
        "plane": "✈️",
        "airplane": "🛫",
        "helicopter": "🚁",
        "rocket": "🚀",
        "spaceship": "🛸",
        "hot air balloon": "🎈",

        # Animals 🐶🐱🐭
        "dog": "🐶",
        "cat": "🐱",
        "mouse": "🐭",
        "rat": "🐀",
        "hamster": "🐹",
        "rabbit": "🐰",
        "fox": "🦊",
        "bear": "🐻",
        "panda": "🐼",
        "koala": "🐨",
        "tiger": "🐯",
        "lion": "🦁",
        "cow": "🐮",
        "pig": "🐷",
        "boar": "🐗",
        "frog": "🐸",
        "monkey": "🐵",
        "horse": "🐴",
        "unicorn": "🦄",
        "zebra": "🦓",
        "deer": "🦌",
        "elephant": "🐘",
        "rhinoceros": "🦏",
        "hippo": "🦛",
        "giraffe": "🦒",
        "camel": "🐫",
        "llama": "🦙",
        "goat": "🐐",
        "sheep": "🐑",
        "hen": "🐔",
        "rooster": "🐓",
        "duck": "🦆",
        "swan": "🦢",
        "eagle": "🦅",
        "owl": "🦉",
        "parrot": "🦜",
        "penguin": "🐧",
        "peacock": "🦚",
        "flamingo": "🦩",
        "dove": "🕊️",
        "bat": "🦇",
        "wolf": "🐺",
        "crocodile": "🐊",
        "turtle": "🐢",
        "lizard": "🦎",
        "snake": "🐍",
        "dragon": "🐉",
        "whale": "🐋",
        "dolphin": "🐬",
        "shark": "🦈",
        "snail": "🐌",
        "butterfly": "🦋",
        "ant": "🐜",
        "bee": "🐝",
        "spider": "🕷️",
        "scorpion": "🦂",
        "kangaroo": "🦘",
        "badger": "🦡",
    }

    # List to store matching emojis
    matching_emojis = []

    # Search for all matching food items in the food_name string
    for food, emoji in food_emojis.items():
        if re.search(r'\b' + re.escape(food) + r'\b', food_name):
            matching_emojis.append(emoji)

    # If we found any matches, return all the emojis found
    if matching_emojis:
        return ' '.join(matching_emojis)

    # If no match found, return generic food emoji
    return "🍽️"
