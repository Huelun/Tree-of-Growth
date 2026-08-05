import asyncio
import datetime
import math
import os
import logging
import random
from enum import Enum
from typing import Any

import discord
import pint
import yaml
from discord import Member, app_commands
from discord.ext import commands
from discord.ext.commands import Context

import effect
import item
import player
import universe
import util
from effect import EffectType, Effect
from interaction_system import PlayerInteractionView
from item import Potion
from player import UnitSystem
from talents import talent_tree, RequirementType
from util import format_quantity

ureg = util.ureg

# Load the authors dictionary from the YAML file
with open("authors.yaml", "r", encoding="utf-8") as file:
    # Loader=yaml.SafeLoader is standard and secure
    AUTHORS = yaml.load(file, Loader=yaml.SafeLoader)


def require_player(allow_trapped: bool = False, allow_overfilled: bool = True):
    """
    Decorator/Check to ensure the command author is registered as a player in the local universe.
    Blocks execution and deploys the Size Reserve UI if the player is overfilled and allow_overfilled=False.
    """

    async def predicate(ctx: Context) -> bool:
        this_universe = universe.multiverse_instance.get_universe_from_id(ctx.channel.id)

        if this_universe is None:
            embed = discord.Embed(description="A universe doesn't exist here.", color=0xBEBEFE)
            await ctx.send(embed=embed, ephemeral=True)
            return False

        this_player_id = ctx.author.id
        grower = util.get_player_from_ctx(ctx)

        # AUTOMATIC TOUCH TREE LOGIC
        if not grower:
            new_player = player.Player(this_player_id, this_universe)
            this_universe.players.add(new_player)
            await ctx.send("You touch the root of tree of growth... You feel a newfound energy course through you. "
                           "You shall grow!", ephemeral=True)
            grower = new_player

        # --- EXTENSIONS AND VALIDATION RULES ---

        # 1. Size Reserve Check (Intercepts and deploys UI if overfilled)
        if not allow_overfilled:
            # Check if player has physically breached their current maximum allowed reserve
            if grower.size_reserve > grower.max_size_reserve:
                units = grower.units

                # Fetch the formatted 10-segment bar and UI rules from your utility module
                display_text, show_grow, show_resist = util.get_size_reserve_display(grower, units)

                # Build a warning embed mirroring your tactical profile/reserve interfaces
                embed = discord.Embed(
                    title="⚠️ GROWTH SPURT IMMINENT",
                    description=(
                        f"### The energy gathered inside of you is about to burst!\n"
                        f"You can either focus all your willpower on keeping that energy contained or "
                        f"let it expand your body in an explosive growth spurt!\n\n"
                        f"{display_text}\n\n"
                        f"⏰ *Your body will undergo an explosive auto-growth sequence "
                        f"if this pressure is not managed immediately.*"
                    ),
                    color=0xFF3333
                )

                # FIXED: Pass the required visibility flags straight into the view initialization!
                action_view = SizeReserveActions(grower, ctx, show_grow=show_grow, show_resist=show_resist)

                # Send the dashboard container. Ephemeral=True keeps channel clutter down during blocks
                msg = await ctx.send(embed=embed, view=action_view, ephemeral=False)
                action_view.message = msg

                # CRITICAL: Returning False cleanly terminates command execution before it reaches the command body
                return False

        # 2. Imprisonment / Busy State Check
        if not allow_trapped:
            if getattr(grower, 'is_trapped', False):
                embed = discord.Embed(description="❌ You are currently trapped and cannot perform this action!",
                                      color=0xFF3333)
                await ctx.send(embed=embed, ephemeral=False)
                return False

        return True

    return commands.check(predicate)


async def meal(ctx: Context, meal_type: str):
    # Prevent timeouts with deferring
    await ctx.defer()

    grower: player.Player = util.get_player_from_ctx(ctx)

    # Base amount based on mass
    amount = grower.get_mass() / 51 / 5

    # Store state before eating
    mass_before = grower.get_mass()
    height_before = grower.get_height()
    fat_ratio_before = grower.get_fat_ratio()
    units = grower.units

    # Check if the player has enough capacity for this specific food item weight
    if grower.can_eat(amount):
        # Generate the random food object using our new unified type-based system
        # This function handles cache hits, AI creation, and fallbacks automatically
        generated_food = util.create_food_by_type(
            meal_type=meal_type,
            size_kg=amount,
            tier=0
        )

        # Feed the generated meal macros to the grower
        grower.feed(
            proteins=generated_food.protein,
            carbohydrates=generated_food.size,
            fats=generated_food.fat
        )

        # Optional: If you want to log or append the item to the grower's inventory/stomach history
        # grower.add_item(generated_food)

        # Prepare the report using your function
        report = util.get_growth_report(
            mass_before, grower.get_mass(),
            height_before, grower.get_height(),
            fat_ratio_before, grower.get_fat_ratio(),
            units
        )

        # Flavor text combining the generated food details and the report
        message = (
            f"### {generated_food.emoji} {meal_type}: {generated_food.name}\n"
            f"You eat {generated_food.full_name_with_article} **Tier {generated_food.tier}**\n\n"
            f"{report}"
        )
    else:
        message = f"You are too full to enjoy your {meal_type.lower()}."

    await ctx.send(embed=discord.Embed(description=message, color=0xBEBEFE))


class InventoryPaginator(discord.ui.View):
    def __init__(
            self,
            idx_interaction: discord.Interaction,
            chunks: list,
            total_pages: int,
            embed_title: str = "🎒 Your Inventory",
            embed_footer: str = "Use /inventory use <number>, /inventory examine <number>, or /inventory delete "
                                "<number> "
    ):
        super().__init__(timeout=60.0)  # Buttons expire after 60 seconds of inactivity
        self.idx_interaction = idx_interaction
        self.chunks = chunks
        self.total_pages = total_pages
        self.current_page = 0

        # Store custom strings for embed generation
        self.embed_title = embed_title
        self.embed_footer = embed_footer

        # Update button states right away during initialization
        self.update_button_states()

    def update_button_states(self):
        """Disables navigation buttons if there is nowhere to go."""
        self.prev_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page == self.total_pages - 1

    def make_embed(self) -> discord.Embed:
        """Helper to construct the embed for the current page state."""
        chunk_text = "```xl\n" + "\n".join(self.chunks[self.current_page]) + "\n```"
        title = self.embed_title
        if self.total_pages > 1:
            title += f" (Page {self.current_page + 1}/{self.total_pages})"

        embed = discord.Embed(title=title, description=chunk_text, color=0x00FF00)
        embed.set_footer(text=self.embed_footer)
        return embed

    @discord.ui.button(label="◀ Previous", style=discord.ButtonStyle.secondary, row=0)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.idx_interaction.user:
            await interaction.response.send_message("This inventory belongs to someone else!", ephemeral=True)
            return

        self.current_page -= 1
        self.update_button_states()

        # Edit the original message with the updated embed and view state
        await interaction.response.edit_message(embed=self.make_embed(), view=self)

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.primary, row=0)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.idx_interaction.user:
            await interaction.response.send_message("This inventory belongs to someone else!", ephemeral=True)
            return

        self.current_page += 1
        self.update_button_states()

        # Edit the original message with the updated embed and view state
        await interaction.response.edit_message(embed=self.make_embed(), view=self)

    async def on_timeout(self):
        """Automatically disable all buttons when the interaction expires."""
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
        try:
            await self.idx_interaction.edit_original_response(view=self)
        except Exception:
            pass  # Suppress errors if message was already deleted


class CookMealModal(discord.ui.Modal, title="Cook a Meal"):
    def __init__(self, grower, unit_system: UnitSystem = UnitSystem.METRIC):
        super().__init__()
        self.player = grower
        self.unit_system = unit_system

        cook_progress = grower.talents.get("cook")
        self.cook_tier = cook_progress.tier if cook_progress else 0

        multiplier = 10 ** self.cook_tier if self.cook_tier > 0 else 1

        self.min_size_kg = grower.get_mass() / 2196
        self.max_size_kg = (grower.get_mass() / 6) * multiplier
        self.max_name_length = 45

        # Cost in troves (kg) per 1 kg of the meal's mass
        self.cost_per_kg = 1.0

        self.meal_name = discord.ui.TextInput(
            label="Meal Name",
            placeholder="Enter the name of your meal",
            max_length=45
        )
        self.meal_size = discord.ui.TextInput(
            label="Meal Size",
            placeholder="e.g., 2 kg, 500 g, 1.5 lbs",
            style=discord.TextStyle.short
        )

        self.add_item(self.meal_name)
        self.add_item(self.meal_size)

        if self.cook_tier > 0:
            self.use_talent_checkbox = discord.ui.Checkbox(
                custom_id="use_cook_talent",
                default=False
            )
            self.talent_label = discord.ui.Label(
                text=f"Use Cook Talent Tier {self.cook_tier}",
                description=f"Costs 1 stamina bar & {self.cost_per_kg} kg troves per kg of meal mass.",
                component=self.use_talent_checkbox
            )
            self.add_item(self.talent_label)
        else:
            self.use_talent_checkbox = None

    async def on_submit(self, interaction: discord.Interaction):
        try:
            meal_name_value = self.meal_name.value.strip().lower()

            articles = ["a", "an"]
            meal_name_value = ' '.join(meal_name_value.split()[1:]) if meal_name_value.split()[
                                                                           0] in articles else meal_name_value

            meal_name = meal_name_value.capitalize()
            size_kg = self.parse_meal_size(self.meal_size.value)
            display_name = meal_name.strip().capitalize()

            target_tier = 0
            use_talent = self.use_talent_checkbox.value if self.use_talent_checkbox else False

            total_cost_kg = size_kg * self.cost_per_kg if use_talent else 0.0
            if use_talent:
                if self.cook_tier <= 0:
                    raise ValueError("You do not have the Cook talent unlocked.")
                if self.player.stamina < self.player.workout_cost:
                    raise ValueError("You do not have enough stamina to use your Cook talent.")
                if self.player.troves < total_cost_kg:
                    await interaction.response.send_message(
                        f"You don't have enough troves! Required: "
                        f"**{util.format_quantity(total_cost_kg * ureg.kg, self.player.units)}**, "
                        f"available: **{util.format_quantity(self.player.troves * ureg.kg, self.player.units)}**.",
                        ephemeral=True
                    )
                    return

                target_tier = self.cook_tier

            cooking_effects = self.player.get_effects(EffectType.INSPIRED_COOKING)

            if cooking_effects:
                target_tier += sum(int(e.power) for e in cooking_effects)

            new_meal = util.create_food_by_name(display_name, size_kg, target_tier)
            new_meal.creator_id = self.player.id

            if use_talent:
                self.player.stamina -= self.player.workout_cost
                self.player.troves -= total_cost_kg

            self.player.remove_single_effect_by_type(effect.EffectType.INSPIRED_COOKING)

            self.player.add_item(new_meal)
            final_protein = new_meal.protein
            final_carbs = new_meal.size
            final_fat = new_meal.fat

            # Check if troves were spent for the talent
            cost_text = f"\nCost: **{util.format_quantity(total_cost_kg * ureg.kg, self.player.units)} kg** troves" \
                if use_talent and total_cost_kg > 0 else ""

            embed = discord.Embed(
                title=f"{new_meal.emoji} {new_meal.name}",
                description=f"You have cooked {new_meal.full_name_with_article} **Tier {new_meal.tier}** "
                            f"(Mass: {format_quantity(size_kg * ureg.kg, self.unit_system)}) and added it to "
                            f"your inventory!{cost_text}",
                color=0x00FF00
            )

            total_energy_j = (final_protein * 17_000_000) + (final_carbs * 17_000_000) + (final_fat * 37_000_000)

            embed.add_field(
                name="Nutrients & Energy",
                value=(
                    f"🥩 {format_quantity(final_protein * ureg.kg, self.unit_system)} | "
                    f"🍞 {format_quantity(final_carbs * ureg.kg, self.unit_system)} | "
                    f"🧈 {format_quantity(final_fat * ureg.kg, self.unit_system)} | "
                    f"⚡ {format_quantity(total_energy_j * ureg.joule, self.unit_system)}"
                ),
                inline=False
            )

            await interaction.response.send_message(embed=embed)

        except ValueError as e:
            await interaction.response.send_message(str(e), ephemeral=True)

    def parse_meal_size(self, input_size: str) -> float:
        input_size = input_size.strip()
        input_size = input_size.replace(',', '.')

        try:
            quantity = ureg(input_size).to("kg")
            value_kg = quantity.magnitude

            if value_kg <= 0:
                raise ValueError("Meal size must be greater than zero.")
            if value_kg < self.min_size_kg:
                raise ValueError(
                    f"Meal size cannot be smaller than {format_quantity(self.min_size_kg * ureg.kg, self.unit_system)}."
                )
            if value_kg > self.max_size_kg:
                raise ValueError(
                    f"Meal size cannot exceed {format_quantity(self.max_size_kg * ureg.kg, self.unit_system)}."
                )

            return value_kg

        except (pint.UndefinedUnitError, pint.DimensionalityError):
            raise ValueError("Invalid unit! Try something like '2 kg', '500 g', '1.5 lbs', '3 stones', etc.")


class UnitSelection(discord.ui.Select):
    def __init__(self):
        # The options must align perfectly with the UnitSystem Enum keys.
        options = [
            discord.SelectOption(
                label="Metric",
                value="METRIC",
                description="The logical precision of the Continent."
            ),
            discord.SelectOption(
                label="US Customary",
                value="US_CUSTOMARY",
                description="The charmingly complex ways of the Colonies."
            ),
            discord.SelectOption(
                label="Prussian",
                value="PRUSSIAN",
                description="The iron-clad standards of the Rhineland."
            ),
        ]
        super().__init__(
            placeholder="Choose your preferred unit system...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        grower = self.view.grower

        try:
            # 1
            unit_choice = player.UnitSystem[self.values[0]]
            grower.units = unit_choice

            # 2
            selected_option = next(opt for opt in self.options if opt.value == self.values[0])
            display_name = selected_option.label

            await interaction.response.send_message(
                f"✅ Unit system updated to **{display_name}**.",
                ephemeral=True
            )

            # Once the choice is made, we may disable the view to prevent clutter.
            self.view.stop()

        except KeyError as e:
            # Should the stars misalign, we inform the user with due gravity.
            await interaction.response.send_message(
                f"A most unusual error occurred: {e}", ephemeral=True
            )


class UnitSelectionView(discord.ui.View):
    def __init__(self, grower):
        super().__init__(timeout=60)
        self.grower = grower
        self.message = None
        # Adding the select menu to the view.
        self.add_item(UnitSelection())

    async def on_timeout(self):
        if self.message:
            for thing in self.children:
                thing.disabled = True
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass


class ConfirmDeleteView(discord.ui.View):
    """A confirmation UI before deleting an item."""

    def __init__(self, interaction, grower, thing, index):
        super().__init__()
        self.interaction = interaction
        self.player = grower
        self.item = thing
        self.index = index

    @discord.ui.button(label="Yes, delete", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handles item deletion upon confirmation."""
        self.player.remove_item_by_index(self.index)
        embed = discord.Embed(description=f"Deleted **{self.item.name}** from your inventory.", color=0xFF0000)
        await interaction.response.edit_message(embed=embed, view=None)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Cancels the deletion process."""
        embed = discord.Embed(description="Deletion cancelled.", color=0x00FF00)
        await interaction.response.edit_message(embed=embed, view=None)


def morph_player_body(grower, new_preset: player.BodyType):
    """
    Performs a full body transformation following the Law of Mass Conservation.
    Maintains global muscle and fat ratios from the old body.
    """
    # --- 1. COLLECT GLOBAL METABOLIC DATA ---
    global_metabolism = {
        'protein': 0.0, 'p_qual': [],
        'carbs': 0.0, 'c_qual': [],
        'fat_c': 0.0, 'f_qual': [],
        'chyme': 0.0
    }

    old_torsos = [p for p in grower.body.values() if isinstance(p, player.Torso)]
    for t in old_torsos:
        global_metabolism['protein'] += getattr(t, 'protein_content', 0.0)
        global_metabolism['carbs'] += getattr(t, 'carbohydrates_content', 0.0)
        global_metabolism['fat_c'] += getattr(t, 'fat_content', 0.0)
        global_metabolism['chyme'] += getattr(t, 'metabolic_chyme', 0.0)
        global_metabolism['p_qual'].append((getattr(t, 'protein_quality', 0.0), getattr(t, 'protein_content', 0.0)))
        global_metabolism['c_qual'].append((getattr(t, 'carbo_quality', 0.0), getattr(t, 'carbohydrates_content', 0.0)))
        global_metabolism['f_qual'].append((getattr(t, 'fat_quality', 0.0), getattr(t, 'fat_content', 0.0)))

    def get_avg_quality(qual_list):
        total_m = sum(m for q, m in qual_list)
        return sum(q * m for q, m in qual_list) / total_m if total_m > 0 else 0.0

    avg_p_qual = get_avg_quality(global_metabolism['p_qual'])
    avg_c_qual = get_avg_quality(global_metabolism['c_qual'])
    avg_f_qual = get_avg_quality(global_metabolism['f_qual'])

    # --- 2. GATHER TOTAL POOLS BEFORE MORPH ---
    old_base_mass = sum(p.mass for p in grower.body.values())
    old_muscle_mass = sum(p.muscle_mass for p in grower.body.values())
    old_fat_mass = sum(p.fat_mass for p in grower.body.values())

    # English: Total mass must remain identical
    total_mass_before = old_base_mass + old_muscle_mass + old_fat_mass

    # --- 3. INITIALIZE NEW BODY ---
    new_body_dict = player.get_body_preset(new_preset, owner=grower)

    # Scale new base masses to match the old TOTAL base mass
    current_new_base_sum = sum(p.mass for p in new_body_dict.values())
    if current_new_base_sum > 0:
        base_scaling = old_base_mass / current_new_base_sum
        for part in new_body_dict.values():
            part.mass *= base_scaling

    # --- 4. DISTRIBUTE METABOLISM ---
    new_torsos = [p for p in new_body_dict.values() if isinstance(p, player.Torso)]
    if new_torsos:
        num_t = len(new_torsos)
        for t in new_torsos:
            t.protein_content = global_metabolism['protein'] / num_t
            t.protein_quality = avg_p_qual
            t.carbohydrates_content = global_metabolism['carbs'] / num_t
            t.carbo_quality = avg_c_qual
            t.fat_content = global_metabolism['fat_c'] / num_t
            t.fat_quality = avg_f_qual
            t.metabolic_chyme = global_metabolism['chyme'] / num_t

    # --- 5. PURE REDISTRIBUTION (No Minimums) ---
    # Calculate total potential for muscle/fat based on new part set points
    total_set_muscle = sum(part.mass * part.set_point_frac[0] for part in new_body_dict.values())
    total_set_fat = sum(part.mass * part.set_point_frac[1] for part in new_body_dict.values())

    for part in new_body_dict.values():
        # Muscle distribution
        if total_set_muscle > 0:
            m_ratio = (part.mass * part.set_point_frac[0]) / total_set_muscle
            part.muscle_mass = old_muscle_mass * m_ratio
        else:
            part.muscle_mass = 0.0

        # Fat distribution
        if total_set_fat > 0:
            f_ratio = (part.mass * part.set_point_frac[1]) / total_set_fat
            part.fat_mass = old_fat_mass * f_ratio
        else:
            part.fat_mass = 0.0

    # --- 6. FINAL INTEGRITY CHECK ---
    total_mass_after = sum(p.total_mass for p in new_body_dict.values())

    # Floating point error correction
    if abs(total_mass_after - total_mass_before) > 0.0001:
        correction = total_mass_before / total_mass_after
        for part in new_body_dict.values():
            part.mass *= correction
            part.muscle_mass *= correction
            part.fat_mass *= correction

    grower.body = new_body_dict
    grower.body_type = new_preset


class RuleEditModal(discord.ui.Modal):
    def __init__(self, rule_name, current_value, universe):
        super().__init__(title=f"Edit Rule: {rule_name}")
        self.rule_name = rule_name
        self.universe = universe

        # Text input field for the new value
        self.new_value_input = discord.ui.TextInput(
            label="New Value",
            default=str(current_value),
            placeholder="Enter the new value here...",
            required=True
        )
        self.add_item(self.new_value_input)

    async def on_submit(self, interaction: discord.Interaction):
        # Use the update_rule method defined in Universe class
        success = self.universe.update_rule(self.rule_name, self.new_value_input.value)

        if success:
            new_val = self.universe.get_rule(self.rule_name)
            await interaction.response.send_message(
                f"✅ Rule **{self.rule_name}** updated to **{new_val}**!",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"❌ Failed to update **{self.rule_name}**. Check the data type!",
                ephemeral=True
            )


class AdminRulesView(discord.ui.View):
    def __init__(self, universe):
        super().__init__(timeout=None)
        self.universe = universe
        self.selected_rule = None
        self.update_select_menu()

    def update_select_menu(self):
        """Creates or updates the dropdown menu with the list of rules."""
        self.clear_items()

        options = [
            discord.SelectOption(label=name, description=f"Current: {val}")
            for name, val in self.universe.rules.items()
        ]

        select = discord.ui.Select(
            placeholder="Select a rule to modify...",
            options=options,
            custom_id="rule_select"
        )
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        if 'values' in interaction.data:
            self.selected_rule = interaction.data['values'][0]
        current_val = self.universe.get_rule(self.selected_rule)

        # Create a fresh view for the update interface
        new_view = discord.ui.View(timeout=None)

        # Add the original dropdown back to allow switching rules
        options = [
            discord.SelectOption(label=name, description=f"Current: {val}")
            for name, val in self.universe.rules.items()
        ]
        select = discord.ui.Select(placeholder="Select a rule...", options=options)
        select.callback = self.select_callback
        new_view.add_item(select)

        # Logic for Toggle (Boolean) vs Edit (Numeric/String)
        if isinstance(current_val, bool):
            button_label = "Switch to False" if current_val else "Switch to True"
            btn = discord.ui.Button(label=button_label, style=discord.ButtonStyle.primary)

            async def toggle_callback(it: discord.Interaction):
                self.universe.update_rule(self.selected_rule, not current_val)
                await it.response.send_message(f"✅ {self.selected_rule} toggled!", ephemeral=True)

            btn.callback = toggle_callback
            new_view.add_item(btn)
        else:
            # Check if it is an Enum
            if isinstance(current_val, Enum):
                # Add a button for each Enum member
                for member in type(current_val):
                    btn = discord.ui.Button(
                        label=member.name.replace("_", " ").title(),
                        style=discord.ButtonStyle.success if member == current_val else discord.ButtonStyle.secondary
                    )

                    async def enum_callback(it: discord.Interaction, m=member):
                        self.universe.update_rule(self.selected_rule, m)
                        # Refresh the view to show the new state
                        await self.select_callback(it)

                    btn.callback = enum_callback
                    new_view.add_item(btn)

            # Default fallback for numeric/string (Modal)
            else:
                btn = discord.ui.Button(label="Edit Value", style=discord.ButtonStyle.secondary)

                async def edit_callback(it: discord.Interaction):
                    await it.response.send_modal(RuleEditModal(self.selected_rule, current_val, self.universe))

                btn.callback = edit_callback
                new_view.add_item(btn)

        await interaction.response.edit_message(
            content=f"### Editing Rule: `{self.selected_rule}`\nCurrent value: **{current_val}**",
            view=new_view
        )


class BodyRewardView(discord.ui.View):
    def __init__(self, grower, options_text, timeout=None):
        super().__init__(timeout=timeout)
        self.grower = grower
        # options_text is a dictionary with descriptions for each button

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensures only the target grower can interact with these buttons."""
        if interaction.user.id != self.grower.id:
            await interaction.response.send_message("❌ This is not your reward to claim!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Cardio", emoji="🏃", style=discord.ButtonStyle.primary)
    async def cardio_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        result_msg = await process_workout(self.grower, "running", "cardio", True, True)
        units = self.grower.units
        stamina_section = util.get_stamina_display(self.grower, units)
        embed = discord.Embed(title="Workout Report", description=result_msg, color=0x3498db)
        embed.add_field(name="Energy Spent", value=util.format_quantity(self.grower.workout_cost * ureg.joule, units))
        embed.add_field(name="Current Condition", value=stamina_section, inline=False)
        await interaction.response.send_message(embed=embed)
        self.stop()

    @discord.ui.button(label="Rest", emoji="💪", style=discord.ButtonStyle.secondary)
    async def rest_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Unpack the tuple returned by the modified process_workout function
        raw_result, growth_amount = await process_workout(self.grower, "full_body", "strength", free_stamina=True,
                                                          free_protein=True)

        units = self.grower.units

        # Format the raw growth number safely using your utility function
        gained_mass_text = util.format_quantity(growth_amount * ureg.kilogram, units)

        stamina_section = util.get_stamina_display(self.grower, units)
        description = (
            f"💤 Your muscles grew by **{gained_mass_text}**."
        )

        embed = discord.Embed(
            title="💤 Muscle Recovery",
            description=description,
            color=0x9b59b6
        )
        embed.add_field(name="Energy Spent", value=util.format_quantity(0 * ureg.joule, units))
        embed.add_field(name="Current Condition", value=stamina_section, inline=False)

        await interaction.response.send_message(embed=embed)
        self.stop()

    @discord.ui.button(label="Dessert", emoji="🍨", style=discord.ButtonStyle.success)
    async def treat_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Determine the tier based on the grower's average stomach content quality
        raw_tier = self.grower.stomach_content_quality_avg + 1.0
        new_tier = int(math.floor(raw_tier))
        if new_tier < 1:
            new_tier = 1

        # Base size calculated from the grower's stomach capacity
        size = self.grower.stomach_capacity / 2
        new_meal = util.create_food_by_type(
            meal_type="dessert",
            size_kg=size,
            tier=new_tier
        )

        # Feed or add the item to the grower's inventory/stomach history
        self.grower.add_item(new_meal)

        # Dynamic flavor text using the new article properties from your item class
        description = (
            f"You get {new_meal.full_name_with_article}!\n"
            f"This treat is much better than what you usually eat!\n"
            f"This dessert's quality reaches **Tier {new_meal.tier}**."
        )

        embed = discord.Embed(
            title=f"{new_meal.full_name}",
            description=description,
            color=0x2ecc71
        )

        await interaction.response.send_message(embed=embed)
        self.stop()


class ChainGrowthView(discord.ui.View):
    """
    English: The "Push Your Luck" interactive chain view for the Bigger mini-game.
    Dynamically escalates labels and rolls checks until the player fails or stops.
    """

    def __init__(self, this_player, ctx: Context, original_gain: float, base_chance: float, step: int = 1,
                 boost_power: float = 0.0):
        super().__init__(timeout=30.0)
        self.this_player = this_player
        self.ctx = ctx
        self.original_gain = original_gain
        self.current_chance = base_chance
        self.step = step
        self.boost_power = boost_power

        # Generate progressively more intense labels based on the current step
        labels = ["Bigger", "Bigger!", "BIGGER!", "🔥 EVEN BIGGER! 🔥", "⚡ UNLIMITED POWAAAAHHHH! ⚡"]
        current_label = labels[min(step - 1, len(labels) - 1)]

        # Add the dynamic button
        btn = discord.ui.Button(label=current_label, style=discord.ButtonStyle.primary, custom_id="chain_click")
        btn.callback = self.click_callback
        self.add_item(btn)

    async def click_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.this_player.id:
            return await interaction.response.send_message("This growth spark is not yours!", ephemeral=True)

        # 1. START DEBUG LOGGING FOR THE CHAIN STEP
        print(f"\n[DEBUG CHAIN STEP START] Player: {self.this_player.id} | Current Step: {self.step}")
        print(f"  -> Incoming Base Gain from previous explosion: {self.original_gain:.4f}")
        print(f"  -> Incoming Chain Chance from previous step: {self.current_chance * 100:.2f}%")

        self.stop()
        for item in self.children:
            if hasattr(item, "disabled"):
                item.disabled = True
        await interaction.response.edit_message(view=self)

        # 2. EVALUATE DICE ROLL
        roll = random.random()
        effective_chance = 1.0 if self.step == 1 else self.current_chance
        print(f"  -> Step {self.step} Evaluated Success Chance: {effective_chance * 100:.2f}%")
        print(f"  -> Dice Roll: {roll * 100:.2f}%")
        if roll <= effective_chance:
            # --- SUCCESS: CHAIN CONTINUES ---
            units = self.this_player.units

            # A. CAPTURE BEFORE STATE (Snapshot before applying the chain bonus)
            old_mass = self.this_player.get_mass()
            old_height = self.this_player.get_height()
            old_fat_ratio = self.this_player.get_fat_ratio()

            # B. RUN EXECUTION (Grants bonus mass and modifies player attributes)
            bonus_gained = self.this_player.apply_chain_growth_bonus(self.original_gain, self.step)

            # C. CAPTURE AFTER STATE
            new_mass = self.this_player.get_mass()
            new_height = self.this_player.get_height()
            new_fat_ratio = self.this_player.get_fat_ratio()

            # Decay the chance slightly for the next step to keep the math tight and bounded
            next_chance = min(0.99, 1 - math.exp(-self.boost_power / 6.0))
            print(f"  -> boost_power used for next_chance: {self.boost_power}")
            next_step = self.step + 1

            print(f"  -> [OUTCOME: SUCCESS] Rolling momentum kept! Injecting bonus mass: {bonus_gained:.4f}")
            print(f"  -> Next Step Chance will decay to: {next_chance * 100:.2f}% (Step {next_step})")

            # D. GENERATE DETAILED REPORT FROM UTIL
            report_text = util.get_growth_report(
                old_mass, new_mass,
                old_height, new_height,
                old_fat_ratio, new_fat_ratio,
                units
            )

            # E. DYNAMICALLY FORMAT TOTALS FOR THE SUB-HEADER
            new_mass_str = util.format_quantity(new_mass * ureg.kg, units)
            new_height_str = util.format_quantity(new_height * ureg.m, units)

            # F. SEND THE DETAILED MOMENTUM EMBED (Mirrors the original growth style)
            embed = discord.Embed(
                title=f"⚡ Momentum Chain x{self.step}!",
                description=(
                    f"### ✨ **SUCCESS!** <@{self.this_player.id}> has surged even further!\n"
                    f"Current dimensions: `{new_mass_str}` | `{new_height_str}`\n\n"
                    f"{report_text}"
                ),
                color=0x55FF55
            )

            # Spawn the next view in the chain!
            next_view = ChainGrowthView(self.this_player, self.ctx, self.original_gain, next_chance, next_step,
                                        self.boost_power)
            msg = await self.ctx.send(embed=embed, view=next_view)
            next_view.message = msg
        else:
            # --- FAILURE: THE CHAIN SNAP ---
            print(f"  -> [OUTCOME: FAILURE] The momentum stabilizes. Chain snapped at Step {self.step}.")

            embed = discord.Embed(
                description="💨 The growth spark fades. Your size stabilizes at last.",
                color=0xBEBEFE
            )
            await self.ctx.send(embed=embed)

        print(f"[DEBUG CHAIN STEP END] Step {self.step} resolution complete.\n")


class SizeReserveActions(discord.ui.View):
    """
    English: Gameplay UI View. Handles user interaction and execution flows.
    Asks player.Player to modify state based on button clicks or timeout panic.
    """

    def __init__(self, this_player: player.Player, ctx: Context, show_grow: bool, show_resist: bool,
                 timeout: float = 60.0):
        super().__init__(timeout=timeout)
        self.this_player = this_player
        self.ctx = ctx
        self.has_responded = False
        self.message = None  # To be injected right after sending

        if show_grow:
            grow_button = discord.ui.Button(label="Grow", style=discord.ButtonStyle.success, custom_id="trigger_growth")
            grow_button.callback = self.grow_callback
            self.add_item(grow_button)

        if show_resist:
            resist_button = discord.ui.Button(label="Resist Growth", style=discord.ButtonStyle.danger,
                                              custom_id="resist_growth")
            resist_button.callback = self.resist_callback
            self.add_item(resist_button)

            # Start real-time gameplay pressure trigger
            asyncio.create_task(self.start_overflow_timer())

    async def _handle_post_growth_gameplay(self, original_gain=None, chain_chance=None, forced_before_stats=None,
                                           boost_power=0.0):

        """
        Helper method to process the growth results from player.py,
        display exact transformation reports from util.py, and trigger the chain minigame.
        """
        units = self.this_player.units

        # 1. CAPTURE BEFORE STATE (Use forced stats if coming from a failed resistance)
        if forced_before_stats is not None:
            old_mass, old_height, old_fat_ratio = forced_before_stats
        else:
            old_mass = self.this_player.get_mass()
            old_height = self.this_player.get_height()
            old_fat_ratio = self.this_player.get_fat_ratio()

        if original_gain is None or chain_chance is None:
            print("  -> Arguments are None! Triggering raw player.execute_growth()...")
            original_gain, chain_chance = self.this_player.execute_growth()
            print(f"  -> Post-execution fetch results: gain={original_gain}, chance={chain_chance}")

        # 3. CAPTURE AFTER STATE
        new_mass = self.this_player.get_mass()
        new_height = self.this_player.get_height()
        new_fat_ratio = self.this_player.get_fat_ratio()

        # 4. GENERATE DETAILED REPORT FROM UTIL
        report_text = util.get_growth_report(
            old_mass, new_mass,
            old_height, new_height,
            old_fat_ratio, new_fat_ratio,
            units
        )

        # 5. DYNAMICALLY FORMAT TOTALS FOR THE SUB-HEADER
        new_mass_str = util.format_quantity(new_mass * ureg.kg, units)
        new_height_str = util.format_quantity(new_height * ureg.m, units)

        # 6. SEND THE MAIN GROWTH SUMMARY EMBED
        growth_embed = discord.Embed(
            title="📈 Growth Spurt!",
            description=(
                f"### <@{self.this_player.id}> has surged in size!\n"
                f"Current dimensions: `{new_mass_str}` | `{new_height_str}`\n\n"
                f"{report_text}"  # Injected cleanly with its own custom lines and emojis
            ),
            color=0xBEBEFE
        )
        await self.ctx.send(embed=growth_embed)

        # 7. TRIGGER CHAIN MINIGAME IF ELIGIBLE (Bigger buttons flow)
        print(f"  -> Checking if minigame triggers: {chain_chance} > 0.0 ?")
        if chain_chance > 0.0:
            print("  -> [UI OUTCOME] SUCCESS! Deploying ChainGrowthView with 'Bigger!' button.")
            embed = discord.Embed(
                title="⚡ The momentum of growth!",
                description="Your body doesn't want to stop growing just yet!",
                color=0xFFBB00
            )
            print(f"  -> boost_power being passed to ChainGrowthView: {boost_power}")
            chain_view = ChainGrowthView(self.this_player, self.ctx, original_gain, chain_chance, step=1,
                                         boost_power=boost_power)

            msg = await self.ctx.send(embed=embed, view=chain_view)
            chain_view.message = msg
        else:
            print("  -> [UI OUTCOME] SKIPPED. No minigame view attached.")

    async def start_overflow_timer(self):
        await asyncio.sleep(60.0)
        if not self.has_responded:
            self.has_responded = True
            self.disable_all_items()

            if self.message:
                try:
                    await self.message.edit(view=self)
                except discord.HTTPException:
                    pass

            await self.ctx.send(
                f"⚠️ <@{self.this_player.id}>, you failed to resist the pressure! You begin growing violently..."
            )

            # CLEAN & DRY: Just invoke the single handler
            await self._handle_post_growth_gameplay()

    async def grow_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.this_player.id:
            return await interaction.response.send_message("This is not your reserve!", ephemeral=True)
        if self.has_responded:
            return

        self.has_responded = True
        self.disable_all_items()
        await interaction.response.edit_message(view=self)

        # We send only the initial atmospheric text via ephemeral followup
        await interaction.followup.send(
            "You let go of all restraint and allow the energy to expand your form...",
            ephemeral=False
        )
        # The main public announcement with math details is handled here
        await self._handle_post_growth_gameplay()

    async def resist_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.this_player.id:
            return await interaction.response.send_message("This is not your reserve!", ephemeral=True)
        if self.has_responded:
            return

        self.has_responded = True
        self.disable_all_items()
        await interaction.response.edit_message(view=self)

        pre_mass = self.this_player.get_mass()
        pre_height = self.this_player.get_height()
        pre_fat = self.this_player.get_fat_ratio()

        # Execute logic (this will trigger growth internally on failure)
        success, original_gain, chain_chance, boost_power = self.this_player.execute_resistance()

        if success:
            await interaction.followup.send(
                "You grit your teeth and manage to hold back your growth... For now.",
                ephemeral=False
            )
        else:
            await interaction.followup.send(
                "💥 You try to hold back for a little longer, but the pressure is too much! Your body starts rapidly "
                "expanding!",
                ephemeral=False
            )
            await self._handle_post_growth_gameplay(
                original_gain=original_gain,
                chain_chance=chain_chance,
                forced_before_stats=(pre_mass, pre_height, pre_fat),
                boost_power=boost_power
            )

    def disable_all_items(self):
        """
        Disables all buttons in this view to prevent double-clicks
        and stops the internal listener.
        """
        for item in self.children:
            if hasattr(item, "disabled"):
                item.disabled = True
        self.stop()


async def execute_event(ctx: commands.Context, event_type: str):
    """
    Core engine to load, filter, and trigger events from YAML with debug logging and scoring fallback.
    """
    if not os.path.exists("events.yaml"):
        print(f"DEBUG: File 'events.yaml' not found.")
        await ctx.send("The book of fate (events.yaml) is missing!", ephemeral=True)
        return

    try:
        with open("events.yaml", "r", encoding="utf-8") as f:
            all_events = yaml.safe_load(f) or {}
    except Exception as e:
        print(f"DEBUG: YAML Parse Error: {e}")
        await ctx.send(f"Error reading fate: {e}", ephemeral=True)
        return

    # 1. PREPARE PLAYER METRICS
    grower = util.get_player_from_ctx(ctx)
    if grower.workout_cost > grower.stamina:
        await ctx.send("You don't have enough stamina!", ephemeral=True)
        return

    player_base_mass = grower.get_base_mass()
    p_fitness = grower.fitness
    p_muscle = grower.get_muscle_mass()
    p_fat = grower.get_fat_mass()
    total_mass = player_base_mass if player_base_mass > 0 else 1.0
    p_fitness_pct = grower.fitness_ratio
    p_muscle_pct = (p_muscle / total_mass)
    p_fat_pct = grower.get_fat_ratio()

    scored_events = []

    for ev_id, ev_data in all_events.items():
        ev_type = ev_data.get("event_type")
        if ev_type != event_type and not (event_type == "work" and ev_type == "work"):
            if ev_type != event_type:
                continue

        reqs = ev_data.get("requirements") or {}
        score = 0
        is_strictly_valid = True

        # --- BODY WHITELIST & BLACKLIST FILTERING ---
        body_whitelist = reqs.get("body_whitelist") or ev_data.get("body_whitelist")
        if body_whitelist:
            if isinstance(body_whitelist, str):
                body_whitelist = [body_whitelist]
            if not any(str(grower.body_type).lower() == str(allowed).lower() for allowed in body_whitelist):
                is_strictly_valid = False
                score -= 50
            else:
                score += 1

        body_blacklist = reqs.get("body_blacklist") or ev_data.get("body_blacklist")
        if body_blacklist:
            if isinstance(body_blacklist, str):
                body_blacklist = [body_blacklist]
            if any(str(grower.body_type).lower() == str(forbidden).lower() for forbidden in body_blacklist):
                is_strictly_valid = False
                score -= 100
            else:
                score += 1
        # -------------------------------------------

        # Min size check (gdy gracz jest za mały)
        if "min_size" in reqs:
            min_val = reqs["min_size"]
            if player_base_mass < min_val:
                is_strictly_valid = False
                # Stosunek limitu do masy gracza (np. 2.0 oznacza, że limit jest dwa razy większy)
                ratio = min_val / max(player_base_mass, 1e-9)
                # log2(2.0) = 1.0, więc dwukrotne niedomiar daje -1 punkt (minus bo to kara)
                penalty = math.log2(ratio) if ratio > 1 else 0
                score -= penalty
            else:
                score += 50

        # Max size check (gdy gracz przekracza limit)
        if "max_size" in reqs:
            max_val = reqs["max_size"]
            if player_base_mass > max_val:
                is_strictly_valid = False
                # Stosunek masy gracza do limitu (np. 2.0 oznacza, że gracz jest dwa razy większy niż limit)
                ratio = player_base_mass / max(max_val, 1e-9)
                # log2(2.0) = 1.0, więc dwukrotne przekroczenie daje dokładnie -1 punkt karze
                penalty = math.log2(ratio) if ratio > 1 else 0
                score -= penalty
            else:
                score += 50

            # 1. Fitness
            if "min_fitness_pct" in reqs:
                if p_fitness_pct < reqs["min_fitness_pct"]:
                    is_strictly_valid = False
                else:
                    score += 1
            if "max_fitness_pct" in reqs:
                if p_fitness_pct > reqs["max_fitness_pct"]:
                    is_strictly_valid = False
                else:
                    score += 1
            if "min_fitness" in reqs:
                if p_fitness < reqs["min_fitness"]:
                    is_strictly_valid = False
                else:
                    score += 1
            if "max_fitness" in reqs:
                if p_fitness > reqs["max_fitness"]:
                    is_strictly_valid = False
                else:
                    score += 1

            # 2. Muscle
            if "min_muscle_pct" in reqs:
                if p_muscle_pct < reqs["min_muscle_pct"]:
                    is_strictly_valid = False
                else:
                    score += 1
            if "max_muscle_pct" in reqs:
                if p_muscle_pct > reqs["max_muscle_pct"]:
                    is_strictly_valid = False
                else:
                    score += 1
            if "min_muscle" in reqs:
                if p_muscle < reqs["min_muscle"]:
                    is_strictly_valid = False
                else:
                    score += 1
            if "max_muscle" in reqs:
                if p_muscle > reqs["max_muscle"]:
                    is_strictly_valid = False
                else:
                    score += 1

            # 3. Fat
            if "min_fat_pct" in reqs:
                if p_fat_pct < reqs["min_fat_pct"]:
                    is_strictly_valid = False
                else:
                    score += 1
            if "max_fat_pct" in reqs:
                if p_fat_pct > reqs["max_fat_pct"]:
                    is_strictly_valid = False
                else:
                    score += 1
            if "min_fat" in reqs:
                if p_fat < reqs["min_fat"]:
                    is_strictly_valid = False
                else:
                    score += 1
            if "max_fat" in reqs:
                if p_fat > reqs["max_fat"]:
                    is_strictly_valid = False
                else:
                    score += 1

        scored_events.append({
            "data": ev_data,
            "score": score,
            "strict": is_strictly_valid
        })

    # 2. FALLBACK RANKING MECHANISM
    if not scored_events:
        await ctx.send("Nothing happens.")
        return

    strict_matches = [item for item in scored_events if item["strict"]]

    if strict_matches:
        max_score = max(item["score"] for item in strict_matches)
        best_candidates = [item["data"] for item in strict_matches if item["score"] == max_score]
    else:
        max_score = max(item["score"] for item in scored_events)
        best_candidates = [item["data"] for item in scored_events if item["score"] == max_score]

    # 3. EXECUTION
    grower.stamina -= grower.workout_cost
    selected = random.choice(best_candidates)

    # 4. APPLY REWARD
    description = selected.get("description", "...")
    view = None

    if "reward" in selected:
        reward_data = selected["reward"]

        if isinstance(reward_data, dict):
            r_type = reward_data.get("type", "").lower().strip()
        else:
            r_type = str(reward_data).lower().strip()

        if r_type in ["troves", "work"]:
            if isinstance(reward_data, dict) and "amount" in reward_data:
                calculated_reward = float(reward_data["amount"])
            else:
                calculated_reward = grower.get_muscle_mass() * 0.01

            fortune_effects = grower.get_effects(EffectType.GOOD_FORTUNE)
            if fortune_effects:
                fortune_bonus = sum(e.power for e in fortune_effects)
                calculated_reward *= (1.0 + fortune_bonus)

            grower.troves += calculated_reward
            reward_display = f"{util.format_quantity(calculated_reward * ureg.kg, grower.units)}"
            description = description.format(troves=reward_display, work=reward_display)

        elif r_type == "body":
            options_txt = "\n\n"
            if selected.get("option1", "") == "":
                options_txt += "🏃 You can either take advantage of the adrenaline coursing through you and go on a " \
                               "run for some cardio.\n "
            else:
                options_txt += f"🏃 {selected['option1']}\n"

            if selected.get("option2", "") == "":
                options_txt += "💪 Or perhaps all the excitement was enough for one day and your already tired " \
                               "muscles could use a rest.\n "
            else:
                options_txt += f"💪 {selected['option2']}\n"

            if selected.get("option3", "") == "":
                options_txt += "🍨 But that ice cream does sound pretty tasty.\n"
            else:
                options_txt += f"🍨 {selected['option3']}\n"

            description += options_txt
            view = BodyRewardView(grower, selected)

        elif r_type in ["breakfast", "lunch", "dinner", "dessert"]:
            amount = grower.get_muscle_mass() / 9
            current_tier = int(math.floor(grower.stomach_content_quality_avg + 1))

            reward_food = util.create_food_by_type(
                meal_type=r_type,
                size_kg=amount,
                tier=current_tier
            )
            grower.add_item(reward_food)
            meal_txt = (
                f"\n\n### 🍽️ Reward: {reward_food.emoji} {reward_food.name}\n"
                f"You received **{reward_food.full_name_with_article}** "
                f"**Tier {reward_food.tier}** and added it to your inventory!"
            )
            description += meal_txt

        elif r_type == "instant_food":
            meal_name = reward_data.get("name")
            fill_stomach = reward_data.get("fill_stomach", False)
            if fill_stomach:
                stomach_free_space = grower.stomach_capacity - grower.stomach_content
                amount = max(0.001, stomach_free_space)
            elif "size" in reward_data:
                amount = float(reward_data["size"])
            else:
                amount = grower.get_muscle_mass() / 9

            current_tier = int(math.floor(grower.stomach_content_quality_avg + 1))
            reward_food = util.create_food_by_name(
                meal_name=meal_name,
                size_kg=amount,
                tier=current_tier
            )
            mass_before = grower.get_mass()
            height_before = grower.get_height()
            grower.feed(
                proteins=reward_food.protein,
                carbohydrates=reward_food.size,
                fats=reward_food.fat
            )
            mass_after = grower.get_mass()
            height_after = grower.get_height()
            delta_mass = mass_after - mass_before
            delta_height = height_after - height_before
            food_weight_str = util.format_quantity(reward_food.size * ureg.kg, grower.units, show_alternative=False)
            dinner_display = f"{food_weight_str} of {reward_food.name}"
            weight_display = f"{util.format_quantity(delta_mass * ureg.kg, grower.units, show_alternative=False)}"
            height_display = f"{util.format_quantity(delta_height * ureg.cm, grower.units, show_alternative=False)}"
            description = description.format(
                dinner=dinner_display,
                d_weight=weight_display,
                size=height_display
            )

        elif r_type == "custom_food":
            forced_name = reward_data.get("name", "Pizza")
            if isinstance(reward_data, dict) and "size" in reward_data:
                amount = float(reward_data["size"])
            else:
                amount = grower.get_muscle_mass() / 9

            current_tier = int(math.floor(grower.stomach_content_quality_avg + 1))
            reward_food = util.create_food_by_name(
                meal_name=forced_name,
                size_kg=amount,
                tier=current_tier,
            )
            grower.add_item(reward_food)
            meal_txt = (
                f"\n\n### 🍽️ Reward: {reward_food.emoji} {reward_food.name}\n"
                f"You received **{reward_food.full_name_with_article}** "
                f"**Tier {reward_food.tier}** and added it to your inventory!"
            )
            description += meal_txt

        elif r_type == "buff":
            if isinstance(reward_data, dict):
                available_buffs = [
                    EffectType.ENERGETIC,
                    EffectType.RAVENOUS,
                    EffectType.INSPIRED_COOKING,
                    EffectType.GOOD_FORTUNE,
                    EffectType.RESTLESS
                ]
                chosen_effect_type = random.choice(available_buffs)
                new_buff = Effect(effect_type=chosen_effect_type, creator_id=None)
                grower.add_effect(new_buff)
                buff_txt = (
                    f"\n\n### ✨ Reward: Status Buff\n"
                    f"You received a {new_buff.emoji} **{chosen_effect_type.display_name}** effect!"
                )
                description += buff_txt

    # 5. DISPATCH RESPONSE
    embed = discord.Embed(
        title=selected.get("title", "An Event Occurs!"),
        description=description,
        color=discord.Color.gold()
    )

    if "pages" in selected:
        embed.description = selected["pages"][0]

    # --- ADDING THE AUTHOR WITH AVATAR ---
    author_data = selected.get("author")
    if author_data:
        if isinstance(author_data, dict):
            author_name = author_data.get("name")
        elif isinstance(author_data, str):
            author_name = author_data
        else:
            author_name = None

        if author_name:
            author_id = AUTHORS.get(author_name.lower())
            author_avatar_url = None

            if author_id:
                author_user = ctx.bot.get_user(int(author_id))
                if not author_user:
                    try:
                        author_user = await ctx.bot.fetch_user(int(author_id))
                    except discord.NotFound:
                        author_user = None

                if author_user and author_user.avatar:
                    author_avatar_url = author_user.avatar.url

            embed.set_author(name=f"✨ {author_name}", icon_url=author_avatar_url)

    stamina_display = util.get_stamina_display(grower, grower.units)
    embed.add_field(name="\u200b", value=stamina_display, inline=False)

    await ctx.send(embed=embed, view=view)


async def process_workout(this_player: player.Player, exercise: str, workout_type: str = "strength",
                          free_stamina: bool = False, free_protein: bool = False) -> str | tuple[str, float | Any]:
    """
    Executes the training logic. Returns a formatted string with the result message
    or raises a ValueError if requirements are not met.
    """
    BODY_PART_EXERCISES = {
        "bench_press": {"part": "torso", "name": "Bench Press", "emoji": "🏋️", "req": "arm"},
        "bicep_curls": {"part": "arm", "name": "Bicep Curls", "emoji": "💪", "req": "arm"},
        "squats": {"part": "leg", "name": "Deep Squats", "emoji": "🦵", "req": "leg"},
        "running": {"part": "leg", "name": "Running", "emoji": "🏃", "req": "leg"},
        "neck_extensions": {"part": "neck", "name": "Neck Extensions", "emoji": "🧣", "req": "neck"},
        "chewing_drills": {"part": "maw", "name": "Jaw Exercises", "emoji": "🦷", "req": "head"},
        "head_lifts": {"part": "head", "name": "Weighted Head Lifts", "emoji": "👤", "req": "head"},
        "full_body": {"part": "all", "name": "Full Body Routine", "emoji": "🌟", "req": None}
    }

    ex_data = BODY_PART_EXERCISES.get(exercise)
    if not ex_data:
        raise ValueError("❌ Exercise not found!")

    # --- ANATOMICAL REQUIREMENT CHECK ---
    required_type = ex_data["req"]
    if required_type:
        limb_map = {
            "arm": ["arm", "front"],
            "leg": ["leg", "back"],
            "neck": ["neck"],
            "head": ["head"]
        }
        target_keywords = limb_map.get(required_type, [required_type])
        has_required_part = any(
            any(k in name for k in target_keywords)
            for name in this_player.body.keys()
        )

        if not has_required_part:
            raise ValueError(
                f"❌ Your current body type (**{this_player.body_type.value}**) "
                f"lacks the necessary anatomy ({required_type}) to perform **{ex_data['name']}**!"
            )

    units = this_player.units
    is_cardio = (workout_type == "cardio" or exercise == "running")
    total_cost = this_player.workout_cost

    # --- PROTEIN CHECK (Skipped if free_protein=True or it's cardio) ---
    player_torsos = [part for part in this_player.body.values() if hasattr(part, 'protein_content')]
    available_protein = sum(t.protein_content for t in player_torsos)

    # This remains the baseline muscle gain, untouched by the efficiency divider
    potential_gain = (total_cost / 1_000_000.0) * 0.1
    total_protein_with_quality = sum(t.protein_content * t.protein_quality for t in player_torsos)
    avg_protein_quality = total_protein_with_quality / available_protein if available_protein > 0 else 0.0
    protein_efficiency_divider = 1.0 + avg_protein_quality

    if not is_cardio and not free_protein:
        if available_protein <= 0:
            raise ValueError(
                "❌ Training aborted! Your stomach is empty of protein. You need building blocks to grow!")

        required_protein = potential_gain / protein_efficiency_divider

        if available_protein < required_protein:
            needed_protein = required_protein - available_protein
            raise ValueError(
                f"❌ You only have {util.format_quantity(available_protein * ureg.kilogram, units)} of protein. "
                f"You need {util.format_quantity(needed_protein * ureg.kilogram, units)} more to sustain this workout."
            )

    # --- STAMINA CHECK (Skipped if free_stamina=True) ---
    if not free_stamina and this_player.stamina < total_cost:
        needed = total_cost - this_player.stamina
        raise ValueError(f"❌ Too exhausted! Need {util.format_quantity(needed * ureg.joule, units)} more energy.")

    # --- DEDUCT STAMINA ---
    if not free_stamina:
        this_player.stamina -= total_cost

    # --- EXECUTE PHYSICS AND GROWTH ---
    if is_cardio:
        # 1. Save fitness state BEFORE the workout
        fitness_before = this_player.fitness

        # 2. Cardio Logic: Burn fat based on energy cost
        energy_to_burn = total_cost
        fat_to_burn = energy_to_burn / 37_000_000.0
        actual_fat_burned = -this_player.add_fat_mass(-fat_to_burn)

        # 3. Dynamic Fitness Growth: Exactly 1% of the remaining mass gap (in kg)
        fitness_growth_effects = this_player.get_effects(effect.EffectType.FITNESS_GROWTH)
        fitness_growth_multiplier = 1.0 + sum(e.power for e in fitness_growth_effects)

        this_player.train_cardio(intensity_fraction=0.01 * fitness_growth_multiplier)
        delta_fitness = this_player.fitness - fitness_before

        # 4. Gather anatomical components (UNIVERSAL: Supports both legged and serpentine forms)
        leg_keywords = ['leg', 'front', 'back']
        leg_parts = [p for n, p in this_player.body.items() if any(k in n for k in leg_keywords)]

        if leg_parts:
            # --- LEGGED LOCOMOTION PHYSICS ---
            leg_muscle = sum(p.muscle_mass for p in leg_parts if hasattr(p, 'muscle_mass'))
            avg_leg_length = sum(p.length for p in leg_parts) / len(leg_parts)

            stride_base = 1.5 + (avg_leg_length * 1.5)
            relative_muscle = leg_muscle / (this_player.get_mass() * 0.15)

            # Used later for distance efficiency scaling
            efficiency_length_factor = avg_leg_length
        else:
            # --- SERPENTINE LOCOMOTION PHYSICS (Snake/No Legs) ---
            # Look for core, torso or tail parts that drive slithering motion
            core_keywords = ['torso', 'body', 'tail', 'core']
            core_parts = [p for n, p in this_player.body.items() if any(k in n for k in core_keywords)]

            core_muscle = sum(p.muscle_mass for p in core_parts if hasattr(p, 'muscle_mass'))

            # For a snake, total body length represents their maximum potential undulating "stride"
            total_body_length = sum(p.length for p in this_player.body.values() if hasattr(p, 'length'))
            # Default fallback if length is missing
            if total_body_length <= 0:
                total_body_length = 2.86

                # Slithering physics: Stride is based on lateral undulation amplitude (scaled by total length)
            stride_base = 1.0 + (total_body_length * 0.8)

            # Snakes use their entire body mass as muscle to move, so we check total core muscle vs weight
            relative_muscle = core_muscle / (this_player.get_mass() * 0.25)

            efficiency_length_factor = total_body_length * 0.3  # Scale efficiency by a fraction of length

        # 5. Speed Physics (Calculated using the dynamically selected locomotion values)
        fat_penalty = 1.0 - (this_player.get_fat_ratio() * 0.4)

        speed_mps = (stride_base * (1.0 + relative_muscle)) * fat_penalty * this_player.energy_efficiency_multiplier
        speed_kmh = speed_mps * 3.6

        # 6. Efficiency & Distance Physics
        base_efficiency = 2.4 / this_player.energy_efficiency_multiplier
        scaled_efficiency = base_efficiency * (24.0 * (1.0 / (efficiency_length_factor + 0.1)))
        distance_meters = total_cost / (this_player.get_mass() * scaled_efficiency)

        # 7. Formatting output displays
        formatted_speed_val = util.format_quantity(speed_kmh * ureg.kilometer, units)

        # Format the fitness mass and its delta using the player's unit system (Metric/Imperial)
        formatted_fitness = util.format_quantity(this_player.fitness * ureg.kilogram, units)
        formatted_delta = util.format_quantity(delta_fitness * ureg.kilogram, units)

        return (
            f"🏃 Cardio complete! Burned **{util.format_quantity(actual_fat_burned * ureg.kilogram, units)}** of fat.\n"
            f"Distance: **{util.format_quantity(distance_meters * ureg.meter, units)}** | "
            f"Avg Speed: **{formatted_speed_val}/h**\n"
            f"📈 Fitness: **{formatted_fitness}** (+{formatted_delta}) | "
            f"Ratio: **{this_player.fitness_ratio * 100.0:.1f}%** | "
            f"Efficiency: **{this_player.energy_efficiency_multiplier:.2f}x**"
        )
    else:
        # Strength Logic
        target_key = ex_data["part"]
        if target_key == "all":
            targets = [part for part in this_player.body.values() if isinstance(part, player.Body)]
            strength_coeff = 4.2
        else:
            target_map = {"arm": ["arm", "front"], "leg": ["leg", "back"], "torso": ["torso"], "neck": ["neck"],
                          "head": ["head"], "maw": ["head", "maw"]}
            keywords = target_map.get(target_key, [target_key])
            targets = [part for name, part in this_player.body.items() if
                       any(k in name for k in keywords) and isinstance(part, player.Body)]
            strength_coeff = 5.5

        involved_muscle = sum(p.muscle_mass for p in targets) if targets else 0

        # --- MUSCLE GROWTH MULTIPLIER ---
        muscle_growth_effects = this_player.get_effects(effect.EffectType.MUSCLE_GROWTH)
        muscle_growth_multiplier = 1.0 + sum(e.power for e in muscle_growth_effects)

        # Apply muscle growth multiplier to the potential gain
        adjusted_potential_gain = potential_gain * muscle_growth_multiplier

        # If protein is free, we treat available protein as infinite for calculations
        effective_protein = adjusted_potential_gain if free_protein else available_protein
        actual_growth_total = min(adjusted_potential_gain, effective_protein)

        if targets and actual_growth_total > 0:
            growth_per_part = actual_growth_total / len(targets)
            for part in targets:
                part.muscle_mass += growth_per_part

            # Only consume protein if it's not free
            if not free_protein:
                # Calculate how much protein to actually consume based on the average quality modifier
                # Formula: protein_to_consume = actual_growth_total / (1.0 + avg_protein_quality)
                protein_to_consume = actual_growth_total / protein_efficiency_divider

                for t in player_torsos:
                    if protein_to_consume <= 0:
                        break
                    take = min(t.protein_content, protein_to_consume)

                    # Remove the protein using its specific quality (0 keeps existing quality logic intact)
                    t.add_proteins(-take, 0)
                    if hasattr(t, 'metabolic_chyme'):
                        t.metabolic_chyme += take
                    protein_to_consume -= take

        weight_lifted_kg = involved_muscle * strength_coeff

        response_text = (
            f"{ex_data['emoji']} **{ex_data['name']}**! "
            f"Gained **{util.format_quantity(actual_growth_total * ureg.kilogram, units)}** of muscle.\n"
            f"Weight Lifted: **{util.format_quantity(weight_lifted_kg * ureg.kilogram, units)}**"
        )

        # Return both the text for general use and the raw variable for buttons/logic
        return response_text, actual_growth_total


class WorkoutInterface(discord.ui.View):
    """Interactive view providing select menus for workout type and exercises."""

    def __init__(self, cog, player_obj):
        super().__init__(timeout=60)
        self.cog = cog
        self.player = player_obj
        self.selected_type = None

        # Define available options internally
        self.cardio_exercises = ["running"]
        self.strength_exercises = [
            "bench_press", "bicep_curls", "squats", "neck_extensions",
            "chewing_drills", "head_lifts", "full_body"
        ]

        # Initialize the first select menu (Type Selection)
        self.add_type_select()

    def add_type_select(self):
        """Adds the initial dropdown menu to pick between Cardio and Strength."""
        self.clear_items()

        select = discord.ui.Select(
            placeholder="Choose your training split...",
            options=[
                discord.SelectOption(label="💪 Strength Training", value="strength"),
                discord.SelectOption(label="🏃 Cardio", value="cardio")
            ]
        )
        select.callback = self.type_callback
        self.add_item(select)

    async def type_callback(self, interaction: discord.Interaction):
        """Handles the workout type selection and transitions to specific exercises."""
        if interaction.user.id != self.player.id:
            await interaction.response.send_message("This menu is not for you!", ephemeral=True)
            return

        self.selected_type = interaction.data['values'][0]
        options_pool = self.cardio_exercises if self.selected_type == 'cardio' else self.strength_exercises

        # Re-build view items for the second stage (Exercise Selection)
        self.clear_items()

        exercise_options = [
            discord.SelectOption(label=opt.replace('_', ' ').capitalize(), value=opt)
            for opt in options_pool
        ]

        exercise_select = discord.ui.Select(
            placeholder=f"Select a {self.selected_type} exercise...",
            options=exercise_options
        )
        exercise_select.callback = self.exercise_callback
        self.add_item(exercise_select)

        # Update the original message with the new dropdown
        embed = discord.Embed(
            title="🎯 Select Your Exercise",
            description=f"You chose **{self.selected_type.capitalize()}**. Now, pick your specific exercise routine "
                        f"below:",
            color=0x3498db
        )
        await interaction.response.edit_message(embed=embed, view=self)

    async def exercise_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.player.id:
            await interaction.response.send_message("This menu is not for you!", ephemeral=True)
            return

        selected_exercise = interaction.data['values'][0]

        await interaction.response.defer()

        try:
            workout_result = await process_workout(
                this_player=self.player,
                exercise=selected_exercise,
                workout_type=self.selected_type,
                free_stamina=False,
                free_protein=False
            )

            # Safe unpacking check or direct assignment depending on what process_workout returns
            if isinstance(workout_result, tuple) and len(workout_result) == 2:
                text_report, raw_muscle_gain = workout_result
            else:
                text_report = str(workout_result)
                raw_muscle_gain = 0

        except ValueError as e:
            error_embed = discord.Embed(
                title="❌ Insufficient Resources",
                description=f"### Operation Halted\n{str(e)}",
                color=0xFF3333
            )
            await interaction.edit_original_response(embed=error_embed, view=self)
            return

        self.clear_items()

        units = self.player.units
        stamina_section = util.get_stamina_display(self.player, units)

        formatted_description = (
            f"### 💪 Routine Results\n"
            f"{text_report}"
        )

        embed = discord.Embed(
            title="🏋️ Workout Execution Report",
            description=formatted_description,
            color=0x3498db
        )

        embed.add_field(
            name="⚡ Energy Expended",
            value=f"`{util.format_quantity(self.player.workout_cost * ureg.joule, units)}`",
            inline=True
        )
        embed.add_field(
            name="🔋 Current Stamina State",
            value=stamina_section,
            inline=False
        )

        await interaction.edit_original_response(embed=embed, view=self)


class BodyTypeSelect(discord.ui.Select):
    """Dropdown selection menu for choosing a target body type."""

    def __init__(self, player_module):
        self.player_module = player_module

        # Populate the dropdown options dynamically from the BodyType Enum
        options = [
            discord.SelectOption(
                label=bt.value.replace("_", " ").title(),
                value=bt.name,
                description=f"Transform into a {bt.value.replace('_', ' ').lower()}."
            )
            for bt in self.player_module.BodyType
        ]

        super().__init__(
            placeholder="Choose your new form...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        # Retrieve the player profile associated with the interaction user
        grower = util.get_player_from_interaction(interaction)
        if not grower:
            await interaction.response.send_message("Player profile could not be found.", ephemeral=True)
            return

        # Convert the selected string value back into the actual Enum member
        selected_enum = self.player_module.BodyType[self.values[0]]

        # Capture the previous body type for the message description
        old_type_val = getattr(grower, 'body_type', 'unknown')
        old_label = old_type_val.value.replace("_", " ").title() if hasattr(old_type_val, 'value') else str(
            old_type_val)

        # Execute the transformation logic
        morph_player_body(grower, selected_enum)

        # Build the final success embed
        embed = discord.Embed(
            title="✨ Transformation Complete",
            description=f"You have transformed from **{old_label}** into a **{selected_enum.value.replace('_', ' ').title()}**.",
            color=0xBEBEFE
        )

        # Update the interaction message to replace the view with the success report
        await interaction.response.edit_message(embed=embed, view=None)


class BodyTypeView(discord.ui.View):
    """View container hosting the body type selection dropdown."""

    def __init__(self, player_module, author_id: int):
        super().__init__(timeout=60)
        self.author_id = author_id
        self.add_item(BodyTypeSelect(player_module))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # Ensure only the command author can interact with the dropdown menu
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("This menu is not for you!", ephemeral=True)
            return False
        return True


class TalentConfirmView(discord.ui.View):
    def __init__(self, player, talent_tree, talent_id: str, target_tier: int, menu_view):
        super().__init__(timeout=60)
        self.player = player
        self.talent_tree = talent_tree
        self.talent_id = talent_id
        self.target_tier = target_tier
        self.menu_view = menu_view
        self.talent = talent_tree.talents[talent_id]

    @discord.ui.button(label="Confirm Unlock", style=discord.ButtonStyle.green, emoji="✅")
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.menu_view.player_id:
            await interaction.response.send_message("This isn't your confirmation menu!", ephemeral=True)
            return

        current_progress = self.player.talents.get(self.talent_id)
        current_tier = current_progress.tier if current_progress else 0

        if self.target_tier != current_tier + 1 or self.target_tier > self.talent.max_tier:
            await interaction.response.edit_message(content="❌ This talent tier is no longer valid.", embed=None,
                                                    view=None, ephemeral=True)
            return

        if self.player.talent_points < 1:
            await interaction.response.edit_message(content="❌ You do not have enough Talent Points.",
                                                    embed=None, view=None, ephemeral=True)
            return

        can_unlock = self.talent_tree.can_unlock(
            {tid: p.tier for tid, p in self.player.talents.items()},
            self.talent_id,
            self.target_tier
        )

        if not can_unlock:
            await interaction.response.edit_message(content="❌ You no longer meet the prerequisites for this talent.",
                                                    embed=None, view=None, ephemeral=True)
            return

        self.player.talent_points -= 1
        if self.talent_id not in self.player.talents:
            self.player.talents[self.talent_id] = player.PlayerTalentProgress(tier=self.target_tier, exp=0)
        else:
            self.player.talents[self.talent_id].tier = self.target_tier

        embed = self.menu_view.build_embed()
        self.menu_view.clear_items()
        self.menu_view.add_item(TalentSelectDropdown(self.player, self.talent_tree))

        await interaction.response.edit_message(
            content=f"✅ Successfully unlocked **{self.talent.name}** (Tier {self.target_tier})!",
            embed=embed,
            view=self.menu_view
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red, emoji="✖️")
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.menu_view.player_id:
            await interaction.response.send_message("This isn't your confirmation menu!", ephemeral=True)
            return

        embed = self.menu_view.build_embed()
        self.menu_view.clear_items()
        self.menu_view.add_item(TalentSelectDropdown(self.player, self.talent_tree))

        await interaction.response.edit_message(content="Purchase cancelled.", embed=embed, view=self.menu_view)


REFUND_COST = 1  # ile talent_refund_points kosztuje jedna refundacja tieru


class TalentRefundSelectDropdown(discord.ui.Select):
    def __init__(self, player, talent_tree):
        self.player = player
        self.talent_tree = talent_tree

        options = []
        current_tiers = {tid: p.tier for tid, p in player.talents.items()}

        for talent_id, talent in talent_tree.talents.items():
            progress = player.talents.get(talent_id)
            tier = progress.tier if progress else 0

            if tier <= 0:
                continue  # nic do zrefundowania

            can_refund = talent_tree.can_refund(current_tiers, talent_id)
            has_refund_points = player.talent_refund_points >= REFUND_COST

            if can_refund and has_refund_points:
                desc = f"Tier {tier} → {tier - 1} - Refundable ({REFUND_COST} RP)"
                emoji = "🟠"
            elif not can_refund:
                desc = f"Tier {tier} - Would break dependent talents"
                emoji = "🔒"
            else:
                desc = f"Tier {tier} - Not enough Refund Points"
                emoji = "🪙"

            options.append(
                discord.SelectOption(
                    label=talent.name,
                    value=talent_id,
                    description=desc[:100],
                    emoji=emoji
                )
            )

        if not options:
            options.append(
                discord.SelectOption(label="No talents to refund", value="__none__", default=False)
            )

        super().__init__(placeholder="Choose a talent to refund a tier from...", min_values=1, max_values=1,
                         options=options)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.view.player_id:
            await interaction.response.send_message("This isn't your menu!", ephemeral=True)
            return

        talent_id = self.values[0]
        if talent_id == "__none__":
            await interaction.response.send_message("You have no talents to refund.", ephemeral=True)
            return

        talent = self.talent_tree.talents[talent_id]
        progress = self.player.talents.get(talent_id)
        current_tier = progress.tier if progress else 0

        if current_tier <= 0:
            await interaction.response.send_message(f"**{talent.name}** has no tiers to refund.", ephemeral=True)
            return

        if self.player.talent_refund_points < REFUND_COST:
            await interaction.response.send_message("You do not have enough Talent Refund Points!", ephemeral=True)
            return

        can_refund = self.talent_tree.can_refund(
            {tid: p.tier for tid, p in self.player.talents.items()},
            talent_id
        )

        if not can_refund:
            await interaction.response.send_message(
                "Refunding this tier would break prerequisites for another unlocked talent.", ephemeral=True)
            return

        confirm_embed = discord.Embed(
            title="⚠️ Confirm Talent Refund",
            description=(f"Are you sure you want to spend **{REFUND_COST} Talent Refund Point(s)** "
                         f"to refund **{talent.name}** from Tier {current_tier} to Tier {current_tier - 1}?\n\n"
                         f"You will receive **1 Talent Point** back."),
            color=0xe67e22
        )

        confirm_view = TalentRefundConfirmView(self.player, self.talent_tree, talent_id, self.view)
        await interaction.response.edit_message(content=None, embed=confirm_embed, view=confirm_view)


class TalentRefundConfirmView(discord.ui.View):
    def __init__(self, player, talent_tree, talent_id: str, menu_view):
        super().__init__(timeout=60)
        self.player = player
        self.talent_tree = talent_tree
        self.talent_id = talent_id
        self.menu_view = menu_view
        self.talent = talent_tree.talents[talent_id]

    @discord.ui.button(label="Confirm Refund", style=discord.ButtonStyle.red, emoji="↩️")
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.menu_view.player_id:
            await interaction.response.send_message("This isn't your confirmation menu!", ephemeral=True)
            return

        current_progress = self.player.talents.get(self.talent_id)
        current_tier = current_progress.tier if current_progress else 0

        if current_tier <= 0:
            await interaction.response.edit_message(content="❌ This talent has no tiers to refund.", embed=None,
                                                    view=None, ephemeral=True)
            return

        if self.player.talent_refund_points < REFUND_COST:
            await interaction.response.edit_message(content="❌ You do not have enough Talent Refund Points.",
                                                    embed=None, view=None, ephemeral=True)
            return

        can_refund = self.talent_tree.can_refund(
            {tid: p.tier for tid, p in self.player.talents.items()},
            self.talent_id
        )

        if not can_refund:
            await interaction.response.edit_message(
                content="❌ Refunding this tier would break prerequisites for another unlocked talent.",
                embed=None, view=None, ephemeral=True)
            return

        self.player.talent_refund_points -= REFUND_COST
        self.player.talent_points += 1

        new_tier = current_tier - 1
        if new_tier <= 0:
            del self.player.talents[self.talent_id]
        else:
            self.player.talents[self.talent_id].tier = new_tier

        embed = self.menu_view.build_embed()
        self.menu_view.clear_items()
        self.menu_view.add_item(TalentSelectDropdown(self.player, self.talent_tree))
        self.menu_view.add_item(TalentRefundSelectDropdown(self.player, self.talent_tree))

        await interaction.response.edit_message(
            content=f"↩️ Refunded 1 tier of **{self.talent.name}** (now Tier {new_tier}).",
            embed=embed,
            view=self.menu_view
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.grey, emoji="✖️")
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.menu_view.player_id:
            await interaction.response.send_message("This isn't your confirmation menu!", ephemeral=True)
            return

        embed = self.menu_view.build_embed()
        self.menu_view.clear_items()
        self.menu_view.add_item(TalentSelectDropdown(self.player, self.talent_tree))
        self.menu_view.add_item(TalentRefundSelectDropdown(self.player, self.talent_tree))

        await interaction.response.edit_message(content="Refund cancelled.", embed=embed, view=self.menu_view)


class TalentSelectDropdown(discord.ui.Select):
    def __init__(self, player, talent_tree):
        self.player = player
        self.talent_tree = talent_tree

        options = []
        for talent_id, talent in talent_tree.talents.items():
            current_progress = player.talents.get(talent_id)
            current_tier = current_progress.tier if current_progress else 0

            if current_tier < talent.max_tier:
                next_tier = current_tier + 1
                can_unlock = talent_tree.can_unlock(
                    {tid: p.tier for tid, p in player.talents.items()},
                    talent_id,
                    next_tier
                )
                has_points = player.talent_points >= 1

                if can_unlock and has_points:
                    desc = f"Tier {next_tier}/{talent.max_tier} - Available (1 TP)"
                    emoji = "🟢"
                elif not can_unlock:
                    desc = f"Tier {next_tier}/{talent.max_tier} - Prerequisites Locked"
                    emoji = "🔒"
                else:
                    desc = f"Tier {next_tier}/{talent.max_tier} - Not enough TP"
                    emoji = "🪙"
            else:
                desc = f"Max Tier Reached ({talent.max_tier})"
                emoji = "⭐"

            options.append(
                discord.SelectOption(
                    label=talent.name,
                    value=talent_id,
                    description=desc[:100],
                    emoji=emoji
                )
            )

        super().__init__(placeholder="Choose a talent to upgrade or unlock...", min_values=1, max_values=1,
                         options=options)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.view.player_id:
            await interaction.response.send_message("This isn't your menu!")
            return

        talent_id = self.values[0]
        talent = self.talent_tree.talents[talent_id]

        current_progress = self.player.talents.get(talent_id)
        current_tier = current_progress.tier if current_progress else 0
        next_tier = current_tier + 1

        if current_tier >= talent.max_tier:
            await interaction.response.send_message(f"**{talent.name}** is already at maximum tier!")
            return

        if self.player.talent_points < 1:
            await interaction.response.send_message("You do not have enough Talent Points!")
            return

        can_unlock = self.talent_tree.can_unlock(
            {tid: p.tier for tid, p in self.player.talents.items()},
            talent_id,
            next_tier
        )

        if not can_unlock:
            await interaction.response.send_message("You do not meet the prerequisites for this talent tier yet.")
            return

        confirm_embed = discord.Embed(
            title="⚠️ Confirm Talent Purchase",
            description=f"Are you sure you want to spend **1 Talent Point** to unlock **{talent.name} (Tier {next_tier})**?",
            color=0xe67e22
        )

        confirm_view = TalentConfirmView(self.player, self.talent_tree, talent_id, next_tier, self.view)
        await interaction.response.edit_message(content=None, embed=confirm_embed, view=confirm_view)


class TalentMenuView(discord.ui.View):
    def __init__(self, player, talent_tree):
        super().__init__(timeout=180)
        self.player = player
        self.talent_tree = talent_tree
        self.player_id = player.id if hasattr(player, 'id') else None

        self.add_item(TalentSelectDropdown(self.player, self.talent_tree))
        self.add_item(TalentRefundSelectDropdown(self.player, self.talent_tree))

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="🌟 Talent Tree",
            description=(f"Available Talent Points: **{self.player.talent_points}**\n"
                         f"Available Refund Points: **{self.player.talent_refund_points}**\n"
                         f"Select a talent below to upgrade, or use the refund menu to reclaim a tier."),
            color=0xf1c40f
        )

        for talent_id, talent in self.talent_tree.talents.items():
            progress = self.player.talents.get(talent_id)
            tier = progress.tier if progress else 0

            field_value = talent.description if talent.description else "No description available."

            if talent.prerequisites:
                req_strings = []
                for req in talent.prerequisites:
                    req_id, req_tier = (req, 1) if isinstance(req, str) else req
                    req_talent = self.talent_tree.talents.get(req_id)
                    req_name = req_talent.name if req_talent else req_id
                    req_strings.append(f"{req_name} (Tier {req_tier}+)")

                req_joiner = " OR " if talent.req_type == RequirementType.ONE_OF else " AND "
                field_value += f"\n🔒 **Prerequisites:** {req_joiner.join(req_strings)}"

            embed.add_field(
                name=f"{talent.name} (Tier {tier}/{talent.max_tier})",
                value=field_value,
                inline=False
            )

        return embed


class CookOptionsView(discord.ui.View):
    def __init__(self, player, unit_system):
        super().__init__(timeout=180)
        self.player = player
        self.unit_system = unit_system
        self.use_talent = False

        cook_progress = player.talents.get("cook")
        self.cook_tier = cook_progress.tier if cook_progress else 0

        # If player has no cook talent, disable or hide talent options
        if self.cook_tier == 0:
            self.remove_item(self.toggle_talent_button)

    @discord.ui.button(label="Cook Talent: OFF", style=discord.ButtonStyle.secondary, emoji="❌")
    async def toggle_talent_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.player.id:
            await interaction.response.send_message("This isn't your kitchen!", ephemeral=True)
            return

        self.use_talent = not self.use_talent
        if self.use_talent:
            button.label = f"Cook Talent: ON (Tier {self.cook_tier}, -1 Stamina)"
            button.style = discord.ButtonStyle.success
            button.emoji = "✅"
        else:
            button.label = "Cook Talent: OFF"
            button.style = discord.ButtonStyle.secondary
            button.emoji = "❌"

        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Proceed to Kitchen", style=discord.ButtonStyle.primary, emoji="🍳")
    async def proceed_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.player.id:
            await interaction.response.send_message("This isn't your kitchen!", ephemeral=True)
            return

        modal = CookMealModal(self.player, self.unit_system, use_talent=self.use_talent, cook_tier=self.cook_tier)
        await interaction.response.send_modal(modal)


class ConfirmBuyView(discord.ui.View):
    def __init__(self, interaction: discord.Interaction, buyer, offer, market):
        super().__init__(timeout=60)  # View expires after 60 seconds
        self.original_interaction = interaction
        self.buyer = buyer
        self.offer = offer
        self.market = market
        self.value = None

    @discord.ui.button(label="Confirm Purchase", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Ensure only the original buyer can click the button
        if interaction.user.id != self.original_interaction.user.id:
            await interaction.response.send_message("This is not your transaction!", ephemeral=True)
            return

        # Double check if the offer still exists in the market
        if self.offer not in self.market.offers:
            await interaction.response.edit_message(content="This offer is no longer available!", view=None, embed=None)
            return

        # Check buyer troves again just in case
        buyer_troves = getattr(self.buyer, "troves", 0.0)
        if buyer_troves < self.offer.price:
            await interaction.response.edit_message(content="You no longer have enough troves to buy this item!",
                                                    view=None, embed=None)
            return

        # --- EXECUTE PURCHASE ---
        self.buyer.troves -= self.offer.price

        seller = util.get_player_from_id(interaction, self.offer.seller_id)
        if seller is not None:
            seller.troves = getattr(seller, "troves", 0.0) + self.offer.price

        buyer_inventory = self.buyer.inventory
        buyer_inventory.append(self.offer.item)

        self.market.remove_offer(self.offer)

        # Prepare public announcement with seller mention
        seller_mention = f"<@{self.offer.seller_id}>"

        embed = discord.Embed(
            title="Market Purchase",
            description=f"**{interaction.user.display_name}** successfully purchased **{self.offer.item.name}** "
                        f"from {seller_mention} for **{self.offer.price} kg**!",
            color=0x00FF00
        )

        # Edit the original message publicly (removing ephemeral state or replying openly)
        await interaction.response.edit_message(content=None, embed=embed, view=None)
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.original_interaction.user.id:
            await interaction.response.send_message("This is not your transaction!", ephemeral=True)
            return

        embed = discord.Embed(description="Purchase cancelled.", color=0xFF0000)
        await interaction.response.edit_message(content=None, embed=embed, view=None)
        self.stop()

    async def on_timeout(self):
        # Disable buttons when the view times out
        for child in self.children:
            child.disabled = True
        try:
            await self.original_interaction.edit_original_response(content="Purchase timed out.", view=self)
        except Exception:
            pass


class BrewPotionModal(discord.ui.Modal, title="Brew a Potion"):
    def __init__(self, grower, potion_template, unit_system):
        super().__init__()
        self.player = grower
        self.potion_template = potion_template
        self.unit_system = unit_system

        alchemist_progress = grower.talents.get("alchemist")
        self.alchemist_tier = alchemist_progress.tier if alchemist_progress else 1

        player_mass = self.player.get_base_mass()

        min_fraction = 1.0 / (1000 * (10 ** (self.alchemist_tier - 1)))
        max_fraction = 10 ** (self.alchemist_tier - 1)

        self.min_size_l = player_mass * min_fraction
        self.max_size_l = player_mass * max_fraction

        self.cost_per_liter = 10.0

        min_size_formatted = util.format_quantity(self.min_size_l * ureg.l, self.player.units)
        max_size_formatted = util.format_quantity(self.max_size_l * ureg.l, self.player.units)

        self.potion_size = discord.ui.TextInput(
            label=f"Potion Size",
            placeholder=f"Allowed: {min_size_formatted} - {max_size_formatted}",
            style=discord.TextStyle.short
        )

        self.add_item(self.potion_size)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            parsed_size = util.ureg.Quantity(self.potion_size.value)
            size_in_liters = parsed_size.to('liter').magnitude
        except Exception:
            await interaction.response.send_message("Invalid potion size format!", ephemeral=True)
            return

        if size_in_liters < self.min_size_l or size_in_liters > self.max_size_l:
            min_size_formatted = util.format_quantity(self.min_size_l * ureg.l, self.player.units)
            max_size_formatted = util.format_quantity(self.max_size_l * ureg.l, self.player.units)
            await interaction.response.send_message(
                f"Potion size out of bounds! Allowed: {min_size_formatted} - {max_size_formatted}.",
                ephemeral=True
            )
            return

        total_cost_kg = size_in_liters * self.cost_per_liter
        player_troves = self.player.troves

        if player_troves < total_cost_kg:
            total_cost_formatted = util.format_quantity(total_cost_kg * ureg.kg, self.player.units)
            player_troves_formatted = util.format_quantity(player_troves * ureg.kg, self.player.units)
            await interaction.response.send_message(
                f"You don't have enough troves! Required: **{total_cost_formatted}**, "
                f"available: **{player_troves_formatted}**.",
                ephemeral=True
            )
            return

        current_stamina = self.player.stamina
        stamina_bar = self.player.workout_cost
        if current_stamina < stamina_bar:
            await interaction.response.send_message("You don't have enough stamina to brew this potion!",
                                                    ephemeral=True)
            return

        self.player.troves -= total_cost_kg
        self.player.stamina -= stamina_bar

        new_potion = Potion(
            name=self.potion_template.name,
            value=self.potion_template.value * (size_in_liters / self.potion_template.size),
            size=size_in_liters,
            tier=self.alchemist_tier,
            effects_data=self.potion_template.effects_data,
            emoji=self.potion_template.emoji,
            nsfw=self.potion_template.nsfw,
            creator_id=self.player.id
        )

        self.player.add_item(new_potion)
        total_cost_formatted = format_quantity(total_cost_kg * ureg.kg, self.player.units)
        embed = discord.Embed(
            title=f"{new_potion.emoji} {new_potion.name}",
            description=f"You have brewed {new_potion.full_name_with_article} **Tier {new_potion.tier}** "
                        f"(Volume: {format_quantity(size_in_liters * util.ureg.liter, self.unit_system)}) "
                        f"and added it to your inventory!\nCost: **{total_cost_formatted}** troves & 1 stamina bar.",
            color=0x00FF00
        )
        await interaction.response.send_message(embed=embed, ephemeral=False)


logger = logging.getLogger("bot")


class BrewPotionSelect(discord.ui.Select):
    """Dropdown list allowing the player to select which potion to brew."""

    def __init__(self, potions_dict: dict, grower, unit_system):
        self.grower = grower
        self.unit_system = unit_system
        self.potions_dict = potions_dict

        alchemist_data = self.grower.talents.get("alchemist")
        alchemist_tier = getattr(alchemist_data, "tier", 0) if alchemist_data is not None else 0

        options = []
        for key, potion in potions_dict.items():
            emoji_arg = potion.emoji

            logger.debug(f"[BREW DEBUG] Potion '{potion.name}' raw emoji: {repr(emoji_arg)}")

            if emoji_arg and emoji_arg.startswith("<"):
                try:
                    emoji_arg = discord.PartialEmoji.from_str(emoji_arg)
                    logger.debug(f"[BREW DEBUG] Parsed Custom Emoji: {emoji_arg}")
                except Exception as e:
                    logger.error(f"[BREW DEBUG] Failed to parse custom emoji '{emoji_arg}': {e}")
                    emoji_arg = "🧪"

            effect_descriptions = []
            for eff_key in potion.effects_data.keys():
                template = eff_key.value[5]

                power = float(alchemist_tier)
                power_pct = power * 100.0

                formatted_desc = template.replace("{power}", str(power)).replace("{power_pct}", str(power_pct)).replace(
                    "**", "")
                effect_descriptions.append(formatted_desc)

            effect_text = ", ".join(effect_descriptions)
            description_text = effect_text if effect_text else "No effects"
            if len(description_text) > 100:
                description_text = description_text[:97] + "..."

            options.append(
                discord.SelectOption(
                    label=potion.name,
                    description=description_text,
                    emoji=emoji_arg,
                    value=key
                )
            )

        super().__init__(placeholder="Choose a potion to brew...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        selected_key = self.values[0]
        potion_template = self.potions_dict[selected_key]

        modal = BrewPotionModal(self.grower, potion_template, self.unit_system)
        await interaction.response.send_modal(modal)


class BrewPotionView(discord.ui.View):
    """View container for the potion selection dropdown."""

    def __init__(self, potions_dict: dict, grower, unit_system):
        super().__init__(timeout=60)
        self.add_item(BrewPotionSelect(potions_dict, grower, unit_system))


class Game(commands.Cog, name="game"):
    def __init__(self, bot) -> None:
        self.bot = bot
        self.registered_commands = set()  # Track registered commands

        # Register interactions ONCE
        self.register_interaction_command(
            name="hug",
            description="Send a warm hug to another player!",
            embed_title="Incoming Hug Request! 🤗",
            embed_description="**{sender}** wants to give you a big hug! Will you accept?",
            success_embed=discord.Embed(
                title="Hug Accepted! 🤗",
                description="{sender} and {recipient} shared a warm hug!",
                color=0x00FF00
            ),
            failure_embed=discord.Embed(
                title="Hug Declined ❌",
                description="{sender} and {recipient} did not share a hug.",
                color=0x808080
            ),
            effect_sender=(EffectType.HUGGED, 0.1, 3600),
            effect_recipient=(EffectType.HUGGED, 0.1, 3600)
        )
        self.register_interaction_command(
            name="belly_rub",
            description="Rub another player's belly to speed up their digestion slightly.",
            embed_title="Incoming Belly Rub Request! 🫳",
            embed_description="**{sender}** wants to rub your belly! Will you accept?",
            success_embed=discord.Embed(
                title="Belly Rub Accepted! 🫳",
                description="{sender} rubbed {recipient}'s belly, helping their digestion.",
                color=0x00FF00
            ),
            failure_embed=discord.Embed(
                title="Belly Rub Declined ❌",
                description="{recipient} refused to have their belly rubbed.",
                color=0x808080
            ),
            effect_recipient=(EffectType.BELLY_RUBBED, 0.1, 7200)
        )

    def register_interaction_command(self, name, description, embed_title, embed_description, success_embed,
                                     failure_embed, effect_sender=None,
                                     effect_recipient=None,
                                     custom_function=None):
        """Registers an interaction command only if it hasn't been added yet."""
        if name in self.registered_commands:
            return  # Prevent duplicate registrations

        @app_commands.command(name=name, description=description)
        async def interaction_command(interaction: discord.Interaction, target: discord.Member):
            """Handles player interactions dynamically."""
            await self.handle_interaction(interaction, target, embed_title, embed_description, success_embed,
                                          failure_embed, effect_sender, effect_recipient, custom_function)

        self.bot.tree.add_command(interaction_command)  # Register the command with the bot
        self.registered_commands.add(name)  # Mark it as registered

    async def handle_interaction(self, interaction: discord.Interaction, target: discord.Member,
                                 embed_title: str, embed_description: str,
                                 success_embed: discord.Embed, failure_embed: discord.Embed,
                                 effect_sender=None, effect_recipient=None,
                                 custom_function=None):
        """Handles the logic for when the interaction is executed."""

        sender = interaction.user
        if sender.id == target.id:
            await interaction.response.send_message("You can't interact with yourself!", ephemeral=True)
            return

        embed_description = embed_description.format(sender=sender.display_name)

        embed = discord.Embed(
            title=embed_title,
            description=embed_description,
            color=0xFFD700
        )

        await interaction.response.send_message(
            content=target.mention,
            embed=embed,
            view=PlayerInteractionView(
                initiator=sender,
                recipient=target,
                effect_initiator=effect_sender,
                effect_recipient=effect_recipient,
                custom_function=custom_function,
                success_embed=success_embed,
                failure_embed=failure_embed
            )
        )

    @commands.hybrid_command(
        name="createuniverse",
        description="Create a new, isolated universe in this channel."
    )
    @commands.is_owner()
    async def createuniverse(self, context: Context, *, name: str):
        if universe.multiverse_instance.get_universe_from_id(context.channel.id):
            embed = discord.Embed(
                description="This channel already belongs to a universe.",
                color=0xBEBEFE
            )
        else:
            universe.multiverse_instance.create_universe(context.channel.id, name)
            embed = discord.Embed(
                description=f"Universe **{name}** created.\nThis channel is now the main channel.",
                color=0xBEBEFE
            )

        await context.send(embed=embed)

    @commands.hybrid_command(
        name="addchannel",
        description="Add another channel to this universe."
    )
    @commands.is_owner()
    async def addchannel(self, context: Context, channel: discord.TextChannel):
        universe_obj = universe.multiverse_instance.get_universe_from_id(context.channel.id)
        if not universe_obj:
            return await context.send("This channel is not part of any universe.")

        try:
            universe.multiverse_instance.add_channel(universe_obj, channel.id)
            await context.send(f"Added {channel.mention} to this universe.")
        except ValueError as e:
            await context.send(str(e))

    @commands.hybrid_command(
        name="removechannel",
        description="Remove a channel from its universe."
    )
    @commands.is_owner()
    async def removechannel(self, context: Context, channel: discord.TextChannel):
        universe_obj = universe.multiverse_instance.get_universe_from_id(channel.id)
        if not universe_obj:
            return await context.send("That channel is not part of any universe.")

        try:
            universe.multiverse_instance.remove_channel(universe_obj, channel.id)
            await context.send(f"Removed {channel.mention} from its universe.")
        except ValueError as e:
            await context.send(str(e))

    @commands.hybrid_command(
        name="setmainchannel",
        description="Set the main channel for this universe."
    )
    @commands.is_owner()
    async def setmainchannel(self, context: Context, channel: discord.TextChannel):
        universe_obj = universe.multiverse_instance.get_universe_from_id(context.channel.id)
        if not universe_obj:
            return await context.send("This channel is not part of any universe.")

        try:
            universe.multiverse_instance.set_main_channel(universe_obj, channel.id)
            await context.send(f"{channel.mention} is now the main channel.")
        except ValueError as e:
            await context.send(str(e))

    @commands.hybrid_command(name="morph", description="Change your body type using an interactive menu.")
    @require_player(allow_trapped=False, allow_overfilled=True)
    async def morph(self, ctx: Context):
        """Allows a player to transform their body via an interactive dropdown."""
        # Create an initial embed prompting the user to select their desired form
        embed = discord.Embed(
            title="🧬 Body Morph",
            description="Select your desired form from the dropdown menu below. Warning: morphing your body will "
                        "remove any unevenness in body parts gained through gameplay.",
            color=0x3498db
        )

        # Attach the dropdown view to the message
        view = BodyTypeView(player, ctx.author.id)
        await ctx.send(embed=embed, view=view)

    @commands.hybrid_command(name="troves", description="Checks your current troves balance.")
    @require_player(allow_trapped=True, allow_overfilled=True)
    async def troves_command(self, ctx: commands.Context):
        # Retrieve the player profile associated with the context
        grower = util.get_player_from_ctx(ctx)

        # Format the raw troves value according to the player's unit system
        formatted_troves = util.format_quantity(grower.troves * ureg.kg, grower.units)

        # Build an embed displaying the user's balance
        embed = discord.Embed(
            title="💰 Hoard Balance",
            description=f"Your troves: **{formatted_troves}**.",
            color=0xf1c40f
        )

        # Send the embed to the channel
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="talents", description="View and unlock your talents.")
    @require_player(allow_trapped=False, allow_overfilled=False)
    async def talents(self, ctx: Context):
        player = util.get_player_from_ctx(ctx)
        view = TalentMenuView(player, talent_tree)
        embed = view.build_embed()  # Generates the embed with all talent fields & descriptions
        await ctx.send(embed=embed, view=view)

    @commands.hybrid_command(name="refund_talents", description="Refund all talents for a specific player.")
    @commands.has_permissions(administrator=True)
    async def refund_talents(self, ctx: commands.Context, member: discord.Member):
        target_player = util.get_player_from_id(ctx, member.id)

        if not target_player:
            await ctx.send("Player not found.", ephemeral=True)
            return

        total_refunded = 0
        for talent_name, talent_data in target_player.talents.items():
            if hasattr(talent_data, "tier") and talent_data.tier > 0:
                total_refunded += talent_data.tier
                talent_data.tier = 0
        target_player.talents.clear()

        target_player.talent_points += total_refunded

        await ctx.send(
            f"Successfully refunded all talents for {member.mention}. "
            f"Returned {total_refunded} talent points.",
            ephemeral=True
        )

    @commands.hybrid_command(name="modify_talent_points",
                             description="Add or remove talent points for a specific player.")
    @commands.has_permissions(administrator=True)
    async def modify_talent_points(self, ctx: commands.Context, member: discord.Member, points: int):
        target_player = util.get_player_from_id(ctx, member.id)

        if not target_player:
            await ctx.send("Player not found.", ephemeral=True)
            return

        # Ensure talent_points attribute exists and handle modification safely
        current_points = getattr(target_player, "talent_points", 0)
        new_points = max(0, current_points + points)
        target_player.talent_points = new_points

        action = "Added" if points >= 0 else "Removed"
        abs_points = abs(points)

        await ctx.send(
            f"Successfully {action.lower()} {abs_points} talent point(s) for {member.mention}. "
            f"Current balance: {new_points} talent point(s).",
            ephemeral=True
        )

    @commands.hybrid_command(name="size", description="Check your height, weight and other measurements.")
    @app_commands.describe(user="The user whose measurements you want to see")
    @require_player(allow_trapped=True, allow_overfilled=True)
    async def size(self, ctx: commands.Context, user: Member = None):
        def get_body_type_title(this_grower):
            """
            Calculates the build title by dynamically mapping current muscle/fat
            to a geometric scale between the player's biological min and max.
            """
            # 1. Get current masses and absolute biological limits
            m_mass = this_grower.get_muscle_mass()
            f_mass = this_grower.get_fat_mass()
            limits = this_grower.get_biological_limits()

            # 2. Helper to find which tier (0-9) a value falls into using geometric scaling
            def calculate_tier(current, min_val, max_val, exponent=1.6):
                if max_val <= min_val: return 0
                # Normalize current value to a 0.0 - 1.0 range
                ratio = max(0.0, min(1.0, (current - min_val) / (max_val - min_val)))

                # We solve: ratio = (tier / 9) ^ exponent
                # So: tier = 9 * (ratio ^ (1 / exponent))
                # This makes the first tiers very 'thin' (easy to skip)
                # and the last tiers very 'wide' (hard to reach)
                tier = int(9 * (ratio ** (1 / exponent)))
                return max(0, min(9, tier))

            # Calculate tiers based on player's current limits
            m_tier = calculate_tier(m_mass, limits['min_m'], limits['max_m'], exponent=1.8)
            f_tier = calculate_tier(f_mass, limits['min_f'], limits['max_f'], exponent=1.5)

            # 3. The Matrix
            matrix = [
                ["Emaciated", "Skeletal", "Scrawny", "Frail", "Doughy", "Soft", "Flabby", "Bloated", "Morbid",
                 "Immobile"],
                ["Stringy", "Lithe", "Slender", "Average", "Puffy", "Plump", "Fleshy", "Burly", "Hefty", "Obese"],
                ["Wiry", "Toned", "Lean", "Solid", "Stocky", "Thick", "Heavy-set", "Stout", "Massive", "Lumpy"],
                ["Sinewy", "Defined", "Athletic", "Rugged", "Broad", "Sturdy", "Built", "Bulky", "Dense", "Round"],
                ["Shredded", "Striated", "Ripped", "Brawny", "Burly", "Beefy", "Hardened", "Barrel", "Loaded",
                 "Solidified"],
                ["Chiseled", "Steel-Knit", "Iron-Bound", "Stalwart", "Gritty", "Bastion", "Ruggedized", "Fortified",
                 "Overloaded", "Slab"],
                ["Anatomical", "Polished", "Heroic", "Warlord", "Brute", "Crusher", "Impactful", "Thick-Skinned",
                 "Hard-Packed", "Monolithic"],
                ["Veiny", "Gladiator", "Titan-Like", "Overbuilt", "Ravager", "Mauler", "Heavy-Duty", "Juggernaut",
                 "Iron-Clad", "Stone-Wall"],
                ["Sculpted", "Exemplary", "Peerless", "Unyielding", "Savage", "Relentless", "Unbreakable",
                 "Impenetrable", "Unshakable", "Unmoving"],
                ["Hyper-Defined", "Max-Density", "Pure-Form", "Absolute", "Alpha", "Apex", "Summit", "Pinnacle", "Peak",
                 "Paradigm"]
            ]

            return matrix[m_tier][f_tier]

        author_player = util.get_player_from_member(ctx, ctx.author)
        if user is None:
            user = ctx.author
            this_player: player.Player = util.get_player_from_ctx(ctx)
        else:
            user = user
            this_player: player.Player = util.get_player_from_member(ctx, user)
        player.check_serializability(this_player)
        chest_circumferences = []
        underbust_circumferences = []  # To store the raw torso circumference
        waist_circumferences = []
        arm_circumferences = []
        leg_circumferences = []

        # Identify all breast objects to calculate total protrusion later
        breasts = [part for part in this_player.body.values() if isinstance(part, player.Breast)]
        total_breast_protrusion = sum(b.circumference_contribution for b in breasts)

        for part_name, part in this_player.body.items():
            # Collect circumferences
            if hasattr(part, 'chest_c'):
                # The raw value from torso is functionally the underbust
                raw_chest = part.chest_c
                underbust_circumferences.append(raw_chest)

                # Calculate full chest circumference by adding breast protrusion
                # We add the sum of all breast protrusions to the torso circumference
                chest_circumferences.append(raw_chest + total_breast_protrusion)

            if hasattr(part, 'waist_c'):
                waist_circumferences.append(part.waist_c)

            if hasattr(part, 'wide_c') and 'arm' in part_name:
                arm_circumferences.append(part.wide_c)

            if hasattr(part, 'wide_c') and 'leg' in part_name:
                leg_circumferences.append(part.wide_c)

        # Handle Torso specific stomach logic
        torsos = [part for part in this_player.body.values() if isinstance(part, player.Torso)]

        t_p = sum(getattr(t, 'protein_content', 0) for t in torsos)
        t_c = sum(getattr(t, 'carbohydrates_content', 0) for t in torsos)
        t_f = sum(getattr(t, 'fat_content', 0) for t in torsos)
        t_chyme = sum(getattr(t, 'metabolic_chyme', 0) for t in torsos)

        # Summing up contents and capacity
        stomach_content = t_p + t_c + t_f + t_chyme
        stomach_capacity = sum(getattr(t, 'stomach_capacity', 2.5) for t in torsos)

        # Calculate height: torso, neck, and head lengths plus longest leg length
        height = this_player.get_height()

        # Calculate average or max values for circumferences, with fallback
        avg_chest_circumference = sum(chest_circumferences) / len(
            chest_circumferences) if chest_circumferences else 0
        avg_underbust_circumference = sum(underbust_circumferences) / len(
            underbust_circumferences) if underbust_circumferences else 0
        avg_waist_circumference = sum(waist_circumferences) / len(
            waist_circumferences) if waist_circumferences else 0
        max_arm_circumference = max(arm_circumferences) if arm_circumferences else 0
        max_leg_circumference = max(leg_circumferences) if leg_circumferences else 0

        units = author_player.units
        stomach_val = format_quantity(stomach_content * ureg.kg, units)
        capacity_val = format_quantity(stomach_capacity * ureg.kg, units)
        total_mass = this_player.get_mass()
        muscle_mass = this_player.get_muscle_mass()
        fat_mass = this_player.get_fat_mass()

        muscle_p = muscle_mass / total_mass if total_mass > 0 else 0
        fat_p = fat_mass / total_mass if total_mass > 0 else 0
        fitness_p = this_player.fitness_ratio
        body_title = get_body_type_title(this_player)
        # --- NSFW ---
        nsfw_details = ""
        is_nsfw = False
        if hasattr(ctx.channel, 'is_nsfw'):
            is_nsfw = ctx.channel.is_nsfw()

        if is_nsfw:
            sexual_parts = []
            for key, part in this_player.body.items():
                if isinstance(part, player.Breast):
                    sexual_parts.append(f"> **Breast:** {part.absolute_cup} cup (∝{part.relative_cup})\n"
                                        f"└ `Mass: {format_quantity(part.total_mass * ureg.kg, units)}`\n"
                                        f"└ `Volume: {format_quantity(part.volume * ureg.m ** 3, units)}`")
                elif isinstance(part, player.Penis):
                    # Displaying both length and girth (circumference)
                    len_val = format_quantity(part.length * ureg.meter, units)
                    girth_val = format_quantity(part.girth * ureg.meter, units)
                    sexual_parts.append(f"> **Penis:** {len_val} long, {girth_val} girth")
                elif isinstance(part, player.Testes):
                    # English: Displaying diameter of a single one and total mass of the pair
                    diam_val = format_quantity(part.diameter * ureg.meter, units)
                    mass_val = format_quantity(part.total_mass * ureg.kilogram, units)
                    sexual_parts.append(f"> **Balls:** {diam_val} diameter each ({mass_val} total mass)")

            if sexual_parts:
                nsfw_details = "\n**Anatomical Details:**\n" + "\n".join(sexual_parts) + "\n"
        # --- 1. DYNAMIC COST CALCULATION ---
        # WORKOUT_COSTS is based on Joules per 1 kg of body mass
        BASE_COST_PER_KG = 12000.0 * 24
        current_mass = this_player.get_mass()

        # Actual cost of one full exercise for the current weight
        dynamic_workout_cost = BASE_COST_PER_KG * current_mass

        # --- 1. DEFINE SYMBOLS ---
        # Using standard Discord emojis for composition visualization
        P_ICON = "🟥"  # Protein
        C_ICON = "🟦"  # Carbs
        F_ICON = "🟧"  # Fats
        CH_ICON = "⬜"  # Chyme
        E_ICON = "⬛"  # Empty space

        # --- 2. CALCULATE SEGMENTS (Total 10) ---
        stomach_ratio = min(stomach_content / stomach_capacity, 1.0) if stomach_capacity > 0 else 0.0

        # Initial check: if there is nothing in the stomach, skip calculations
        if stomach_content > 0.0001:  # Use small epsilon for float stability
            fill_factor = 10 * stomach_ratio

            # Calculate segments with safety for stomach_content
            p_segs = round((t_p / stomach_content) * fill_factor)
            c_segs = round((t_c / stomach_content) * fill_factor)
            f_segs = round((t_f / stomach_content) * fill_factor)
            ch_segs = round((t_chyme / stomach_content) * fill_factor)

            # Adjust for rounding errors
            current_filled = p_segs + c_segs + f_segs + ch_segs
            target_filled = round(fill_factor)

            if current_filled != target_filled:
                segments = [p_segs, c_segs, f_segs, ch_segs]
                max_idx = segments.index(max(segments))
                segments[max_idx] += (target_filled - current_filled)
                p_segs, c_segs, f_segs, ch_segs = segments
        else:
            # Safe fallback for empty stomach
            p_segs = c_segs = f_segs = ch_segs = 0

        empty_segs = 10 - (p_segs + c_segs + f_segs + ch_segs)

        # --- 3. CONSTRUCT STOMACH BAR ---
        stomach_bar = (
                P_ICON * max(0, p_segs) +
                C_ICON * max(0, c_segs) +
                F_ICON * max(0, f_segs) +
                CH_ICON * max(0, ch_segs) +
                E_ICON * max(0, empty_segs)
        )

        stomach_text = f"{stomach_val} / {capacity_val}"

        # --- 1. PREPARE DYNAMIC MEASUREMENTS BASED ON BODY TYPE ---
        # We differentiate between bipeds (anthro), serpents (snake), and flyers (dragon)

        measurements = []
        b_type = this_player.body_type
        if b_type is None:
            # English: Basic fallback for players without a selected body type
            measurements.append("*Your form is undefined.*")
            measurements.append("\n*You must choose a form using the /morph command to see full anatomical details.*")
            embed = discord.Embed(description=measurements, color=0xBEBEFE)
            await ctx.send(embed=embed)
            return
        elif b_type in [player.BodyType.DRAGON_MALE, player.BodyType.DRAGON_FEMALE]:
            # We use your existing get_height() for the full vertical reach
            # and get_height_at_withers() for the shoulder height.
            h_withers = this_player.get_height_at_withers()
            h_full = this_player.get_height()

            full_length = this_player.get_full_length()

            # Calculating tail length correctly to get snout-to-rump body length
            tail_len = max((p.length for n, p in this_player.body.items() if 'tail' in n), default=0)
            body_length = full_length - tail_len
            wingspan = this_player.get_wingspan()

            # --- FORMATTED OUTPUT ---
            measurements.append(f"> **Height at withers:** {format_quantity(h_withers * ureg.meter, units)}")
            measurements.append(f"> **Full height:** {format_quantity(h_full * ureg.meter, units)}")
            measurements.append(f"> **Body length:** {format_quantity(body_length * ureg.meter, units)}")
            measurements.append(f"> **Total length:** {format_quantity(full_length * ureg.meter, units)}")
            measurements.append(f"> **Wingspan:** {format_quantity(wingspan * ureg.meter, units)}")
            measurements.append(
                f"> **Chest circumference:** {format_quantity(avg_chest_circumference * ureg.meter, units)}")
            measurements.append(
                f"> **Waist circumference:** {format_quantity(avg_waist_circumference * ureg.meter, units)}"
            )
            measurements.append(
                f"> **Leg circumference:** {format_quantity(max_leg_circumference * ureg.meter, units)}")

        elif b_type in [player.BodyType.SNAKE_MALE, player.BodyType.SNAKE_FEMALE]:
            # Snakes are measured by total length and maximum girth (chest/torso)
            total_length = this_player.get_full_length()
            measurements.append(f"> **Total length:** {format_quantity(total_length * ureg.meter, units)}")
            # For snakes, 'Chest' is their main girth indicator
            measurements.append(f"> **Maximum girth:** "
                                f"{format_quantity(avg_chest_circumference * ureg.meter, units)}")

        elif b_type in [player.BodyType.NAGA_MALE, player.BodyType.NAGA_FEMALE]:
            # Nagas have an upper humanoid body and a long lower tail
            tail_len = max((p.length for n, p in this_player.body.items() if 'tail' in n), default=0)
            measurements.append(f"> **Height:** {format_quantity(height * ureg.meter, units)}")
            measurements.append(
                f"> **Chest circumference:** {format_quantity(avg_chest_circumference * ureg.meter, units)}")
            if abs(avg_chest_circumference - avg_underbust_circumference) > 0.001:
                measurements.append(
                    f"> **Underbust:** {format_quantity(avg_underbust_circumference * ureg.meter, units)}")
            measurements.append(
                f"> **Waist circumference:** {format_quantity(avg_waist_circumference * ureg.meter, units)}"
            )
            measurements.append(
                f"> **Arm circumference:** {format_quantity(max_arm_circumference * ureg.meter, units)}")
            # Tail girth acts as the leg/lower body circumference equivalent for naga types
            tail_girth = max((p.circumference for n, p in this_player.body.items() if 'tail' in n),
                             default=max_leg_circumference)
            measurements.append(f"> **Tail length:** {format_quantity(tail_len * ureg.meter, units)}")
            measurements.append(f"> **Tail girth:** {format_quantity(tail_girth * ureg.meter, units)}")

        else:
            # Anthro/Humanoid standard measurements
            measurements.append(f"> **Height:** {format_quantity(height * ureg.meter, units)}")
            # Standard chest circumference (including protrusion)
            measurements.append(
                f"> **Chest circumference:** {format_quantity(avg_chest_circumference * ureg.meter, units)}")
            # Add Underbust only if it differs from the main chest circumference
            # We check if the difference is more than 1 millimeter to avoid precision artifacts
            if abs(avg_chest_circumference - avg_underbust_circumference) > 0.001:
                measurements.append(
                    f"> **Underbust:** {format_quantity(avg_underbust_circumference * ureg.meter, units)}")
            measurements.append(
                f"> **Waist circumference:** {format_quantity(avg_waist_circumference * ureg.meter, units)}"
            )
            measurements.append(
                f"> **Arm circumference:** {format_quantity(max_arm_circumference * ureg.meter, units)}")
            measurements.append(
                f"> **Leg circumference:** {format_quantity(max_leg_circumference * ureg.meter, units)}")

        # Mass is universal for all types
        measurements.insert(1, f"> **Mass:** {format_quantity(total_mass * ureg.kilogram, units)}")

        # Combine measurements into a single string
        measurements_str = "\n".join(measurements)

        stamina_section = util.get_stamina_display(this_player, units)

        # --- 1.5 FETCH SIZE RESERVE DATA ---
        # We retrieve the rule and check for the player's talent/eligibility
        current_rule = this_player.universe.rules.get("size_reserve", universe.SizeReserveRule.ENABLED)

        # Determine if the feature should be active for the current player
        size_reserve_active = False
        if current_rule == universe.SizeReserveRule.ENABLED:
            size_reserve_active = True
        elif current_rule == universe.SizeReserveRule.TALENT_REQUIRED:
            gs_data = this_player.talents.get("growth_spurt")
            size_reserve_active = gs_data is not None and getattr(gs_data, "tier", 0) > 0

        # --- 1. PREPARE RESERVE DISPLAY ---
        reserve_section = ""
        if size_reserve_active:
            reserve_text, show_grow, show_resist = util.get_size_reserve_display(this_player, units)
            if reserve_text:
                reserve_section = f"\n{reserve_text}"

        # --- 2. CONSTRUCT FINAL RESPONSE ---
        response = (
            f"### 📏 **{user.display_name}'s Measurements**\n"
            f"**Body type:** {b_type.value}\n"
            f"{measurements_str}\n"
            f"\n"
            f"**Build type:** {body_title}\n"
            f"└ `Muscle: {muscle_p:.1%} | Fat: {fat_p:.1%} | Fitness: {fitness_p:.1%}`\n"
            f"{nsfw_details}"
            f"\n"
            f"{stamina_section}\n"
            f"**Stomach:** {stomach_bar} **{stomach_ratio:.0%}**\n"
            f"└ `{stomach_text}`"
            f"{reserve_section}"  # Injected right under the stomach section
        )

        # Send the response
        embed = discord.Embed(description=response, color=0xBEBEFE)
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.set_footer(text="Legend: 🟥 Proteins | 🟦 Carbs | 🟧 Fats | ⬜ Chyme | ⬛ Empty")

        # --- 3. CONSTRUCT VIEW BASED ON UTIL FLAGS ---
        if size_reserve_active and (show_grow or show_resist) and user.id == ctx.author.id:
            # Build the view inside game.py using the flags returned from util
            reserve_view = SizeReserveActions(this_player, ctx, show_grow, show_resist)
            msg = await ctx.send(embed=embed, view=reserve_view)
            reserve_view.message = msg  # Inject message object for the background overflow timer
        else:
            await ctx.send(embed=embed)

    class InventoryView(discord.ui.View):
        """Creates buttons for each item in a player's inventory."""

        def __init__(self, grower):
            super().__init__(timeout=None)
            self.player = grower

            for thing in grower.get_inventory():
                self.add_item(Game.InventoryButton(thing, grower))

    class InventoryButton(discord.ui.Button):
        """A button that allows players to use an item."""

        def __init__(self, thing, grower):
            super().__init__(label=thing.name, style=discord.ButtonStyle.primary)
            self.item = thing
            self.player = grower

        async def callback(self, interaction: discord.Interaction):
            """Runs when the button is clicked."""
            if self.item in self.player.get_inventory():
                result = self.item.use(self.player)  # The use method should return a string
                embed = discord.Embed(description=result, color=0x00FF00)
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message("You no longer have this item.", ephemeral=True)

    inventory_group = app_commands.Group(name="inventory", description="Manage your inventory")

    @commands.hybrid_command(name="effects", description="Displays your effects")
    @require_player(allow_trapped=True, allow_overfilled=True)
    async def effects(self, ctx: Context, user: Member = None):
        """Shows the player's active effects, grouped by type with detailed descriptions."""
        if user is None:
            user = ctx.author
        this_player: player.Player = util.get_player_from_member(ctx, user)

        if not this_player.effects:
            embed = discord.Embed(
                title=f"{user.display_name}'s Effects",
                description="No active effects.",
                color=0x00FF00
            )
            await ctx.send(embed=embed)
            return

        # 1. Group effects by their EffectType enum object instead of raw value
        grouped_effects = {}
        for e in this_player.effects:
            e_type = e.effect_type
            if e_type not in grouped_effects:
                # We also store an instance reference to easily pull emoji and dynamic description later
                grouped_effects[e_type] = {
                    "count": 0,
                    "max_duration": 0,
                    "is_permanent": False,
                    "effect_ref": e
                }

            grouped_effects[e_type]["count"] += 1

            if e.duration is None:
                grouped_effects[e_type]["is_permanent"] = True
            elif not grouped_effects[e_type]["is_permanent"]:
                grouped_effects[e_type]["max_duration"] = max(grouped_effects[e_type]["max_duration"], e.duration)

        # 2. Format the grouped text using our Rich Enum properties
        lines = []
        for e_type, data in grouped_effects.items():
            count_str = f" x{data['count']}" if data['count'] > 1 else ""
            ref = data["effect_ref"]

            if data['is_permanent']:
                time_str = "*(Permanent)*"
            else:
                # Calculate timestamp based on the longest lasting effect in the stack
                # Note: Ensure 'datetime' is imported in this file
                expire_ts = int(
                    (datetime.datetime.now() + datetime.timedelta(seconds=data['max_duration'])).timestamp())
                time_str = f"*(expires <t:{expire_ts}:R>)*"

            # Construct a beautiful RPG-styled line: Emoji Name xCount time - Dynamic Description
            lines.append(f"{ref.emoji} **{e_type.display_name}**{count_str} {time_str}\n└ {ref.description}")

        embed = discord.Embed(
            title=f"{user.display_name}'s Active Effects",
            description="\n\n".join(lines),  # Using double newline for clean separation between different effects
            color=0x00FF00
        )
        await ctx.send(embed=embed)

    market_group = app_commands.Group(name="market", description="Commands for the universe market system")

    @market_group.command(name="list", description="List an item from your inventory onto the market")
    @app_commands.describe(
        index="The number of the item in your inventory",
        price="The price with units (e.g., '2 kg', '1.6 Mt', '500 pounds')"
    )
    @require_player(allow_trapped=False, allow_overfilled=False)
    async def market_list(self, interaction: discord.Interaction, index: int, price: str):
        """Lists an item for sale on the current universe's market."""
        ctx = await commands.Context.from_interaction(interaction)
        this_player = util.get_player_from_ctx(ctx)

        inventory = this_player.get_inventory()
        if index < 1 or index > len(inventory):
            await interaction.response.send_message("Invalid item number!", ephemeral=True)
            return

        try:
            parsed_price = util.ureg.Quantity(price)
        except Exception:
            await interaction.response.send_message(
                "Invalid price format! Please specify a number and unit (e.g., `2 kg`, `1.5 tons`, `500 mg`).",
                ephemeral=True
            )
            return

        try:
            price_in_kg = parsed_price.to('kg').magnitude
        except Exception:
            await interaction.response.send_message(
                "Invalid units! The price must be specified in units of mass (e.g., kg, grams, tons, pounds).",
                ephemeral=True
            )
            return

        if price_in_kg <= 0:
            await interaction.response.send_message("Price must be greater than zero!", ephemeral=True)
            return

        item = inventory.pop(index - 1)

        universe = this_player.universe
        if not hasattr(universe, 'market') or universe.market is None:
            universe.market = universe.market

        universe.market.list_item(seller_id=this_player.id, item=item, price=price_in_kg)

        embed = discord.Embed(
            title="Market Listing Created",
            description=f"Successfully listed **{item.name}**"
                        f" for **{util.format_quantity(price_in_kg * ureg.kg, this_player.units)}**.",
            color=0x00FF00
        )
        await interaction.response.send_message(embed=embed)

    @market_group.command(name="unlist", description="Remove your item from the market and return it to your inventory")
    @app_commands.describe(index="The number of your market offer to remove")
    @require_player(allow_trapped=False, allow_overfilled=False)
    async def market_unlist(self, interaction: discord.Interaction, index: int):
        """Removes a listing created by the player and returns the item to their inventory."""
        ctx = await commands.Context.from_interaction(interaction)
        this_player = util.get_player_from_ctx(ctx)

        universe = this_player.universe
        market = getattr(universe, 'market', None)

        if not market or index < 1 or index > len(market.offers):
            await interaction.response.send_message("Invalid market offer number!", ephemeral=True)
            return

        offer = market.offers[index - 1]

        # Verify that the player trying to unlist is the actual seller
        if offer.seller_id != this_player.id:
            await interaction.response.send_message("You can only remove your own listings!", ephemeral=True)
            return

        # Remove offer from the market
        market.remove_offer(offer)

        # Return the item to the player's inventory
        inventory = this_player.get_inventory()
        inventory.append(offer.item)

        embed = discord.Embed(
            title="Listing Removed",
            description=f"Successfully removed **{offer.item.name}** "
                        f"from the market and returned it to your inventory.",
            color=0x00FF00
        )
        await interaction.response.send_message(embed=embed)

    @market_group.command(name="show", description="Displays all items currently for sale on the market")
    @require_player(allow_trapped=True, allow_overfilled=True)
    async def market_show(self, interaction: discord.Interaction):
        ctx = await commands.Context.from_interaction(interaction)
        this_player = util.get_player_from_ctx(ctx)

        universe = this_player.universe
        market = getattr(universe, 'market', None)

        if not market or not market.offers:
            embed = discord.Embed(description="The market is currently empty!", color=0xFF0000)
            await interaction.response.send_message(embed=embed)
            return

        # Check if the current channel is marked as NSFW
        is_channel_nsfw = getattr(interaction.channel, 'nsfw', False)

        all_lines = []
        for i, offer in enumerate(market.offers):
            index_str = f"{i + 1}.".ljust(4)

            # Check if item is NSFW and channel is NOT NSFW
            if getattr(offer.item, 'nsfw', False) and not is_channel_nsfw:
                line1 = f"{index_str} [REDACTED]"
                line2 = f"{' ' * 5}"
            else:
                emoji_str = offer.item.emoji or ""
                emoji_count = len(emoji_str)

                spaces_needed = max(0, 6 - (emoji_count * 2))
                padding = " " * spaces_needed
                emoji_field = f"{emoji_str}{padding}"

                # Get the two-line market block from the item
                item_market_block = offer.item.get_market_line(offer.price, this_player.units)
                block_lines = item_market_block.split("\n")

                # Line 1: [Index] [Emoji] [Name]
                line1 = f"{index_str} {emoji_field} {block_lines[0]}"

                # Line 2: Indented so numerical values line up nicely under the name
                indent = " " * (4 + 1 + 6 + 1)  # length of index + space + emoji_field + space
                line2 = f"{indent}{block_lines[1]}"

            all_lines.append(f"{line1}\n{line2}")

        chunk_size = 6
        chunks = [all_lines[i:i + chunk_size] for i in range(0, len(all_lines), chunk_size)]
        total_pages = len(chunks)

        view = InventoryPaginator(
            interaction,
            chunks,
            total_pages,
            embed_title="⚖ Marketplace",
            embed_footer="Use /market buy <number> or /market examine <number>"
        )

        initial_embed = view.make_embed()
        if total_pages <= 1:
            await interaction.response.send_message(embed=initial_embed)
        else:
            await interaction.response.send_message(embed=initial_embed, view=view)

    @market_group.command(name="examine", description="Examine an item listed on the market")
    @app_commands.describe(index="The number of the market offer")
    @require_player(allow_trapped=True, allow_overfilled=True)
    async def market_examine(self, interaction: discord.Interaction, index: int):
        """Shows details about an item from the market using DRY principle."""
        ctx = await commands.Context.from_interaction(interaction)
        this_player = util.get_player_from_ctx(ctx)

        universe = this_player.universe
        market = getattr(universe, 'market', None)

        if not market or index < 1 or index > len(market.offers):
            await interaction.response.send_message("Invalid market offer number!", ephemeral=True)
            return

        offer = market.offers[index - 1]
        is_channel_nsfw = getattr(interaction.channel, 'nsfw', False)

        if getattr(offer.item, 'nsfw', False) and not is_channel_nsfw:
            embed = discord.Embed(title="[REDACTED]", description="[REDACTED]", color=0xFF0000)
        else:
            embed = discord.Embed(title=offer.item.name, description=offer.item.get_description(), color=0x00AAFF)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @market_group.command(name="buy", description="Buy an item from the market")
    @app_commands.describe(index="The number of the market offer to buy")
    @require_player(allow_trapped=False, allow_overfilled=False)
    async def market_buy(self, interaction: discord.Interaction, index: int):
        """Initiates the purchase of a market offer with a confirmation prompt."""
        ctx = await commands.Context.from_interaction(interaction)
        this_player = util.get_player_from_ctx(ctx)

        universe = this_player.universe
        market = getattr(universe, 'market', None)

        if not market or index < 1 or index > len(market.offers):
            await interaction.response.send_message("Invalid market offer number!", ephemeral=True)
            return

        offer = market.offers[index - 1]

        # Prevent buying NSFW items on non-NSFW channels
        is_channel_nsfw = getattr(interaction.channel, 'nsfw', False)
        if getattr(offer.item, 'nsfw', False) and not is_channel_nsfw:
            await interaction.response.send_message("???",
                                                    ephemeral=True)
            return

        # Prevent buying your own item
        if offer.seller_id == this_player.id:
            await interaction.response.send_message("You cannot buy your own item!", ephemeral=True)
            return

        # Check if buyer has enough troves before showing confirmation
        buyer_troves = getattr(this_player, "troves", 0.0)
        if buyer_troves < offer.price:
            await interaction.response.send_message(
                f"You don't have enough troves! Required: **{offer.price} kg**, available: **{buyer_troves} kg**.",
                ephemeral=True
            )
            return

        # Send confirmation view
        view = ConfirmBuyView(interaction, this_player, offer, market)
        embed = discord.Embed(
            title="Confirm Purchase",
            description=f"Do you really want to buy **{offer.item.name}** for **{offer.price} kg**?",
            color=0xFFA500
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @inventory_group.command(name="show", description="Displays your inventory")
    @require_player(allow_trapped=True, allow_overfilled=True)
    async def inventory_show(self, interaction: discord.Interaction):
        """Shows the player's inventory using an elegant, clickable paginator view."""
        ctx = await commands.Context.from_interaction(interaction)
        this_player = util.get_player_from_ctx(ctx)

        inventory = this_player.get_inventory()

        if not inventory:
            embed = discord.Embed(description="Your inventory is empty!", color=0xFF0000)
            await interaction.response.send_message(embed=embed)
            return

        # Check if the current channel is marked as NSFW
        is_channel_nsfw = getattr(interaction.channel, 'nsfw', False)

        # 1. Generate all inventory lines dynamically
        all_lines = []
        for i, thing in enumerate(inventory):
            index_str = f"{i + 1}.".ljust(4)

            # Check if item is NSFW and channel is NOT NSFW
            if getattr(thing, 'nsfw', False) and not is_channel_nsfw:
                line = f"{index_str} [REDACTED]"
            else:
                # 1. Get the clean aligned columns from the item object
                columns_text = thing.get_inventory_line(i + 1, this_player.units)

                # 3. DYNAMIC EMOJI ALIGNMENT (Taking 2-space width into account)
                emoji_str = thing.emoji or ""
                emoji_count = len(emoji_str)  # Counts logical characters

                visual_target = 6
                spaces_needed = visual_target - (emoji_count * 2)

                if spaces_needed < 0:
                    spaces_needed = 0

                padding = " " * spaces_needed
                emoji_field = f"{emoji_str}{padding}"

                # 4. Assemble the final perfectly aligned line
                line = f"{index_str} {emoji_field} {columns_text}"

            all_lines.append(line)

        # 2. Slice lines into clean chunks of 15 items per page
        chunk_size = 15
        chunks = [all_lines[i:i + chunk_size] for i in range(0, len(all_lines), chunk_size)]
        total_pages = len(chunks)

        # 3. Instantiate the View controller
        view = InventoryPaginator(interaction, chunks, total_pages)

        # 4. Generate the initial page (Page 1) embed
        initial_embed = view.make_embed()

        # 5. Send the response. If there's only 1 page, buttons will be hidden or disabled automatically
        if total_pages <= 1:
            await interaction.response.send_message(embed=initial_embed)
        else:
            await interaction.response.send_message(embed=initial_embed, view=view)

    @inventory_group.command(name="use", description="Use an item from your inventory")
    @app_commands.describe(index="The number of the item in your inventory")
    @require_player(allow_trapped=False, allow_overfilled=False)
    async def inventory_use(self, interaction: discord.Interaction, index: int):
        """Uses an item from the inventory by its list number."""
        ctx = await commands.Context.from_interaction(interaction)
        this_player = util.get_player_from_ctx(ctx)

        inventory = this_player.get_inventory()
        if index < 1 or index > len(inventory):
            await interaction.response.send_message("Invalid item number!", ephemeral=True)
            return

        thing = inventory[index - 1]

        # Prevent using NSFW items on non-NSFW channels
        is_channel_nsfw = getattr(interaction.channel, 'nsfw', False)
        if getattr(thing, 'nsfw', False) and not is_channel_nsfw:
            await interaction.response.send_message("You cannot use restricted items on a non-NSFW channel!",
                                                    ephemeral=True)
            return

        result = thing.use(this_player)  # Calls the item's use method
        embed = discord.Embed(description=result, color=0x00FF00)
        await interaction.response.send_message(embed=embed)

    @inventory_group.command(name="examine", description="Examine an item in your inventory")
    @app_commands.describe(index="The number of the item in your inventory")
    @require_player(allow_trapped=True, allow_overfilled=True)
    async def inventory_examine(self, interaction: discord.Interaction, index: int):
        """Shows details about an item from the inventory."""
        ctx = await commands.Context.from_interaction(interaction)
        this_player = util.get_player_from_ctx(ctx)

        inventory = this_player.get_inventory()
        if index < 1 or index > len(inventory):
            await interaction.response.send_message("Invalid item number!", ephemeral=True)
            return

        thing = inventory[index - 1]
        is_channel_nsfw = getattr(interaction.channel, 'nsfw', False)

        if getattr(thing, 'nsfw', False) and not is_channel_nsfw:
            embed = discord.Embed(title="[REDACTED]", description="[REDACTED]", color=0xFF0000)
        else:
            embed = discord.Embed(title=thing.name, description=thing.get_description(), color=0x00AAFF)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @inventory_group.command(name="delete", description="Delete an item from your inventory")
    @app_commands.describe(index="The number of the item in your inventory")
    @require_player(allow_trapped=True, allow_overfilled=True)
    async def inventory_delete(self, interaction: discord.Interaction, index: int):
        """Asks for confirmation before deleting an item."""
        ctx = await commands.Context.from_interaction(interaction)
        this_player = util.get_player_from_ctx(ctx)

        inventory = this_player.get_inventory()
        if index < 1 or index > len(inventory):
            await interaction.response.send_message("Invalid item number!", ephemeral=True)
            return

        thing = inventory[index - 1]
        is_channel_nsfw = getattr(interaction.channel, 'nsfw', False)

        # Prevent deleting/interacting with NSFW items on non-NSFW channels if desired,
        # or redact the name in the confirmation prompt
        item_name_display = "[REDACTED]" if (getattr(thing, 'nsfw', False) and not is_channel_nsfw) else thing.name

        # Send a confirmation message with buttons
        view = ConfirmDeleteView(interaction, this_player, thing, index - 1)
        embed = discord.Embed(
            description=f"Are you sure you want to delete **{item_name_display}**?",
            color=0xFF0000
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @commands.hybrid_command(name="brew", description="Brew a magical potion and add it to your inventory.")
    @require_player(allow_trapped=False, allow_overfilled=False)
    async def brew(self, ctx: commands.Context):
        this_player = util.get_player_from_ctx(ctx)

        if ctx.interaction is None:
            await ctx.send("This command must be used as a slash command!")
            return

        alchemist_data = this_player.talents.get("alchemist")
        alchemist_tier = alchemist_data.tier if alchemist_data else 0

        if alchemist_tier <= 0:
            await ctx.interaction.response.send_message(
                "You do not possess the Alchemist talent required to brew potions!", ephemeral=True)
            return

        AVAILABLE_POTIONS = {
            "stamina": item.stamina_potion,
            "fat": item.fat_potion,
            "muscle": item.muscle_potion,
            "fitness": item.fitness_potion,
            "breast": item.breast_growth_potion,
            "cooking": item.inspired_cooking_potion,
            "ravenous": item.ravenous_potion
        }

        is_channel_nsfw = getattr(ctx.interaction.channel, 'nsfw', False)

        if not is_channel_nsfw:
            AVAILABLE_POTIONS = {
                k: v for k, v in AVAILABLE_POTIONS.items()
                if not getattr(v, 'nsfw', False)
            }

        view = BrewPotionView(AVAILABLE_POTIONS, this_player, this_player.units)
        embed = discord.Embed(
            title="🧪 Alchemical Workbench",
            description="Select the potion you wish to brew from the dropdown menu below.",
            color=0x9900FF
        )
        await ctx.interaction.response.send_message(embed=embed, view=view, ephemeral=False)

    @commands.hybrid_command(name="cook", description="Cook a meal and add it to your inventory.")
    @require_player(allow_trapped=False, allow_overfilled=False)
    async def cook(self, ctx: commands.Context):
        this_player = util.get_player_from_ctx(ctx)

        if ctx.interaction is None:
            await ctx.send("This command must be used as a slash command!")
            return

        await ctx.interaction.response.send_modal(CookMealModal(this_player, this_player.units))

    @commands.hybrid_command(name="breakfast", description="Energy for the day.")
    @require_player(allow_trapped=False, allow_overfilled=False)
    async def breakfast(self, ctx: Context):
        await meal(ctx, "Breakfast")

    @commands.hybrid_command(name="lunch", description="Protein-rich meal.")
    @require_player(allow_trapped=False, allow_overfilled=False)
    async def lunch(self, ctx: Context):
        await meal(ctx, "Lunch")

    @commands.hybrid_command(name="dinner", description="Filling dinner.")
    @require_player(allow_trapped=False, allow_overfilled=False)
    async def dinner(self, ctx: Context):
        await meal(ctx, "Dinner")

    @commands.hybrid_command(name="dessert", description="A sweet treat!")
    @require_player(allow_trapped=False, allow_overfilled=False)
    async def dessert(self, ctx: Context):
        await meal(ctx, "Dessert")

    @commands.hybrid_command(name="units", description="Set your preferred unit system.")
    @require_player(allow_trapped=True, allow_overfilled=True)
    async def units(self, ctx: commands.Context):
        """Handles the /units hybrid command with proper message tracking."""
        grower = util.get_player_from_ctx(ctx)

        embed = discord.Embed(
            title="🌍 Choose Your Unit System",
            description=(
                "Select your preferred measurement system:\n\n"
                "🔹 **Metric**\n*Meters, kilograms, liters.*\n\n"
                "🔹 **US Customary**\n*Feet, pounds, gallons.*\n\n"
                "🔹 **Prussian**\n*Fuß, Pfund, Quart.*"
            ),
            color=discord.Color.blue()
        )

        view = UnitSelectionView(grower)
        # Here is the vital step: we capture the message and store it in the view.
        view.message = await ctx.send(embed=embed, view=view)

    # --- MAIN HYBRID COMMAND ---
    @commands.hybrid_command(name="workout", description="Open the training panel to exercise")
    @require_player(allow_trapped=False, allow_overfilled=False)
    async def workout(self, ctx: commands.Context):
        """Opens an interactive embed menu to select and execute workouts."""
        this_player: player.Player = util.get_player_from_ctx(ctx)

        # Create the interaction view instance
        view = WorkoutInterface(self, this_player)

        embed = discord.Embed(
            title="🏋️ Workout",
            description="Choose your workout type:",
            color=0x3498db
        )

        await ctx.send(embed=embed, view=view)

    @commands.hybrid_command(name="give_item",
                             description="[ADMIN] Gives a specified item to a chosen player in a given amount.")
    @commands.has_permissions(administrator=True)
    async def give_item(self, ctx: commands.Context, member: discord.Member, amount: int = 1):
        """
        Grants a predefined administrative item (such as the stamina potion)
        to the target player in the requested quantity.
        """
        # Retrieve the player object from the Discord member using util helper
        target_player = util.get_player_from_member(ctx, member)

        if not target_player:
            await ctx.send(f"Could not find a registered player profile for {member.display_name}.", ephemeral=True)
            return

        # Instantiate the item to be given (e.g., Stamina Potion)
        # Creating a fresh potion instance for the transfer
        for _ in range(amount):
            stamina_potion = Potion(
                name="Elixir of Stamina",
                value=15.0,
                size=0.01 * target_player.get_mass(),
                tier=1,
                effects_data={
                    EffectType.STAMINA_SURGE: 0.0
                },
                emoji="🧪"
            )
            target_player.add_item(stamina_potion)

        await ctx.send(f"Successfully gave {amount}x {stamina_potion.full_name} to {member.mention}.")

    @commands.hybrid_command(name="debug_set_height",
                             description="[ADMIN] Sets player height and scales anatomy accordingly.")
    @commands.has_permissions(administrator=True)
    async def admin_set_height(self, ctx: commands.Context, height_str: str, member: discord.Member = None):
        target = member if member else ctx.author
        this_player: player.Player = util.get_player_from_member(ctx, target)

        if not this_player:
            await ctx.send(f"❌ Target **{target.display_name}** does not have a character.", ephemeral=True)
            return

        try:
            parsed_height = util.ureg.Quantity(height_str)
            target_height = parsed_height.to('meter').magnitude
        except Exception:
            await ctx.send("❌ Invalid height format! Please provide a valid quantity (e.g., `7 feet`, `200 cm`).",
                           ephemeral=True)
            return

        height_before = this_player.get_height()
        mass_before = this_player.get_mass()
        fat_before = this_player.get_fat_ratio()

        if height_before <= 0:
            await ctx.send("❌ Current height calculation failed (height is zero or negative).", ephemeral=True)
            return

        if target_height <= 0:
            await ctx.send("❌ Target height must be greater than zero.", ephemeral=True)
            return

        scale_factor = target_height / height_before

        this_player.scale_all_body_parts(scale_factor)

        if this_player.stamina > this_player.max_stamina:
            this_player.stamina = this_player.max_stamina

        for part_name, part in this_player.body.items():
            if 'torso' in part_name:
                capacity = part.stomach_capacity
                current_content = part.stomach_content
                if current_content > capacity and current_content > 0:
                    overflow_factor = capacity / current_content
                    part.protein_content *= overflow_factor
                    part.carbohydrates_content *= overflow_factor
                    part.fat_content *= overflow_factor
                    part.metabolic_chyme *= overflow_factor

        height_after = this_player.get_height()
        mass_after = this_player.get_mass()
        fat_after = this_player.get_fat_ratio()

        report_text = util.get_growth_report(
            mass_before=mass_before,
            mass_after=mass_after,
            height_before=height_before,
            height_after=height_after,
            fat_ratio_before=fat_before,
            fat_ratio_after=fat_after,
            units=this_player.units
        )

        if not report_text:
            report_text = "No significant physical changes detected."

        final_report = (
            f"⚖️ **Height & Mass Adjusted for {target.display_name}**\n"
            f"{report_text}"
        )

        await ctx.send(final_report, ephemeral=True)


    @commands.hybrid_command(name="debug_digest", description="[ADMIN] Manually triggers digestion for a player.")
    @commands.has_permissions(administrator=True)
    async def admin_digest(self, ctx: commands.Context, seconds: float, member: discord.Member = None):
        """
        Forces the digestion process for a specific player or the caller.
        Usage: /admin_digest seconds:3600 member:@user
        """
        # 1. Determine target player
        target = member if member else ctx.author
        this_player: player.Player = util.get_player_from_member(ctx, target)

        if not this_player:
            await ctx.send(f"❌ Target **{target.display_name}** does not have a character.", ephemeral=True)
            return

        # 2. Capture state before digestion for the report
        old_protein = sum(t.protein_content for t in this_player.body.values() if hasattr(t, 'protein_content'))
        old_stamina = this_player.stamina

        # 3. Execute the digestion function
        # English: We pass delta_time (seconds) to simulate time passing in the metabolic system.
        this_player.digest(seconds)

        # 4. Capture state after digestion
        new_protein = sum(t.protein_content for t in this_player.body.values() if hasattr(t, 'protein_content'))
        new_stamina = this_player.stamina

        protein_gain = new_protein - old_protein
        stamina_gain = new_stamina - old_stamina

        # 5. Build the admin report
        units = this_player.units
        embed = discord.Embed(
            title="✨ Admin Metabolic Override",
            description=f"Simulated **{seconds}** seconds of digestion for **{target.display_name}**.",
            color=0xFFD700  # Gold color for admin commands
        )

        embed.add_field(
            name="Protein Change",
            value=f"**{util.format_quantity(protein_gain * ureg.kilogram, units)}**"
        )
        embed.add_field(
            name="Stamina Change",
            value=f"**{util.format_quantity(stamina_gain * ureg.joule, units)}**"
        )

        # Display the current stamina bar after the skip
        stamina_bar = util.get_stamina_display(this_player, units)
        embed.add_field(name="Final Condition", value=stamina_bar, inline=False)

        await ctx.send(embed=embed)

    # Error handling for missing permissions
    @admin_digest.error
    async def admin_digest_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("⛔ You don't have required permissions!",
                           ephemeral=True)

    @commands.hybrid_command(name="debug_move_mass", description="[ADMIN] Move muscle or fat between body parts.")
    @commands.has_permissions(administrator=True)
    async def debug_move_mass(
            self,
            ctx: commands.Context,
            target_player: discord.Member,
            target_part: str,
            amount_kg: float,
            tissue_type: str = "muscle"
    ):
        grower = util.get_player_from_id(ctx, target_player.id)
        if not grower:
            return await ctx.send(f"❌ No data for {target_player.display_name}.", ephemeral=True)

        tissue_type = tissue_type.lower()
        if tissue_type not in ["muscle", "fat"]:
            return await ctx.send("❌ Use 'muscle' or 'fat'.", ephemeral=True)

        if target_part not in grower.body:
            return await ctx.send(f"❌ Part '{target_part}' not found.", ephemeral=True)

        # Identify target parts and handle symmetry via mirror object reference
        target_names = [target_part]
        target_obj = grower.body[target_part]
        mirror_obj = target_obj.mirror

        is_mirrored = False
        if mirror_obj:
            # Find the dictionary key associated with the mirror object
            mirror_name = next((name for name, obj in grower.body.items() if obj == mirror_obj), None)

            if mirror_name and mirror_name in grower.body:
                target_names.append(mirror_name)
                amount_per_target = amount_kg / 2
                is_mirrored = True
            else:
                amount_per_target = amount_kg
        else:
            amount_per_target = amount_kg

        # Collect available mass from donor parts
        donors = [p for name, p in grower.body.items() if name not in target_names]
        total_available = sum(getattr(p, f"{tissue_type}_mass") for p in donors)

        if amount_kg > total_available:
            return await ctx.send(
                f"❌ Not enough {tissue_type}! (Available: {total_available:.2f} kg)",
                ephemeral=True
            )

        # Redistribute mass by pulling proportionally from donors
        for p in donors:
            current_val = getattr(p, f"{tissue_type}_mass")
            reduction = (current_val / total_available) * amount_kg
            setattr(p, f"{tissue_type}_mass", current_val - reduction)

        # Apply the mass to the target parts
        for name in target_names:
            t_obj = grower.body[name]
            current_val = getattr(t_obj, f"{tissue_type}_mass")
            setattr(t_obj, f"{tissue_type}_mass", current_val + amount_per_target)

        # Final mass check using the preferred getter
        final_mass = grower.get_mass()
        symmetry_note = " (Symmetric transfer applied)" if is_mirrored else ""

        embed = discord.Embed(
            title=f"🔧 Body Sculpting: {target_player.display_name}",
            description=(
                f"Moved **{amount_kg} kg** of **{tissue_type}** to **{', '.join(target_names)}**{symmetry_note}.\n\n"
                f"**Current Total Mass:** {final_mass:.2f} kg"
            ),
            color=0xe74c3c
        )

        await ctx.send(embed=embed)

    # Error handling for permissions
    @debug_move_mass.error
    async def debug_move_mass_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("⛔ This command is reserved for administrators only.", ephemeral=True)

    @commands.hybrid_command(name="set_reserve_pct", description="[ADMIN] Sets player's size reserve to a specific "
                                                                 "percentage of base capacity.")
    @commands.has_permissions(administrator=True)
    async def set_reserve_pct(self, ctx: commands.Context, percentage: float):
        # 1. Fetch the player object using the unified context
        grower = util.get_player_from_ctx(ctx)

        if not grower:
            return await ctx.send("❌ Player data not found!", ephemeral=True)

        # 2. Calculate what 100% of clean base capacity means for this specific player
        # Based on your formula: base_max = current_mass / 6
        base_max_capacity = grower.get_base_mass() / 6
        max_capacity = grower.max_size_reserve

        if base_max_capacity <= 0:
            return await ctx.send("❌ Player has an invalid base mass!", ephemeral=True)

        # 3. Convert percentage to raw mass value (e.g., 150% -> 1.5 * base_max)
        multiplier = percentage / 100.0
        target_raw_reserve = max_capacity * multiplier

        # 4. Force-inject the new value directly into the player state
        grower.size_reserve = target_raw_reserve

        # 5. Format outputs nicely using the player's preferred system of units
        units = grower.units
        formatted_reserve = util.format_quantity(target_raw_reserve * ureg.kg, units)
        formatted_base_max = util.format_quantity(base_max_capacity * ureg.kg, units)

        # 6. Build a comprehensive breakdown for the administrator
        debug_embed = discord.Embed(
            title="🔧 Debug: Size Reserve Altered (Hybrid)",
            description=(
                f"Successfully manipulated the fabric of reality for <@{grower.id}>.\n\n"
                f"📊 **Requested Percentage:** `{percentage:.1f}%` of base capacity\n"
                f"⚖️ **Calculated 100% Base Max:** `{formatted_base_max}`\n"
                f"🔋 **New Current Reserve:** `{formatted_reserve}`\n\n"
            ),
            color=0xFF5555
        )

        # Unified context 'send' seamlessly handles both interaction responses and chat messages
        await ctx.send(embed=debug_embed, ephemeral=False)

    @commands.hybrid_command(name="set_reserve_boost",
                             description="[ADMIN] Clears current reserve boosts and sets a new one with specified "
                                         "power.")
    @commands.has_permissions(administrator=True)
    async def set_reserve_boost(self, ctx: commands.Context, power: float):
        grower = util.get_player_from_ctx(ctx)

        if not grower:
            return await ctx.send("❌ Player data not found!", ephemeral=True)

        while grower.remove_single_effect_by_type(effect.EffectType.RESERVE_BOOST):
            pass

        if power > 0.0:
            new_boost_effect = effect.Effect(
                effect_type=effect.EffectType.RESERVE_BOOST,
                power=power,
                duration=None,
                stackable=False,
                creator_id=grower.id
            )
            grower.add_effect_instance(new_boost_effect)

        debug_embed = discord.Embed(
            title="🔧 Debug: Reserve Boost Altered (Hybrid)",
            description=(
                f"Successfully manipulated the fabric of reality for <@{grower.id}>.\n\n"
                f"⚡ **New Reserve Boost Power:** `{power:.4f}`\n\n"
            ),
            color=0xFF5555
        )

        await ctx.send(embed=debug_embed, ephemeral=False)

    @commands.hybrid_command(name="clear_effects",
                             description="[ADMIN] Clears all active effects from the player.")
    @commands.has_permissions(administrator=True)
    async def clear_effects(self, ctx: commands.Context):
        grower = util.get_player_from_ctx(ctx)

        if not grower:
            return await ctx.send("❌ Player data not found!", ephemeral=True)

        grower.clear_all_effects()

        debug_embed = discord.Embed(
            title="🔧 Debug: Effects Cleared",
            description=f"Successfully removed all active effects for <@{grower.id}>.",
            color=0xFF5555
        )

        await ctx.send(embed=debug_embed, ephemeral=False)

    @app_commands.command(name="admin_rules", description="Manage universe rules and coefficients")
    @app_commands.checks.has_permissions(administrator=True)
    async def admin_rules(self, interaction: discord.Interaction):
        # Fetch the universe instance for this player
        this_player = util.get_player_from_interaction(interaction)
        if not this_player or not this_player.universe:
            await interaction.response.send_message("Universe not found!", ephemeral=True)
            return

        view = AdminRulesView(this_player.universe)
        await interaction.response.send_message(
            "## 🛠️ Admin Universe Settings\nSelect a rule from the menu below to modify its value.",
            view=view,
            ephemeral=True
        )

    @commands.hybrid_command(name="hero", description="Help some people using your size")
    async def hero(self, ctx: commands.Context):
        # We call the core logic and pass ctx
        await ctx.defer()
        await execute_event(ctx, "hero")

    @commands.hybrid_command(name="rampage", description="Dominate your surroundings with the use of your size")
    async def rampage(self, ctx: commands.Context):
        await ctx.defer()
        await execute_event(ctx, "rampage")

    @commands.hybrid_command(name="work", description="Earn some troves")
    async def work(self, ctx: commands.Context):
        await ctx.defer()
        await execute_event(ctx, "work")


async def setup(bot: commands.Bot) -> None:
    """Adds the Game cog and syncs commands, but does NOT register interactions again."""
    await bot.add_cog(Game(bot))  # No duplicate registration here
