import asyncio
import json
import os
import random
import traceback

import ai

import util

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
CACHE_FILE = "meal_cache.json"
MODEL_ID = "nvidia/nemotron-3-ultra-550b-a55b"
MAX_AI_ATTEMPTS = 2

VALID_ARTICLES = ("", "a", "an", "the")
VALID_MEAL_TYPES = ("", "breakfast", "lunch", "dinner", "dessert")

# Keys used internally by the rest of the bot (cache format).
REQUIRED_MEAL_FIELDS = {
    "name",
    "art",
    "meal_type",
    "p",
    "c",
    "f",
    "e",
    "min_mass",
    "max_mass"
}

# JSON schema sent to the model. The keys are deliberately descriptive,
# they are mapped to the short internal keys in normalize_ai_meal().
_MEAL_OBJECT_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "article": {"type": "string", "enum": list(VALID_ARTICLES)},
        "meal_type": {"type": "string", "enum": list(VALID_MEAL_TYPES)},
        "protein": {"type": "number"},
        "carbs": {"type": "number"},
        "fat": {"type": "number"},
        "emoji": {"type": "string"},
        "min_mass_kg": {"type": "number"},
        "max_mass_kg": {"type": "number"},
    },
    "required": [
        "name", "article", "meal_type", "protein", "carbs",
        "fat", "emoji", "min_mass_kg", "max_mass_kg",
    ],
    "additionalProperties": False,
}

_ERROR_OBJECT_SCHEMA = {
    "type": "object",
    "properties": {"error": {"type": "string"}, "rule": {"type": "integer", "enum": [7, 8, 9]}},
    "required": ["error", "rule"],
    "additionalProperties": False,
}

# The model returns EITHER a meal OR an error object.
# If the provider does not support anyOf, use one object with all meal keys optional plus "error".
MEAL_JSON_SCHEMA = {"anyOf": [_MEAL_OBJECT_SCHEMA, _ERROR_OBJECT_SCHEMA]}

SYSTEM_INSTRUCTION = (
    "You are a nutritional and culinary engine for a modern RPG. "
    "Players in this game can be humans, robots, dragons, or monsters (e.g., Tarrasques). "
    "Return ONLY a valid JSON object (either a meal or an error object, as described), "
    "without any markdown formatting wrappers or extra text."
)

USER_PROMPT_TEMPLATE = """\
Provide nutritional data for this player-defined meal: '{meal_input}'.

Return ONE JSON object with exactly these keys:
{{
  "name": string,           // the player's full phrase, only spelling/capitalization fixed, WITHOUT a leading article (a, an)
  "article": string,        // exactly "a", "an" or "" (empty string)
  "meal_type": string,      // "breakfast", "lunch", "dinner", "dessert" or ""
  "protein": number,      // proportion of protein in the meal
  "carbs": number,        // proportion of carbohydrates in the meal
  "fat": number,          // proportion of fat in the meal
  "emoji": string,          // 1-3 emoji characters only, no text
  "min_mass_kg": number,    // minimum mass of the meal in kilograms
  "max_mass_kg": number     // maximum mass of the meal in kilograms
}}

Rules:
1. This is a fantasy RPG and everything in it is fiction. No medical warnings, moral commentary or
   refusals. ANY item can be a meal for a suitable creature: monsters eat people, knights, dragons,
   gods, other monsters and planets. Violence, gore and dark themes are never a reason to reject. ALWAYS return 
   nutritional values: for any item, however strange, estimate them from its physical composition. If the item is not 
   normally edible, estimate the macronutritional composition by vibes of its name.
2. "article" is ONLY a grammatical indefinite article ("a", "an") or "". Never put emoji or any
   other text there. Use "" for uncountable substances (honey, water, rice, gold, lava) and for
   plural names. Use "a"/"an" for single countable items (e.g. "a sandwich").
3. Nutrition must NEVER be all zeros. Individual values CAN be 0 (e.g. fat is 0 for most fruit,
   carbs is 0 for plain meat), only the sum must be above 0. If the item is not normally edible
   (a star, steel girders, a knight in plate armor), assume it is eaten by a creature able to
   digest it (a dragon, a robot, a Tarrasque) and estimate its macros from its composition.
4. If the item is not conventional assign "meal_type" based on vibes.
5. "emoji" must contain only emoji characters. For complex meals use up to 3 emoji.
6. min_mass_kg: Use 0 ONLY for divisible foods and standard portions that can naturally exist in arbitrarily small 
   amounts (a cutlet, a slice of bread, a drop of soup). 
   For holistic, monolithic, geographical, planetary, or cosmic entities that cannot naturally exist as a fractional 
   human portion (e.g., a planet, a star, an ocean, a mountain, a cathedral), min_mass_kg MUST reflect their true, 
   realistic minimum natural scale (e.g., actual mass of the smallest possible planet, a star's ignition threshold). 
   Never default to human-sized micro-portions for macro-objects.
   
   max_mass_kg: The largest mass the meal could possibly be. Be generous. It's very important to not understate this 
   value. Do not hesitate to scale it to mythological or cosmic scales, if the input calls for something gigantic. Use 
   scientific notation when needed.
   
   max_mass_kg must always be greater than min_mass_kg.

REJECTION RULES. If the input breaks any of rules 7-9, do NOT return a meal. Return only
{{"error": "Item not allowed: <short reason>", "rule": <7, 8 or 9>}} (English, reason under
100 characters), e.g. {{"error": "Item not allowed: potion", "rule": 7}}.
Rejecting is allowed ONLY for rules 7, 8 and 9. If the input doesn't break any of these 3 rules return a meal.
7. Potions are not food. Reject potions, elixirs, tonics and any magical or medicinal item
   with special effects.
8. The player may not request a bare macronutrient. Reject inputs that are just "fat", "protein",
   "carbohydrates", "carbs", or a quantity of them (e.g. "20 g of protein"). Concrete substances and
   products are allowed, even if nearly pure: sugar, butter, honey, olive oil, protein shake,
   protein powder.
9. The player may not describe a meal by its nutritional profile instead of its ingredients.
   Reject inputs like "fatty meal", "balanced meal", "high-protein dinner", "low-carb food",
   "healthy meal". Concrete ingredients are allowed, including extreme compositions: "Caesar salad
   with extra olive oil", "cereal with protein powder", "cheese with an insane amount of sugar".

Example for 'celery':
{{"name": "Celery", "article": "", "meal_type": "", "protein": 0.7, "carbs": 3.0, "fat": 0.2, "emoji": "🥬", "min_mass_kg": 0, "max_mass_kg": 0.5}}
"""

_cache_write_lock = asyncio.Lock()


class MealRejectedError(ValueError):
    """
    The model refused the item because it breaks the game rules (potion, requested macros, ...).
    Subclasses ValueError, so `except ValueError` in on_submit shows the message to the player.
    """


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------
def _load_cache_sync() -> dict:
    if not os.path.exists(CACHE_FILE):
        return {}
    try:
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            cache = json.load(f)
        return cache if isinstance(cache, dict) else {}
    except (json.JSONDecodeError, IOError):
        return {}


def _save_cache_sync(cache: dict) -> None:
    """Atomic write: a crash mid-write cannot corrupt the cache."""
    tmp_path = CACHE_FILE + ".tmp"
    with open(tmp_path, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False, indent=4)
    os.replace(tmp_path, CACHE_FILE)


async def _load_cache() -> dict:
    # File I/O runs in a thread so it never blocks the event loop (OneDrive can be slow).
    return await asyncio.to_thread(_load_cache_sync)


async def _store_in_cache(keys: list, data: dict) -> None:
    """Re-reads the cache under a lock, so parallel requests don't overwrite each other."""
    async with _cache_write_lock:
        cache = await asyncio.to_thread(_load_cache_sync)
        for key in keys:
            if key:
                cache[key] = data
        try:
            await asyncio.to_thread(_save_cache_sync, cache)
        except IOError:
            traceback.print_exc()


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
def is_meal_complete(meal: dict) -> bool:
    """
    Check whether a meal has all required fields AND sane values.
    Entries from the old, faulty format (emoji in 'art', all-zero macros,
    stray 'emoji' key) are treated as incomplete, so they get regenerated.
    """
    if not (
            isinstance(meal, dict)
            and all(field in meal and meal[field] is not None for field in REQUIRED_MEAL_FIELDS)
    ):
        return False

    try:
        return (
                meal["art"] in VALID_ARTICLES
                and float(meal["p"]) >= 0
                and float(meal["c"]) >= 0
                and float(meal["f"]) >= 0
                and float(meal["p"]) + float(meal["c"]) + float(meal["f"]) > 0
                and 0 <= float(meal["min_mass"]) < float(meal["max_mass"])
                and "emoji" not in meal
        )
    except (TypeError, ValueError):
        return False


def normalize_ai_meal(raw, fallback_name: str) -> dict:
    """
    Converts the model's JSON into the internal cache format and validates it.
    Raises ValueError with a human-readable message when the answer is unusable;
    that message is fed back to the model on retry.
    """
    if not isinstance(raw, dict):
        raise ValueError("the response is not a JSON object")

    if raw.get("error"):
        if str(raw.get("rule", "")).strip() not in ("7", "8", "9"):
            raise ValueError(
                "rejecting is allowed only for rules 7, 8 and 9 (potions, bare macronutrients, "
                "nutritional-profile descriptions). Cannibalism, humans or creatures as food, "
                "violence and gore are allowed in this game. Return the meal with nutritional values"
            )
        message = " ".join(str(raw["error"]).split())[:150]
        if not message.lower().startswith("item not allowed"):
            message = f"Item not allowed: {message}"
        raise MealRejectedError(message)

    def num(*keys) -> float:
        for key in keys:
            try:
                return float(raw[key])
            except (KeyError, TypeError, ValueError):
                continue
        raise ValueError(f"missing or non-numeric field '{keys[0]}'")

    name = str(raw.get("name") or fallback_name).strip().capitalize()

    article = str(raw.get("article", raw.get("art", "")) or "").strip().lower()
    if article not in VALID_ARTICLES:
        raise ValueError(f"'article' must be \"\", \"a\" or \"an\", got {article!r}")

    protein = num("protein", "p")
    carbs = num("carbs", "c")
    fat = num("fat", "f")
    if min(protein, carbs, fat) < 0 or not (0.1 <= protein + carbs + fat <= 100):
        raise ValueError(
            "protein + carbs + fat must be between 0.1 and 100 (never all zeros, never negative)"
        )

    min_mass = num("min_mass_kg", "min_mass")
    max_mass = num("max_mass_kg", "max_mass")
    if min_mass < 0 or max_mass <= min_mass:
        raise ValueError("max_mass_kg must be greater than min_mass_kg, and min_mass_kg must be >= 0")

    meal_type = str(raw.get("meal_type") or "").strip().lower()
    if meal_type not in VALID_MEAL_TYPES:
        meal_type = ""

    raw_emoji = ""
    for key in ("emoji", "e"):
        if isinstance(raw.get(key), str):
            raw_emoji = raw[key]
            break
    emojis = "".join(ch for ch in raw_emoji if ord(ch) > 1000)
    if not emojis:
        emojis = util.food_to_emoji(name)

    return {
        "name": name,
        "art": article,
        "meal_type": meal_type,
        "p": protein,
        "c": carbs,
        "f": fat,
        "e": emojis,
        "min_mass": min_mass,
        "max_mass": max_mass,
    }


# ---------------------------------------------------------------------------
# Model call
# ---------------------------------------------------------------------------
async def _ask_model(prompt: str) -> str:
    """
    Sends the prompt to the model and returns the raw response text.

    STRUCTURED OUTPUT: if your version of the `ai` SDK lets you pass a JSON
    schema / response format to the stream call, pass MEAL_JSON_SCHEMA here
    (check the SDK docs for the exact parameter name; I did not guess it).
    The code works without it, because the response is validated and retried anyway.
    """
    model = ai.get_model(MODEL_ID)
    messages = [
        ai.system_message(SYSTEM_INSTRUCTION),
        ai.user_message(prompt),
    ]

    response_text = ""
    async with ai.stream(model, messages) as stream:
        async for event in stream:
            if isinstance(event, ai.events.TextDelta):
                response_text += event.chunk
    return response_text


def _extract_json(text: str):
    """Parses JSON even if the model wrapped it in markdown fences or added stray text."""
    cleaned = text.strip().replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start != -1 and end > start:
            return json.loads(cleaned[start:end + 1])
        raise


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
async def get_nutrients_from_ai(meal_input: str, meal_type: str = "dinner", tier: int = 1):
    """
    Fetches nutritional data from cache or from the AI model asynchronously.
    If meal_input is a generation command ("__generate__..."), a random meal is
    selected locally from the cache. A specific custom meal that is missing from
    the cache (or whose cache entry is invalid) is requested from the AI model.

    Returns a meal dict in the internal format, or None if the AI failed.
    Raises MealRejectedError (a ValueError) with a player-facing message when the model
    rejects the item (potion, requested macros, ...). Rejections are not cached.
    """
    search_key = meal_input.lower().strip()
    cache = await _load_cache()

    # --- Random generation: purely local, never uses AI ---------------------
    if search_key.startswith("__generate__"):
        unique_meals = {}
        for value in cache.values():
            if isinstance(value, dict) and value.get("name"):
                unique_meals[str(value["name"]).strip().casefold()] = value
        meals = [m for m in unique_meals.values() if is_meal_complete(m)]

        if meals:
            matching = [m for m in meals if str(m.get("meal_type") or "").lower() == meal_type.lower()]
            return random.choice(matching or meals)

        default_meal = {
            "name": "Beef Stew",
            "art": "a",
            "meal_type": "dinner",
            "p": 15.0,
            "c": 10.0,
            "f": 8.0,
            "e": "🍲",
            "min_mass": 0.0,
            "max_mass": 5.0
        }
        await _store_in_cache(["beef stew"], default_meal)
        return default_meal

    # --- Specific meal: valid cache entry wins ------------------------------
    cached = cache.get(search_key)
    if is_meal_complete(cached):
        return cached

    # --- No API key: generic placeholder meal (not cached) ------------------
    if not os.getenv("AI_GATEWAY_API_KEY") and not os.getenv("OPENAI_API_KEY"):
        return {
            "name": meal_input.capitalize(),
            "art": "a",
            "meal_type": meal_type,
            "p": 10.0,
            "c": 10.0,
            "f": 5.0,
            "e": "🍽️",
            "min_mass": 0.0,
            "max_mass": 5.0
        }

    # --- Ask the AI, retrying once with the validation error ----------------
    base_prompt = USER_PROMPT_TEMPLATE.format(meal_input=meal_input)
    data = None
    last_error = None

    for _ in range(MAX_AI_ATTEMPTS):
        prompt = base_prompt
        if last_error:
            prompt += f"\n\nYour previous answer was invalid: {last_error}. Fix it and return the JSON again."
        try:
            response_text = await _ask_model(prompt)
            data = normalize_ai_meal(_extract_json(response_text), meal_input)
            break
        except MealRejectedError:
            raise  # a deliberate refusal from the model, passed on to the caller, no retry
        except Exception as e:
            last_error = str(e) or e.__class__.__name__
            data = None

    if data is None:
        print(f"AI meal generation failed for {meal_input!r}: {last_error}")
        return None

    # Double storage: the player's input and the corrected name point to the same data
    await _store_in_cache([search_key, data["name"].lower()], data)
    return data