import random
from typing import Optional
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from item import Food

import discord
import inflect
import pint
import json
import os
import re

import ai
import universe

p = inflect.engine()
# Initialize the unit registry
ureg = pint.UnitRegistry()
ureg.define('pferdestaerke = 735.49875 * watts = PS')

# Recommended replacement for ureg.default_format = ".3g"
# This setting applies the global formatting pattern to all formatting operations
ureg.formatter.default_format = ".3g"


def format_to_3_sig_figs(value):
    """
    Formats values to 3 significant figures without scientific notation.
    """
    if value == 0:
        return "0"

    import math
    abs_val = abs(value)
    # Determine position of the first significant digit
    log_val = math.floor(math.log10(abs_val))

    # Calculate precision to keep exactly 3 significant figures
    precision = max(0, 2 - log_val)

    # Format as fixed-point to avoid 'e+03'
    formatted = f"{value:.{precision}f}"

    # Clean up trailing zeros and dots
    if "." in formatted:
        formatted = formatted.rstrip('0').rstrip('.')

    return formatted


# A collection of immutable standards for physical comparison.
COMPARISON_STANDARDS = [
    # ---(< 1 kg) ---
    {"name": "a grain of sand", "mass": 2e-7, "length": 0.0005, "volume": 1e-10, "girth": 0.0015},
    {"name": "a honeybee", "mass": 0.0001, "length": 0.015, "wingspan": 0.025, "volume": 1e-6, "girth": 0.03},
    {"name": "a 1-Euro coin", "mass": 0.0075, "length": 0.0232, "volume": 8e-7, "girth": 0.073},
    {"name": "a standard 12-inch LP Vinyl Record", "mass": 0.18, "length": 0.304, "volume": 0.0001, "girth": 0.95},
    {"name": "an IKEA Pokal glass", "mass": 0.25, "length": 0.14, "volume": 0.00035, "girth": 0.24},
    {"name": "a standard football", "mass": 0.43, "length": 0.22, "volume": 0.0058, "girth": 0.69},
    {"name": "a Baseball Bat (Standard)", "mass": 0.95, "length": 0.86, "volume": 0.0008, "girth": 0.20},

    # ---(1 kg - 100 kg) ---
    {"name": "a standard Wine Bottle (750ml)", "mass": 1.3, "length": 0.30, "volume": 0.00075, "girth": 0.235},
    {"name": "a Landsknecht Zweihänder", "mass": 3.0, "length": 1.80, "volume": 0.001, "girth": 0.12},
    {"name": "a bowling ball", "mass": 7.2, "length": 0.218, "volume": 0.0054, "girth": 0.685},
    {"name": "a Wandering Albatross", "mass": 10.0, "length": 1.35, "wingspan": 3.10, "volume": 0.015, "girth": 0.80},
    {"name": "a standard 12kg kettlebell", "mass": 12.0, "length": 0.25, "volume": 0.0015, "girth": 0.60},
    {"name": "a standard adult bicycle", "mass": 15.0, "height": 1.05, "length": 1.75, "girth": 0.10},
    {"name": "an IKEA Kallax shelf (2x2)", "mass": 18.0, "length": 0.77, "height": 0.77, "volume": 0.23, "girth": 3.08},
    {"name": "an Olympic Barbell (Men's)", "mass": 20.0, "length": 2.20, "volume": 0.0025, "girth": 0.09},
    {"name": "an IKEA Malm Desk", "mass": 25.0, "length": 1.40, "height": 0.73, "volume": 0.65, "girth": 4.26},
    {"name": "a standard door frame", "mass": 40.0, "height": 2.03, "length": 0.81},
    {"name": "a King Size mattress", "mass": 45.0, "length": 2.03, "height": 0.25, "girth": 4.56},
    {"name": "a large Oak Barrel (empty)", "mass": 50.0, "length": 0.90, "volume": 0.225, "girth": 2.10},

    # ---(100 kg - 1000 kg) ---
    {"name": "a 100kg Heavy Punching Bag", "mass": 100.0, "length": 1.80, "volume": 0.15, "girth": 1.10},
    {"name": "a Giant Panda", "mass": 105.0, "length": 1.50, "height": 0.80, "girth": 1.30},
    {"name": "a classic Vespa GS 150", "mass": 111.0, "length": 1.70, "volume": 0.5, "girth": 1.20},
    {"name": "a Parlour Grand Piano", "mass": 350.0, "length": 1.87, "height": 1.0, "girth": 5.74},
    {"name": "a Ford Model T (Touring)", "mass": 540.0, "length": 3.40, "height": 2.10, "volume": 10.0, "girth": 11.0},
    {"name": "a Red Telephone Box (K6)", "mass": 750.0, "height": 2.51, "length": 0.91, "girth": 3.64},
    {"name": "a Cessna 172 Skyhawk", "mass": 760.0, "length": 8.28, "wingspan": 11.0, "height": 2.72, "volume": 25.0,
     "girth": 4.2},
    {"name": "a 1967 Volkswagen Beetle", "mass": 820.0, "length": 4.07, "height": 1.50, "volume": 12.0, "girth": 11.1},
    {"name": "a Snooker Table", "mass": 1000.0, "length": 1.77, "height": 0.85, "girth": 8.0},

    # ---(powyżej 1 t) ---
    {"name": "an ISO Shipping Container", "mass": 2200.0, "height": 2.59, "length": 6.06, "girth": 9.8},
    {"name": "a Supermarine Spitfire", "mass": 2300.0, "length": 9.12, "wingspan": 11.23, "volume": 15.0, "girth": 4.5},
    {"name": "a Routemaster bus", "mass": 7470.0, "length": 8.4, "height": 4.38, "volume": 80.0, "girth": 15.0},
    {"name": "a Douglas DC-3", "mass": 11800.0, "length": 19.7, "wingspan": 29.0, "volume": 120.0, "girth": 9.2},
    {"name": "a Boeing 747-400", "mass": 178700.0, "length": 70.6, "wingspan": 64.4, "volume": 1100.0, "girth": 20.4},
    {"name": "an Airbus A380", "mass": 575000.0, "length": 72.7, "wingspan": 79.7, "volume": 1500.0, "girth": 22.4},
    {"name": "the Elizabeth Tower (Big Ben)", "mass": 8600000.0, "height": 96.0, "volume": 4500.0, "girth": 48.0},
    {"name": "the Eiffel Tower", "mass": 10100000.0, "height": 330.0, "volume": 950000.0, "girth": 500.0},
    {"name": "the Titanic", "mass": 52310000.0, "length": 269.1, "volume": 130000.0, "girth": 56.0},
    {"name": "the Empire State Building", "mass": 331000000.0, "height": 381.0, "volume": 1047000.0, "girth": 130.0},
    {"name": "the Burj Khalifa", "mass": 450000000.0, "height": 828.0, "volume": 950000.0, "girth": 120.0},
    {"name": "the Great Pyramid of Giza", "mass": 6e9, "length": 230.0, "volume": 2580000.0, "girth": 920.0}
]


def format_quantity(quantity, unit_system=None, compare_to=None, show_alternative: bool = True) -> str:
    """
    Formats physical quantities with optional real-world comparisons.
    The 'compare_to' argument can be 'mass', 'length', 'height', 'girth', 'wingspan' or 'volume'.
    """
    import pint
    import math
    from player import UnitSystem

    if unit_system is None:
        unit_system = UnitSystem.METRIC

    if not isinstance(quantity, pint.Quantity):
        quantity = ureg.Quantity(quantity)

    def get_metric_suffix(q):
        # Recursive call to get the metric equivalent in parentheses
        metric_part = format_quantity(q, unit_system=UnitSystem.METRIC)
        return f" ({metric_part})"

        # --- HANDLE MASS ---
        # One must approach the measurement of matter with the utmost gravity.

    formatted_result = ""
    if quantity.check("[mass]"):
        if unit_system == UnitSystem.PRUSSIAN:
            # Based on 1817-1858 standards (1 Pfund = 0.4677 kg)
            # A sturdy Prussian Pfund, far more substantial than those flimsy 500g "metric" imposters.
            val_pfund = quantity.to_base_units().magnitude / 0.4677
            val_lot = val_pfund * 32

            if quantity < 0.001 * ureg.kg:
                # For items so minuscule they would escape the notice of a Prussian tax collector.
                formatted_result = f"{quantity.to_compact():#.3g~P}"
            elif val_lot < 1:
                # Splitting hairs, or rather, Lot.
                pr_str = f"{val_lot:.2f} Lot"
            elif val_pfund < 1:
                # Small treasures, perhaps a modest portion of tobacco.
                pr_str = f"{val_lot:.1f} Lot"
            elif val_pfund < 110:
                # The bread and butter of daily commerce.
                pfund_int = int(val_pfund)
                lot_rem = round((val_pfund - pfund_int) * 32)
                if lot_rem > 0:
                    pr_str = f"{pfund_int} Pfund {lot_rem} Lot"
                else:
                    pr_str = f"{pfund_int} Pfund"
            elif val_pfund < 4000:
                # For the serious merchant dealing in bulk.
                pr_str = f"{val_pfund / 110:.2f} Zentner"
            else:
                # For the heavy lifting of imperial shipping. 1 Last is approx 1870.8 kg.
                pr_str = f"{quantity.to_base_units().magnitude / 1870.8:.2f} Last"
            if show_alternative:
                formatted_result = f"{pr_str}{get_metric_suffix(quantity)}"
            else:
                formatted_result = pr_str

        elif unit_system == UnitSystem.US_CUSTOMARY:
            # Handling weights in the imperial fashion with appropriate thresholds
            val_oz = quantity.to(ureg.ounce).magnitude
            pounds_total = quantity.to(ureg.pound).magnitude
            tons = quantity.to(ureg.ton).magnitude
            if quantity < 1 * ureg.grain:
                # Extremely light masses
                formatted_result = f"{quantity.to_compact():#.3g~P}"

            elif quantity < 1 * ureg.dram:
                us_str = f"{quantity.to(ureg.grain).magnitude:#.3g} grains"
            elif quantity < 1 * ureg.ounce:
                us_str = f"{val_oz * 16:#.3g} drams"
            elif quantity < 1 * ureg.pound:
                us_str = f"{val_oz:#.3g} oz"
            elif pounds_total < 2000:
                # We handle the transition from pounds to tons.
                # To avoid leading zeros in tons (e.g., 0.7 tons), we stay in pounds until 2000 lb.

                pounds_int = int(pounds_total)

                if 1000 <= pounds_total < 2000:
                    # Special case for 1000-1999 lb to maintain 4 digits of precision
                    # instead of 3, avoiding scientific notation and rounding errors.
                    us_str = f"{pounds_int} lb"

                elif pounds_total < 100:
                    # Detailed view for lighter objects (e.g., "45 lb 8 oz")
                    ounces = int(round(val_oz % 16))
                    if ounces > 0:
                        us_str = f"{pounds_int} lb {ounces} oz"
                    else:
                        us_str = f"{pounds_int} lb"
                else:
                    # Standard 3-digit view for mid-range weights (100-999 lb)
                    us_str = f"{format_to_3_sig_figs(pounds_total)} lb"
            elif tons < 1000:
                # Only switch to tons when we have a full ton or more
                us_str = f"{tons:#.3g} tons"
                if show_alternative:
                    formatted_result = f"{us_str}{get_metric_suffix(quantity)}"
                else:
                    formatted_result = us_str
            else:
                # Revert to Metric for astronomical values
                formatted_result = format_quantity(quantity, UnitSystem.METRIC)
            if not formatted_result and us_str:
                if show_alternative:
                    formatted_result = f"{us_str}{get_metric_suffix(quantity)}"
                else:
                    formatted_result = us_str

        else:
            # --- METRIC MASS LOGIC ---
            if quantity < 1 * ureg.gram:
                compact = quantity.to_compact()
                val_str = format_to_3_sig_figs(compact.magnitude)
                formatted_result = f"{val_str} {compact.units:~P}"

            elif quantity < 1 * ureg.kilogram:
                val = quantity.to('gram').magnitude
                formatted_result = f"{format_to_3_sig_figs(val)} g"

            elif quantity < 1000 * ureg.kilogram:
                val = quantity.to('kilogram').magnitude
                formatted_result = f"{format_to_3_sig_figs(val)} kg"

            else:
                t_val = quantity.to('tonne').magnitude
                prefixes = ["", "k", "M", "G", "T", "P", "E", "Z", "Y", "R", "Q"]
                import math
                n = int(math.floor(math.log10(t_val) / 3)) if t_val > 0 else 0

                if n < len(prefixes):
                    scaled_value = t_val / (1000 ** n)
                    val_str = format_to_3_sig_figs(scaled_value)
                    formatted_result = f"{val_str} {prefixes[n]}t"

            # --- THE MEASUREMENT OF LENGTH ---
    elif quantity.check("[length]"):
        if unit_system == UnitSystem.PRUSSIAN:
            m = quantity.to(ureg.meter).magnitude
            pr_str = ""  # English: Temporary holder for the Prussian string

            if m < 0.002179:
                formatted_result = f"{quantity.to_compact():#.3g~P}"
            elif m < 0.02615:
                pr_str = f"{m / 0.002179:.2f} Linie"
            elif m < 0.31385:
                pr_str = f"{m / 0.02615:.1f} Zoll"
            elif m < 0.6669:
                pr_str = f"{m / 0.31385:.2f} Fuß"
            elif m < 3.766:
                pr_str = f"{m / 0.6669:.2f} Elle"
            elif m < 7532.5:
                pr_str = f"{m / 3.766:,.1f} Ruthe"
            else:
                pr_str = f"{m / 7532.5:,.2f} Meile"

            # Ensure the result is moved to the final variable if not already handled
            if not formatted_result and pr_str:
                if show_alternative:
                    formatted_result = f"{pr_str}{get_metric_suffix(quantity)}"
                else:
                    formatted_result = pr_str

        elif unit_system == UnitSystem.US_CUSTOMARY:
            inches = quantity.to(ureg.inch).magnitude
            us_str = ""  # Temporary holder for the US string
            if quantity < 0.001 * ureg.inch:
                # Removed # if it causes issues with Pint's format_spec
                formatted_result = f"{quantity.to_compact():.3g~P}"
            elif quantity < (1 / 32) * ureg.inch:
                val_mils = inches * 1000
                us_str = f"{val_mils:.3g} mil"
            elif quantity < 1 * ureg.inch:
                numerator = round(inches * 32)
                us_str = f"{numerator}/32\"" if numerator > 0 else f"{inches:.3f}\""
            elif quantity < 0.5 * ureg.mile:
                total_inches = quantity.to(ureg.inch).magnitude
                feet = int(total_inches // 12)
                rem_inches = total_inches % 12
                if feet >= 1:
                    us_str = f"{feet}' {rem_inches:.1f}\"" if round(rem_inches, 1) > 0 else f"{feet}'"
                else:
                    us_str = f"{rem_inches:.1f}\""
            else:
                # Use :,.3f for standard comma separation with 3 decimal places
                # or just :,.2f for a cleaner look in miles.
                val_miles = quantity.to(ureg.mile).magnitude
                us_str = f"{val_miles:,.2f} miles"

            # Final assignment for US Customary formatting
            if not formatted_result and us_str:
                if show_alternative:
                    formatted_result = f"{us_str}{get_metric_suffix(quantity)}"
                else:
                    formatted_result = us_str

        # --- METRIC LENGTH LOGIC ---
        else:
            val_in_cm = quantity.to(ureg.centimeter).magnitude
            if 1 <= val_in_cm <= 300:
                formatted_result = f"{val_in_cm:.0f} cm"
            else:
                formatted_result = f"{quantity.to_compact():#.3g~P}"

        # --- HANDLE VOLUME ---
    elif quantity.check("[volume]"):
        lites = quantity.to(ureg.liter).magnitude

        if unit_system == UnitSystem.PRUSSIAN:
            if lites < 1.145:
                compact = quantity.to_compact()
                val_str = format_to_3_sig_figs(compact.magnitude)
                formatted_result = f"{val_str} {compact.units:~P}"

            elif lites < 3.435:
                pr_str = f"{format_to_3_sig_figs(lites / 1.145)} Quart"
            elif lites < 54.96:
                pr_str = f"{format_to_3_sig_figs(lites / 3.435)} Quartier"
            elif lites < 219.85:
                pr_str = f"{format_to_3_sig_figs(lites / 54.961)} Scheffel"
            elif lites < 3957:
                pr_str = f"{format_to_3_sig_figs(lites / 219.85)} Tonne (Bier)"
            else:
                pr_str = f"{format_to_3_sig_figs(lites / 3957)} Last"
                if show_alternative:
                    formatted_result = f"{pr_str}{get_metric_suffix(quantity)}"
                else:
                    formatted_result = pr_str
            if not formatted_result and pr_str:
                if show_alternative:
                    formatted_result = f"{pr_str}{get_metric_suffix(quantity)}"
                else:
                    formatted_result = pr_str

        elif unit_system == UnitSystem.US_CUSTOMARY:
            # --- SMALL & MEDIUM VOLUMES ---
            if quantity < 1 * ureg.fluid_ounce:
                val = quantity.to(ureg.teaspoon).magnitude
                us_str = f"{format_to_3_sig_figs(val)} tsp"
            elif quantity < 1 * ureg.cup:
                val = quantity.to(ureg.fluid_ounce).magnitude
                us_str = f"{format_to_3_sig_figs(val)} fl oz"
            elif quantity < 4 * ureg.cup:
                val = quantity.to(ureg.cup).magnitude
                us_str = f"{format_to_3_sig_figs(val)} cup"
            elif quantity < 4 * ureg.quart:
                val = quantity.to(ureg.quart).magnitude
                us_str = f"{format_to_3_sig_figs(val)} qt"

            # --- LARGE VOLUMES (The Oil Barrel Scale) ---
            elif quantity < 42 * ureg.gallon:
                # Standard gallons up to exactly 1 Oil Barrel (42 gallons / ~159 liters)
                val = quantity.to(ureg.gallon).magnitude
                us_str = f"{format_to_3_sig_figs(val)} gal"
            elif quantity < 325851 * ureg.gallon:
                # Explicitly use oil_barrel to ensure it represents 42 gallons (159L) and not 31.5 gallons (119L)
                val = quantity.to(ureg.oil_barrel).magnitude
                us_str = f"{format_to_3_sig_figs(val)} bbl"
            else:
                # Acre-foot (325,851 gallons) for colossally large volumes
                val = quantity.to(ureg.acre_foot).magnitude
                us_str = f"{format_to_3_sig_figs(val)} ac-ft"
            # --- FINAL ASSEMBLY ---
            if not formatted_result and us_str:
                formatted_result = f"{us_str}{get_metric_suffix(quantity)}"
        else:
            # --- METRIC VOLUME ---
            if quantity.check('[length]**3'):
                # Check magnitude in liters to decide the scale
                volume_in_liters = quantity.to(ureg.liter).magnitude

                if volume_in_liters >= 1000:
                    # For 1000L and above, use cubic meters
                    quantity = quantity.to(ureg.m ** 3)
                else:
                    # Below 1000L, stick to the liter family (ml, l)
                    quantity = quantity.to(ureg.liter)

            compact = quantity.to_compact()
            val_str = format_to_3_sig_figs(compact.magnitude)
            formatted_result = f"{val_str} {compact.units:~P}"

    # --- HANDLE ENERGY ---
    elif quantity.check("[energy]"):
        if unit_system == UnitSystem.METRIC:
            compact = quantity.to_compact()
            formatted_result = f"{format_to_3_sig_figs(compact.magnitude)} {compact.units:~P}"

        elif unit_system == UnitSystem.US_CUSTOMARY:
            val = quantity.to(ureg.calorie).magnitude
            q_cal = val * ureg.calorie
            compact = q_cal.to_compact()
            formatted_result = f"{format_to_3_sig_figs(compact.magnitude)} {compact.units:~P}"

        elif unit_system == UnitSystem.PRUSSIAN:
            # Conversion to Prussian Horsepower-hour (PS·h)
            # 1 PS·h = 2,647,795.5 Joules
            joules = quantity.to(ureg.joule).magnitude
            ps_h_value = joules / 2647795.5
            # We use PS·h for standard dragon-scale energy values.
            # If the value is still extreme, we fall back to compact metric.
            if ps_h_value >= 10000 or ps_h_value < 0.01:
                compact = quantity.to_compact()
                formatted_result = f"{format_to_3_sig_figs(compact.magnitude)} {compact.units:~P}"
            else:
                # Using our robust formatter to keep 3 or 4 sig figs
                val_str = format_to_3_sig_figs(ps_h_value)
                formatted_result = f"{val_str} PS·h{get_metric_suffix(quantity)}"

    # --- COMPARISON LOGIC ---
    if compare_to:
        # English: Safely extract magnitude and check for zero/NaN/Inf
        mag = quantity.to_base_units().magnitude

        if mag > 0 and not math.isnan(mag) and not math.isinf(mag):
            best_match = None
            min_diff = float('inf')

            for obj in COMPARISON_STANDARDS:
                if compare_to in obj:
                    obj_val = obj[compare_to]
                    # English: Logarithmic difference helps find the right order of magnitude
                    diff = abs(math.log10(mag) - math.log10(obj_val))
                    if diff < min_diff:
                        min_diff = diff
                        best_match = obj

            if best_match:
                val_ref = best_match[compare_to]
                ratio = mag / val_ref
                name = best_match['name']

                # English: Natural language mapping for ratios
                if 0.95 <= ratio <= 1.05:
                    comparison_str = f"about the same {compare_to} as {name}"
                elif 1.05 < ratio <= 1.5:
                    comparison_str = f"slightly larger {compare_to} than {name}"
                elif 0.75 <= ratio < 0.95:
                    comparison_str = f"slightly smaller {compare_to} than {name}"
                elif ratio > 1.5:
                    comparison_str = f"{ratio:.1f}x the {compare_to} of {name}"
                else:
                    # English: Handling small ratios using clean percentage formatting
                    inv_ratio = 1 / ratio
                    if 1.9 <= inv_ratio <= 2.1:
                        comparison_str = f"half the {compare_to} of {name}"
                    else:
                        # English: Use a standard percentage format and append the rest manually
                        percentage = ratio * 100
                        comparison_str = f"{percentage:.1f}% of the {compare_to} of {name}"

                # English: Ensure we don't double-append if the function is called recursively
                if " — " not in formatted_result:
                    formatted_result += f" — {comparison_str}"

    return formatted_result


from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import player


def get_player_from_ctx(ctx) -> 'player.Player':
    # Get the universe based on the channel ID
    this_universe = universe.multiverse_instance.get_universe_from_id(ctx.channel.id)
    if this_universe is None:
        return None

    # Retrieve the player based on the author ID
    return this_universe.get_player_by_id(ctx.author.id)


def get_player_from_interaction(interaction: discord.Interaction) -> 'player.Player':
    """
    Retrieves the player object from a discord.Interaction by checking
    the universe associated with the channel ID.
    """
    # 1. Get the universe based on the channel ID where interaction happened
    # English: Accessing the global multiverse instance to find the local universe
    this_universe = universe.multiverse_instance.get_universe_from_id(interaction.channel_id)

    if this_universe is None:
        return None

    # 2. Retrieve the player based on the user ID of the person who triggered it
    return this_universe.get_player_by_id(interaction.user.id)


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


def get_player_from_member(source, member: 'discord.Member') -> 'player.Player':
    """
    Retrieves a player based on a Discord Member object.

    :param source: Either `commands.Context` or `discord.Interaction`
    :param member: The Discord Member whose player instance to retrieve
    :return: The corresponding player object or None if not found
    """
    return get_player_from_id(source, member.id)


# Assuming your cache file path is accessible
CACHE_FILE = "meal_cache.json"


def get_article(food_name: str) -> str:
    clean_key = re.sub(r'[^\w\s]', '', food_name).lower().strip()

    prefix_match = re.match(r"^([\W_]*\s*)(.*)$", food_name)
    prefix = prefix_match.group(1) or ""
    core_text = prefix_match.group(2) or food_name

    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                cache = json.load(f)

                if clean_key in cache:
                    cached_data = cache[clean_key]
                    article = cached_data.get('art', "").strip()

                    if article:
                        return f"{prefix}{article} {core_text.strip()}"
                    else:
                        return food_name
        except Exception as e:
            print(f"Cache Reading Error in get_article: {e}")

    words_list = core_text.split()
    if not words_list:
        return food_name

    last_word_clean = words_list[-1].rstrip(',.').lower()

    if last_word_clean.endswith('s'):
        return f"{prefix}{core_text}"

    first_word_full = words_list[0]
    first_word_clean = first_word_full.rstrip(',')

    article_with_first_word = p.a(first_word_clean)

    if first_word_full.endswith(','):
        article_with_first_word += ','

    formatted_phrase = core_text.replace(first_word_full, article_with_first_word, 1)

    return f"{prefix}{formatted_phrase}"


def get_food_name_with_article(food_name: str, food_emoji: str) -> str:
    """
    Determines the correct article for a food name and places the emoji at the very front.
    Priority: 1. AI Cache -> 2. Local Linguistic Fallback
    """
    # 1. CLEAN KEY FOR CACHE LOOKUP
    clean_key = re.sub(r'[^\w\s]', '', food_name).lower().strip()

    # 2. TRY AI CACHE
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                cache = json.load(f)
                if clean_key in cache:
                    cached_data = cache[clean_key]
                    article = cached_data.get('art', "").strip()

                    if article:
                        phrase = f"{article} {food_name}"
                    else:
                        phrase = food_name

                    return f"{food_emoji} {phrase}" if food_emoji else phrase
        except Exception as e:
            print(f"Cache Reading Error in get_food_name_with_article: {e}")

    # 3. LINGUISTIC FALLBACK (Runs if cache miss or error)
    words_list = food_name.split()
    if not words_list:
        return f"{food_emoji} {food_name}" if food_emoji else food_name

    # Check the last word to see if it's plural (simple heuristic)
    last_word_clean = words_list[-1].rstrip(',.').lower()

    # Handle plural nouns (if ends with 's', skip article)
    if last_word_clean.endswith('s'):
        phrase = food_name
        return f"{food_emoji} {phrase}" if food_emoji else phrase

    # Handle phonetic article via inflect engine on the first word
    first_word_full = words_list[0]
    first_word_clean = first_word_full.rstrip(',')

    article_with_first_word = p.a(first_word_clean)

    if first_word_full.endswith(','):
        article_with_first_word += ','

    formatted_phrase = food_name.replace(first_word_full, article_with_first_word, 1)

    return f"{food_emoji} {formatted_phrase}" if food_emoji else formatted_phrase


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
        "fry": "🍟",
        "chip": "🍟",
        "fast food": "🍟",
        "sandwich": "🥪",
        "hot dog": "🌭",
        "paella": "🥘",
        "stew": "🥘",
        "pie": "🥧",
        "bento": "🍱",
        "rice cracker": "🍘",
        "onigiri": "🍙",
        "rice ball": "🍙",
        "shaved ice": "🍧",
        "dango": "🍡",
        "fortune cookie": "🥠",
        "takeout": "🥡",
        "falafel": "🧆",
        "canned food": "🥫",
        "salt": "🧂",

        # Sweet foods
        "cake": "🍰",
        "cookie": "🍪",
        "ice cream": "🍦",
        "donut": "🍩",
        "chocolate": "🍫",
        "candy": "🍬",
        "sweet": "🍬",
        "cotton candy": "🍭",

        # Fruits
        "apple": "🍎",
        "green apple": "🍏",
        "banana": "🍌",
        "grape": "🍇",
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
        "melon": "🍈",
        "mango": "🥭",
        "chestnut": "🌰",
        "olive": "🫒",
        "coconut": "🥥",

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
        "bean": "🫘",
        "pea pod": "🫛",
        "green pepper": "🫑",
        "sweet potato": "🍠",
        "yam": "🍠",

        # Grains and bread
        "bread": "🍞",
        "cheese": "🧀",
        "butter": "🧈",
        "pasta": "🍝",
        "noodle": "🍜",
        "rice": "🍚",
        "dumpling": "🥟",
        "ravioli": "🥟",  # Ravioli are a type of dumpling
        "pierogi": "🥟",  # Pierogi are also dumplings
        "pieróg": "🥟",
        "bao": "🥟",  # Bao is a type of steamed dumpling
        "pretzel": "🥨",
        "bagel": "🥯",
        "pancake": "🥞",
        "waffle": "🧇",
        "cereal": "🥣",
        "oatmeal": "🥣",
        "flatbread": "🫓",
        "naan": "🫓",

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
        "whiskey": "🥃",

        # Soups and salads
        "soup": "🍲",
        "salad": "🥗",
        "oden": "🍢",
        "kebab": "🍢",

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
        "kiwi": "🥝",
        "pumpkin": "🎃",
        "peanut": "🥜",
        "honey": "🍯",
        "fried egg": "🍳",
        "omelette": "🍳",

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

    all_matches = []

    # 1
    foods = sorted(food_emojis.items(), key=lambda x: -len(x[0]))

    # 2
    covered_indices = set()

    for food, emoji in foods:
        if food.endswith('y'):
            base = re.escape(food[:-1])
            pattern = r'\b(?:' + re.escape(food) + r'|' + base + r'ies)\b'
        elif food.endswith(('o', 'ch', 'sh', 'ss', 'x')):
            pattern = r'\b' + re.escape(food) + r'(?:es|s)?\b'
        else:
            pattern = r'\b' + re.escape(food) + r's?\b'

        for match in re.finditer(pattern, food_name):
            start, end = match.span()
            if not any(i in covered_indices for i in range(start, end)):
                all_matches.append((start, emoji))
                for i in range(start, end):
                    covered_indices.add(i)

    # 3
    all_matches.sort(key=lambda x: x[0])

    result_emojis = [emoji for pos, emoji in all_matches]

    if result_emojis:
        return ' '.join(result_emojis)

    return "🍽️"


# Nutrient values per portion/emoji: (Proteins, Carbohydrates, Fats)
nutrients = {
    # Fish and seafood (High Protein)
    "🐟": (15.0, 0.0, 3.0),  # fish
    "🍤": (10.0, 5.0, 4.0),  # shrimp
    "🦞": (18.0, 1.0, 1.0),  # lobster
    "🦀": (14.0, 0.0, 1.0),  # crab
    "🍣": (8.0, 15.0, 2.0),  # sushi
    "🐙": (12.0, 2.0, 1.0),  # octopus
    "🦪": (7.0, 3.0, 2.0),  # oyster/scallop
    "🦑": (13.0, 2.0, 1.0),  # squid

    # Fast food (High Carb & Fat)
    "🍕": (10.0, 35.0, 12.0),  # pizza
    "🍔": (15.0, 30.0, 14.0),  # burger
    "🍟": (3.0, 40.0, 15.0),  # fries
    "🥪": (12.0, 25.0, 8.0),  # sandwich
    "🌭": (8.0, 20.0, 15.0),  # hot dog
    "🌮": (10.0, 20.0, 10.0),  # taco
    "🌯": (15.0, 45.0, 12.0),  # burrito
    "🥨": (10.0, 75.0, 3.0),  # pretzel
    "🥯": (10.0, 48.0, 1.5),  # bagel
    "🥞": (6.0, 28.0, 10.0),  # pancakes
    "🧇": (6.0, 35.0, 14.0),  # waffle
    "🍳": (13.0, 1.0, 11.0),  # cooking/fried egg
    "🥘": (12.0, 15.0, 8.0),  # paella/shallow pan of food
    "🥣": (5.0, 25.0, 2.0),  # cereal/oatmeal
    "🥧": (4.0, 45.0, 22.0),  # pie
    "🍱": (15.0, 35.0, 10.0),  # bento box
    "🍘": (7.0, 80.0, 1.0),  # rice cracker
    "🍙": (2.5, 40.0, 0.5),  # rice ball (onigiri)
    "🍧": (0.0, 30.0, 0.0),  # shaved ice
    "🍡": (1.0, 45.0, 0.5),  # dango
    "🥠": (4.0, 75.0, 3.0),  # fortune cookie
    "🥡": (10.0, 40.0, 12.0),  # takeout box

    # Sweet foods (Pure Carb & Fat)
    "🍰": (3.0, 50.0, 20.0),  # cake
    "🍪": (2.0, 20.0, 8.0),  # cookie
    "🍦": (4.0, 25.0, 10.0),  # ice cream
    "🍩": (2.0, 30.0, 15.0),  # donut
    "🍫": (4.0, 40.0, 30.0),  # chocolate
    "🍬": (0.0, 10.0, 0.0),  # candy
    "🍭": (0.0, 20.0, 0.0),  # cotton candy/lollipop
    "🍯": (0.0, 17.0, 0.0),  # honey

    # Fruits (Pure Carb/Sugar)
    "🍎": (0.3, 14.0, 0.2),  # red apple
    "🍏": (0.4, 13.0, 0.1),  # green apple
    "🍌": (1.1, 23.0, 0.3),  # banana
    "🍇": (0.7, 18.0, 0.2),  # grapes
    "🍊": (0.9, 12.0, 0.1),  # orange
    "🍉": (0.6, 8.0, 0.2),  # watermelon
    "🍋": (0.4, 9.0, 0.1),  # lemon
    "🍓": (0.7, 8.0, 0.3),  # strawberry
    "🍍": (0.5, 13.0, 0.1),  # pineapple
    "🍒": (1.0, 12.0, 0.3),  # cherry
    "🫐": (0.7, 14.0, 0.3),  # blueberry
    "🍑": (0.9, 10.0, 0.3),  # plum/peach
    "🍐": (0.4, 15.0, 0.1),  # pear
    "🥭": (0.8, 15.0, 0.4),  # mango
    "🥝": (1.1, 15.0, 0.5),  # kiwi
    "🥥": (3.3, 15.0, 33.0),  # coconut
    "🍈": (0.8, 8.0, 0.2),  # melon
    "🌰": (2.4, 45.0, 2.3),  # chestnut
    "🫒": (0.8, 6.0, 11.0),  # olive

    # Vegetables
    "🥕": (0.9, 10.0, 0.2),  # carrot
    "🥦": (2.8, 7.0, 0.4),  # broccoli
    "🍅": (0.9, 3.9, 0.2),  # tomato
    "🥔": (2.0, 17.0, 0.1),  # potato
    "🥬": (1.3, 3.3, 0.3),  # lettuce
    "🧅": (1.1, 9.0, 0.1),  # onion
    "🧄": (6.0, 33.0, 0.5),  # garlic
    "🌶️": (1.9, 9.0, 0.4),  # pepper
    "🌽": (3.2, 19.0, 1.2),  # corn
    "🍄": (3.1, 3.3, 0.3),  # mushroom
    "🍆": (1.0, 6.0, 0.2),  # eggplant
    "🥑": (2.0, 9.0, 15.0),  # avocado
    "🥒": (0.7, 3.6, 0.1),  # cucumber
    "🍃": (5.0, 14.0, 0.4),  # pea
    "🎃": (1.0, 6.5, 0.1),  # pumpkin
    "🫘": (21.0, 63.0, 1.2),  # beans
    "🫛": (5.0, 14.0, 0.4),  # pea pod
    "🫑": (1.0, 6.0, 0.3),  # bell pepper
    "🍠": (1.6, 20.0, 0.1),  # roasted sweet potato

    # Grains and Bread
    "🍞": (9.0, 49.0, 3.0),  # bread
    "🥖": (10.0, 52.0, 3.0),  # baguette
    "🥐": (8.0, 45.0, 21.0),  # croissant
    "🍝": (5.0, 30.0, 1.0),  # pasta/spaghetti
    "🍜": (7.0, 40.0, 4.0),  # noodles/ramen
    "🍚": (2.7, 28.0, 0.3),  # rice
    "🥟": (8.0, 25.0, 6.0),  # dumplings

    # Dairy and Eggs
    "🥛": (3.4, 5.0, 3.7),  # milk
    "🧀": (25.0, 1.3, 33.0),  # cheese
    "🧈": (0.9, 0.1, 81.0),  # butter
    "🥚": (13.0, 1.1, 11.0),  # egg

    # Meat and Poultry (Protein heavy)
    "🥩": (25.0, 0.0, 15.0),  # meat (beef)
    "🍖": (20.0, 0.0, 10.0),  # morsel/meat on bone
    "🍗": (18.0, 0.0, 8.0),  # chicken
    "🥓": (37.0, 1.4, 42.0),  # bacon

    # Soups and Mixed
    "🍲": (8.0, 15.0, 5.0),  # soup
    "🥗": (3.0, 10.0, 7.0),  # salad
    "🍢": (12.0, 18.0, 4.0),  # oden

    # Others
    "🥜": (26.0, 16.0, 49.0),  # peanut
    "🧂": (0.0, 0.0, 0.0),  # salt
    "🥫": (5.0, 15.0, 2.0),  # canned food
    "🫓": (8.0, 45.0, 2.0),  # flatbread
    "🧆": (13.0, 30.0, 18.0),  # falafel
}


def create_food_by_name(meal_name: str, size_kg: float, tier: int, meal_type: str = "dinner") -> "Food":
    """
    Creates a Food object using the provided name or generation string.
    """
    final_protein, final_carbs, final_fat = 0.0, 0.0, 0.0
    display_name = meal_name.strip().capitalize()

    # Pass the name, type, and tier to our unified AI engine
    ai_data = ai.get_nutrients_from_ai(meal_name.strip(), meal_type=meal_type, tier=tier)

    if ai_data:
        # AI SUCCESS PATH (Both for player input and auto-generated meals)

        # --- MINIMUM MASS VALIDATION ---
        min_mass = ai_data.get('min_mass', 0.0)
        if size_kg < min_mass:
            raise ValueError(
                f"The requested portion is too small. '{ai_data.get('name', display_name)}' requires a minimum mass of "
                f"{format_quantity(min_mass * ureg.kg)}.")
        # -------------------------------

        total_p_raw = ai_data.get('p', 0.0)
        total_c_raw = ai_data.get('c', 0.0)
        total_f_raw = ai_data.get('f', 0.0)

        display_name = ai_data.get('name', display_name)
        meal_emoji = ai_data.get('e', food_to_emoji(display_name))
    else:
        # FALLBACK PATH (Runs ONLY if AI fails entirely / returns None)
        if meal_name.startswith("__generate__"):
            fallback_names = {"breakfast": "Oatmeal", "lunch": "Sandwich", "dinner": "Hearty Stew",
                              "dessert": "Sweet Cake"}
            display_name = fallback_names.get(meal_type, "Standard Ration")

        meal_emoji = food_to_emoji(display_name)
        unique_ingredients = []
        for char in meal_emoji:
            if char not in unique_ingredients:
                unique_ingredients.append(char)

        total_p_raw, total_c_raw, total_f_raw = 0.0, 0.0, 0.0
        phi = 1.61803398875

        for i, e in enumerate(unique_ingredients):
            if e in nutrients:
                p, c, f = nutrients[e]
                weight = 1.0 / (phi ** i)
                total_p_raw += p * weight
                total_c_raw += c * weight
                total_f_raw += f * weight

    raw_mass_sum = total_p_raw + total_c_raw + total_f_raw
    if raw_mass_sum > 0:
        scaling_factor = size_kg / raw_mass_sum
        final_protein = total_p_raw * scaling_factor
        final_carbs = total_c_raw * scaling_factor
        final_fat = total_f_raw * scaling_factor

    from item import Food
    return Food(
        name=display_name,
        value=0,
        size=final_carbs,
        tier=tier,
        protein=final_protein,
        fat=final_fat,
        emoji=meal_emoji
    )


def create_food_by_type(meal_type: str, size_kg: float, tier: int) -> "Food":
    """
    Selects a random meal matching the meal_type from cache.
    Treats missing min_mass as 0.0. If a chosen meal lacks min_mass,
    it queries the API to regenerate it, updates the cache, and checks the size.
    If the final min_mass is greater than size_kg, it rolls again.
    """
    meal_type = meal_type.lower().strip()

    while True:
        cached_matches = []
        cache_keys_to_remove = []

        # 1. Gather all matching meals from cache (treating missing min_mass as 0.0)
        if os.path.exists(ai.CACHE_FILE):
            try:
                with open(ai.CACHE_FILE, 'r', encoding='utf-8') as f:
                    cache = json.load(f)
                    for key, data in cache.items():
                        if key.startswith("__generate__"):
                            continue
                        if data.get('meal_type', '').lower().strip() == meal_type:
                            cached_matches.append((key, data))
            except (json.JSONDecodeError, IOError):
                pass

        # 2. If we have matches, pick one at random
        if cached_matches:
            chosen_key, chosen_meal_data = random.choice(cached_matches)
            meal_name = chosen_meal_data.get('name', 'Unknown Dish')

            # Check if min_mass is missing from this cached entry
            if "min_mass" not in chosen_meal_data:
                # Query API to regenerate/update the meal so it gets min_mass
                # We call get_nutrients_from_ai directly to get the fresh data and update cache
                updated_data = ai.get_nutrients_from_ai(meal_name, meal_type=meal_type, tier=tier)

                if updated_data:
                    chosen_meal_data = updated_data

            min_mass = chosen_meal_data.get('min_mass', 0.0)

            # 3. Validate mass: if it's too big, roll again by continuing the loop
            if size_kg < min_mass:
                continue

            # If valid, create and return the food item using its name
            return create_food_by_name(meal_name, size_kg, tier, meal_type=meal_type)

        # 4. Cache Miss (no meals of this type at all): Request generation via API
        generation_command = f"__generate_random_{meal_type}__"
        return create_food_by_name(generation_command, size_kg, tier, meal_type=meal_type)


class FoodOfTheDay:
    def __init__(self, food_emojis_dict: dict[str, str]):
        """
        Initialize the culinary rotation using a proper dictionary of delicacies.
        One must ensure the larder is well-stocked before the guests arrive.
        """
        self._emoji_by_universe: dict["universe.Universe", str] = {}
        # We extract the emojis (values) from the provided dictionary.
        # This ensures we are picking from the treats themselves, not their names.
        self._food_emojis_dict = food_emojis_dict

    @property
    def _options(self) -> list[str]:
        """
        A private property to fetch the latest selection of emojis.
        It is best to serve the freshest ingredients available.
        """
        return list(self._food_emojis_dict.keys())

    def get(self, universe: "universe.Universe") -> Optional[str]:
        return self._emoji_by_universe.get(universe)

    def set(self, universe: "universe.Universe", emoji: str) -> None:
        self._emoji_by_universe[universe] = emoji

    def reroll(self, universe: "universe.Universe", fallback: str = "🍽️") -> str:
        """
        Assign a fresh emoji to a specific universe.
        A change of menu is often as good as a holiday.
        """
        options = self._options
        new_emoji = random.choice(options) if options else fallback
        self._emoji_by_universe[universe] = new_emoji
        return new_emoji

    def choose_if_missing(self, universe: "universe.Universe", fallback: str = "🍽️") -> str:
        """Assign a random delicacy if the universe's plate is currently empty."""
        if universe not in self._emoji_by_universe:
            self.reroll(universe, fallback)
        return self._emoji_by_universe[universe]

    def choose_for_missing(self, universes: list["universe.Universe"]):
        """Assign random emojis to all famished universes in the list."""
        for uni in universes:
            self.choose_if_missing(uni)

    def reroll_all(self, universes: Optional[list["universe.Universe"]] = None):
        """
        Reroll emojis for all universes currently in the rotation.
        Consistency is key, even when changing the entire menu.
        """
        target_universes = universes if universes else list(self._emoji_by_universe.keys())
        for uni in target_universes:
            self.reroll(uni)


def get_growth_report(mass_before, mass_after, height_before, height_after, fat_ratio_before, fat_ratio_after, units):
    """
    Generates a consolidated report of physical changes during a growth or shrinking phase.
    English comments as requested by Waszmość.
    """
    report_parts = []

    # 1. Total Mass Change
    mass_delta = mass_after - mass_before
    if abs(mass_delta) > 0.0001:
        m_str = format_quantity(abs(mass_delta) * ureg.kg, units)
        word = "gained" if mass_delta > 0 else "lost"
        report_parts.append(f"You have {word} {m_str} of total mass.")

    # 2. Height Change (Obsługuje zarówno wzrost, jak i kurczenie się)
    height_delta = height_after - height_before
    if abs(height_delta) > 0.0001:
        h_str = format_quantity(abs(height_delta) * ureg.m, units)
        word = "taller" if height_delta > 0 else "shorter"
        report_parts.append(f"You have grown {h_str} {word}.")

    # 3. Body Composition (Fatness)
    fat_ratio_delta = fat_ratio_after - fat_ratio_before
    abs_fat_delta = abs(fat_ratio_delta)

    intensity = None
    if abs_fat_delta > 0.05:
        intensity = "massively"
    elif abs_fat_delta > 0.02:
        intensity = "much"
    elif abs_fat_delta > 0.01:
        intensity = "noticeably"
    elif abs_fat_delta > 0.001:
        intensity = "slightly"

    if intensity:
        direction = "fatter" if fat_ratio_delta > 0 else "skinnier"
        report_parts.append(f"You have become {intensity} {direction}.")

    # JOIN WITH NEWLINES TO AVOID PRINTING RAW PYTHON LIST BRACKETS []
    return "\n".join(report_parts)


def get_stamina_display(this_player, units):
    """
    English: Generates a stamina bar where the number of segments represents
    physical capacity, but is capped to prevent Discord API payload errors.
    """

    cost_per_rep = this_player.workout_cost

    if cost_per_rep <= 0:
        return "Stamina: ∞\n└ `Infinite Energy`"

    # Calculate real physical capacity
    max_exercises = int(this_player.max_stamina / cost_per_rep)
    available_exercises = int(this_player.stamina / cost_per_rep)

    # VISUAL CAPPING:
    # We allow the bar to grow naturally with the character's stats,
    # but we cap it at 50 segments to stay well within Discord's 1024-character field limit.
    # If the dragon is small or weak, it might show 3 segments. If it's a titan, it shows up to 50.
    visual_max = min(max_exercises, 50)

    # Scale the filled portion relative to the cap if needed,
    # or keep it 1:1 if below the cap.
    if max_exercises > 50:
        fill_ratio = available_exercises / max_exercises
        visual_filled = int(visual_max * fill_ratio)
    else:
        visual_filled = available_exercises
        visual_max = max_exercises

    bar = "▰" * visual_filled + "▱" * (visual_max - visual_filled)

    # Energy formatting using Pint
    curr_st_val = format_quantity(this_player.stamina * ureg.J, units)
    max_st_val = format_quantity(this_player.max_stamina * ureg.J, units)

    display = (
        f"**Stamina:** {bar} **{available_exercises}/{max_exercises}**\n"
        f"└ `{curr_st_val} / {max_st_val}`"
    )

    return display


def get_size_reserve_display(this_player, units) -> tuple[str, bool, bool]:
    """
    Generates a 10-segment size reserve bar string. Supports overfilling past 100%.
    Returns a tuple: (display_text, show_grow_button, show_resist_button)
    """
    this_universe = this_player.universe
    is_rule_active = getattr(this_universe, "size_reserve_active", True)
    if not is_rule_active:
        return "", False, False

    current_reserve = this_player.size_reserve
    max_reserve = this_player.max_size_reserve

    if max_reserve <= 0:
        return "**Size Reserve:** ∞\n└ `Infinite Capacity`", False, False

    # Base visual parameters
    base_segments = 10
    raw_ratio = current_reserve / max_reserve
    percentage = int(raw_ratio * 100)

    if raw_ratio <= 1.0:
        filled_segments = int(base_segments * max(0.0, raw_ratio))
        if current_reserve > 0 and filled_segments == 0:
            filled_segments = 1
        bar = "▰" * filled_segments + "▱" * (base_segments - filled_segments)
    else:
        overfill_ratio = raw_ratio - 1.0
        extra_segments = min(int(overfill_ratio * 10), 30)
        if extra_segments == 0:
            extra_segments = 1
        bar = "▰" * base_segments + "⧇" * extra_segments + " ⚠️ OVERFLOW"

    # Format using Pint system
    curr_res_val = format_quantity(current_reserve * ureg.kg, units)
    max_res_val = format_quantity(max_reserve * ureg.kg, units)

    display = (
        f"**Size Reserve:** {bar} **{percentage}%**\n"
        f"└ `{curr_res_val} / {max_res_val}`"
    )

    # Determine UI requirements based on current state data
    show_grow = current_reserve > 0
    show_resist = current_reserve > max_reserve

    return display, show_grow, show_resist


# Implementation:
food_of_the_day = FoodOfTheDay(nutrients)
