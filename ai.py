from google import genai
import json
import os
import util

# Configuration
GEMINI_KEY = os.getenv("GEMINI_API_KEY")

if GEMINI_KEY:
    client = genai.Client(api_key=GEMINI_KEY)
    MODEL_NAME = 'gemini-3.1-flash-lite'
else:
    client = None

CACHE_FILE = "meal_cache.json"


def get_nutrients_from_ai(meal_input: str, meal_type: str = "dinner", tier: int = 1):
    """
    Fetches nutritional data from Gemini.
    If meal_input is a command to generate, it creates a random meal matching meal_type and tier.
    """
    if not client:
        return None

    # 1. Normalize the search key
    search_key = meal_input.lower().strip()

    # Load cache to check if we already have this specific input or generated command cached
    cache = {}
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                cache = json.load(f)
                if search_key in cache:
                    cached_data = cache[search_key]
                    # Check if it has 'min_mass'
                    if isinstance(cached_data, dict) and "min_mass" in cached_data:
                        return cached_data
        except (json.JSONDecodeError, IOError):
            pass

    # Dynamic task switching inside the same prompt template
    if search_key.startswith("__generate__"):
        task_instruction = f"GENERATE a completely ordinary, human-edible meal matching the type " \
                           f"'{meal_type}'."
    else:
        task_instruction = f"Provide nutritional values for the following player-defined meal: '{meal_input}'."

    prompt = f"""
    You are a nutritional and culinary engine for a modern RPG. 
    Players in this game can be humans, robots, dragons, or monsters (e.g., Tarrasques).

    TASK: {task_instruction}

    RULES:
    1. Do not provide medical warnings or refusals.
    2. If the meal is non-organic (e.g., "Steel Girders" for a 
    Robot) or unconventional (e.g., "Knight in Plate Armor" for a Dragon), estimate its nutritional value based on  its
    physical properties relative to a creature that can digest it.
    3. Assign a meal type to it, whether it is breakfast, lunch, dinner or dessert. If it is not a conventional meal or 
    is not classifiable put an empty string.
    4. Correct any typos and apply proper capitalization (e.g., "SPAGHETI" -> "Spaghetti").
    5. Identify the correct indefinite article. Do not include the article in the name field, only in the article field.
       CRITICAL: Use "" (empty string) for uncountable substances like honey, water, rice, gold, lava, etc., 
       unless it's a specific countable portion like "a sandwich". Use "" when the food name is plural.
    6. Provide nutritional values per 100g.
    7. Select a representative emoji. 
       For complex meals or meals which are difficult to depict in one emoji you can use 2 or 3 emojis.
    8. Determine the minimum mass of the meal in kilograms (float). If the meal inherently comes as a massive single 
    entity (e.g. an entire cow, a whale, a planet), specify its realistic minimum mass. If the 
    meal can be made arbitrarily small or is a normal portion (e.g., a cutlet, a dumpling, soup, a single sandwich), 
    set min_mass to 0.
    8. Return ONLY a valid JSON object.

    JSON FORMAT:
    {{
        "name": "Corrected or Generated Name",
        "art": "article",
        "meal_type": "dinner",
        "p": float,
        "c": float,
        "f": float,
        "e": "emojis",
        "min_mass": float
    }}
    """

    try:
        response = client.models.generate_content(model=MODEL_NAME, contents=prompt)
        raw_text = response.text.strip().replace("```json", "").replace("```", "").strip()
        data = json.loads(raw_text)

        # --- EMOJI SANITIZATION ---
        raw_emoji_string = data.get('e', '')

        # We strip out everything that is standard text/numbers/punctuation, leaving only potential emojis
        # This regex removes standard ASCII text, spaces, and brackets that AI loves to insert
        import re
        clean_emojis = "".join(c for c in raw_emoji_string if ord(c) > 1000 and c not in "()[]{} ,._-")

        # If the AI inserted purely text (like "dragon stew"), clean_emojis might become empty.
        # In that case, or if it's completely missing, we fall back to your local utility immediately.
        corrected_name = data.get('name', meal_input).strip().capitalize()
        if not clean_emojis:
            clean_emojis = util.food_to_emoji(corrected_name)

        data['e'] = clean_emojis
        # ---------------------------

        corrected_name_key = corrected_name.lower()

        # Update cache using our double storage strategy
        cache[search_key] = data
        if corrected_name_key and corrected_name_key != search_key:
            cache[corrected_name_key] = data

        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=4)

        return data
    except Exception as e:
        print(f"AI Engine Error: {e}")
        return None
