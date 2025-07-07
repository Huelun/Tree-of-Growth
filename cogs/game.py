import datetime

import discord
import pint
import pytz
from discord import Member, app_commands
from discord.ext import commands
from discord.ext.commands import Context

from cogs import item, universe, util
import player
from cogs.effect import EffectType
from cogs.interaction_system import PlayerInteractionView
from player import UnitSystem
from cogs.util import format_quantity


async def meal(ctx: Context):
    grower: player.Player = util.get_player_from_ctx(ctx)
    if grower is None:
        embed = discord.Embed(description="Touch the tree first!", color=0xBEBEFE)
        await ctx.send(embed=embed)
        return
    amount = grower.get_mass() / 51 / 5
    weight_before = grower.get_mass()
    height_before = grower.get_height()
    units = grower.units
    if grower.can_eat(amount):
        grower.feed(amount)
        delta_h = format_quantity((grower.get_height() - height_before) * ureg.m, units)
        delta_w = format_quantity((grower.get_mass() - weight_before) * ureg.kg, units)
        message = f"You have grown {delta_h} in height and became {delta_w} more massive."
    else:
        message = "You are too full to eat."
    await ctx.send(embed=discord.Embed(description=message, color=0xBEBEFE))


def get_meal_for_time(user_timezone: str) -> str:
    try:
        # Get the user's timezone object from pytz
        tz = pytz.timezone(user_timezone)

        # Get the current time in the user's timezone
        now = datetime.datetime.now(tz)

        # Get the current hour
        hour = now.hour

        # Determine the meal based on the time of day
        if hour < 6:
            return "Late Night Snack"
        if hour < 10:
            return "Breakfast"  # For those early risers, a little meal before the main breakfast
        elif hour < 11:
            return "Second Breakfast"  # Typical breakfast time
        elif hour == 11:
            return "Elevenses"  # A small snack around 11 AM, often a tea break
        elif hour == 12:
            return "Brunch"  # Late breakfast, early lunch
        elif hour < 16:
            return "Lunch"  # Midday meal
        elif hour == 16:
            return "Dessert"  # Dessert after dinner or late-night treat
        elif hour == 17:
            return "Afternoon Tea"  # A light meal or snack around 3-5 PM, typically with tea
        elif hour < 21:
            return "Dinner"  # Main meal of the day, usually around evening
        elif hour == 21:
            return "Post-Dinner Treat"  # A small snack or treat after the late-night supper
        elif hour == 22:
            return "Supper"  # Light evening meal, often after dinner
        elif hour == 23:
            return "Something Special"
        else:
            return "Midnight Feast"  # Late-night meal for the night owls

    except pytz.UnknownTimeZoneError:
        return "Invalid time zone provided. Please use a valid time zone."


class CookMealModal(discord.ui.Modal, title="Cook a Meal"):
    """A form that lets players cook a meal with full unit support using Pint."""

    meal_name = discord.ui.TextInput(label="Meal Name", placeholder="Enter the name of your meal", max_length=45)
    meal_size = discord.ui.TextInput(label="Meal Size (e.g., 2 kg, 500 g, 1.5 lbs)",
                                     style=discord.TextStyle.short)

    def __init__(self, grower, unit_system: UnitSystem = UnitSystem.METRIC):
        """
        :param grower: The player creating the meal.
        :param unit_system: The unit system for displaying results.
        """
        super().__init__()
        self.player = grower
        self.unit_system = unit_system
        self.min_size_kg = grower.get_mass() / 2196
        self.max_size_kg = grower.get_mass() / 6
        self.max_name_length = 45

    def parse_meal_size(self, input_size: str) -> float:
        """
        Parses a meal size input with any mass unit supported by Pint.
        Converts everything to kilograms.
        """
        input_size = input_size.strip().lower()
        input_size = input_size.replace(',', '.')

        try:
            quantity = ureg(input_size).to("kg")  # Convert to kilograms
            value_kg = quantity.magnitude  # Extract numeric value

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

    async def on_submit(self, interaction: discord.Interaction):
        """Handles the form submission."""
        try:
            # Format the meal name and remove article (if it exists)
            meal_name_value = self.meal_name.value.strip().lower()

            # Remove article if it exists at the start of the meal name
            articles = ["a", "an"]
            meal_name_value = ' '.join(meal_name_value.split()[1:]) if meal_name_value.split()[
                                                                           0] in articles else meal_name_value

            # Get the meal emoji and formatted meal name
            meal_emoji = util.food_to_emoji(meal_name_value)
            meal_name = meal_name_value.capitalize()

            # Parse the meal size in kilograms
            size_kg = self.parse_meal_size(self.meal_size.value)

            # Create a new meal (tier = 0 for now, ignoring fat & protein)
            new_meal = item.Food(name=meal_name, value=0, size=size_kg, tier=0, protein=0, fat=0, emoji=meal_emoji)
            self.player.add_item(new_meal)  # Ensure this method exists

            embed = discord.Embed(
                title="Meal Cooked! 🍽️",
                description=f"You have cooked **{util.get_article(new_meal.full_name)}** "
                            f"(Size: {format_quantity(new_meal.size * ureg.kg, self.unit_system)}) and added it to "
                            f"your inventory!",
                color=0x00FF00
            )
            await interaction.response.send_message(embed=embed)

        except ValueError as e:
            await interaction.response.send_message(str(e), ephemeral=True)


class UnitSelection(discord.ui.Select):
    """Dropdown menu for selecting a unit system."""

    def __init__(self, grower):
        self.player = grower
        # Use the player's ID or another unique identifier to track the player
        self.player_id = grower.id  # Assuming `grower` is a player object with an `id` attribute
        options = [
            discord.SelectOption(label="Metric", description=str(UnitSystem.METRIC.value), value="METRIC"),
            discord.SelectOption(label="US Customary", description=str(UnitSystem.US_CUSTOMARY.value),
                                 value="US_CUSTOMARY"),
        ]
        super().__init__(placeholder="Choose your preferred unit system", options=options)

    async def callback(self, interaction: discord.Interaction):
        """Handles unit selection."""
        # Ensure that the interaction is coming from the correct player
        if interaction.user.id != self.player_id:
            return await interaction.response.send_message(
                "This selection is not for you.", ephemeral=True
            )

        # Acknowledge the interaction first (this prevents the interaction from timing out)
        await interaction.response.defer()

        unit_choice = player.UnitSystem[self.values[0]]  # Convert string to Enum
        self.player.set_unit_preference(unit_choice)

        embed = discord.Embed(
            title="✅ Unit Preference Updated",
            description=f"You have selected **{unit_choice.value}** as your preferred unit system.",
            color=discord.Color.green(),
        )

        # Send follow-up message after deferring the interaction
        await interaction.followup.send(embed=embed, ephemeral=True)

        # Optionally disable the view after selection to prevent further interaction
        self.view.stop()  # This will stop the view and prevent any further interactions


class UnitSelectionView(discord.ui.View):
    """View that contains the UnitSelection dropdown menu."""

    def __init__(self, grower):
        super().__init__()
        self.add_item(UnitSelection(grower))

    async def on_timeout(self):
        """This will stop the view if it times out (no selection)."""
        for thing in self.children:
            thing.disabled = True  # Disable all items when the view times out
        await self.message.edit(view=self)  # Update the message to reflect the disabled state


async def check_player_and_send_embed(ctx) -> player.Player:
    """
    Checks if a player instance exists in the context. If not, sends an embed with a message.
    Returns the player if it exists or None.
    """
    # Get player instance from the context
    this_player: player.Player = util.get_player_from_ctx(ctx)

    if this_player is None:
        embed = discord.Embed(description="Touch the Tree of Growth first!", color=0xBEBEFE)
        await ctx.send(embed=embed)
        return None

    # Return the player instance if found
    return this_player


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
            effect_sender=(EffectType.HUGGED, 1, 3600),
            effect_recipient=(EffectType.HUGGED, 1, 3600)
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
            effect_recipient=(EffectType.BELLY_RUBBED, 1, 7200)
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

    async def handle_interaction(self, interaction: discord.Interaction, target: discord.Member, embed_title: str,
                                 embed_description: str, success_embed: discord.Embed, failure_embed: discord.Embed,
                                 effect_sender=None, effect_recipient=None,
                                 custom_function=None):
        """Handles the logic for when the interaction is executed."""

        sender = interaction.user
        if sender.id == target.id:
            await interaction.response.send_message("You can't interact with yourself!", ephemeral=True)
            return

        # Replace the placeholders in the embed description with the sender's information
        embed_description = embed_description.format(sender=sender.display_name)

        embed = discord.Embed(
            title=embed_title,
            description=embed_description,
            color=0xFFD700
        )

        # Send the message with the embed and an interaction view (button to accept/deny)
        await interaction.response.send_message(content=target.mention, embed=embed,
                                                view=PlayerInteractionView(
                                                    initiator=sender,
                                                    recipient=target,
                                                    effect_initiator=effect_sender,
                                                    effect_recipient=effect_recipient,
                                                    custom_function=custom_function,
                                                    success_embed=success_embed,  # Pass custom success embed
                                                    failure_embed=failure_embed  # Pass custom failure embed
                                                ))

    async def duel_logic(self, interaction: discord.Interaction, sender: discord.Member, recipient: discord.Member):
        """Handles a duel between two players."""
        embed = discord.Embed(
            title="⚔️ Duel Results!",
            description=f"**{sender.display_name}** and **{recipient.display_name}** faced off in an epic duel!",
            color=0xFF0000
        )
        await interaction.channel.send(embed=embed)

    @commands.hybrid_command(
        name="touchtree", description="Join the game and receive the blessing of growth."
    )
    async def touchtree(self, context: Context) -> None:
        this_universe: universe.Universe = universe.multiverse_instance.get_universe_from_id(context.channel.id)
        if this_universe is None:
            embed = discord.Embed(description="A universe doesn't exist here.", color=0xBEBEFE)
            await context.send(embed=embed)
        else:
            this_player_id = context.author.id
            if any(grower.id == this_player_id for grower in this_universe.players):
                embed = discord.Embed(description="You are already blessed with growth.", color=0xBEBEFE)
                await context.send(embed=embed)
            else:
                this_universe.players.add(player.Player(this_player_id))
                await context.send("You shall grow!")

    @commands.hybrid_command(
        name="createuniverse", description="Create a new, isolated universe."
    )
    @commands.is_owner()
    async def createuniverse(self, context: Context, *, name: str) -> None:
        if universe.multiverse_instance.get_universe_from_id(context.channel.id):
            embed = discord.Embed(description="A universe already exists in this channel.", color=0xBEBEFE)
        else:
            universe.multiverse_instance.create_universe(context.channel.id, name)
            embed = discord.Embed(description="Created a new universe.", color=0xBEBEFE)
        await context.send(embed=embed)

    @commands.hybrid_command(name="size", description="Check your height, weight and other measurements.")
    @app_commands.describe(user="The user whose measurements you want to see")
    async def size(self, ctx: commands.Context, user: Member = None):
        author_player = util.get_player_from_member(ctx, ctx.author)
        if user is None:
            user = ctx.author
            this_player: player.Player = util.get_player_from_ctx(ctx)
        else:
            user = user
            this_player: player.Player = util.get_player_from_member(ctx, user)
        if this_player is None:
            embed = discord.Embed(description="Touch the tree first!", color=0xBEBEFE)
            await ctx.send(embed=embed)
            return
        else:
            pass
        player.check_serializability(this_player)
        total_weight = this_player.get_mass()
        torso_circumferences = []
        arm_circumferences = []
        leg_circumferences = []
        stomach_content = 0
        stomach_capacity = 0

        # Iterate through body parts
        for part_name, part in this_player.body.items():
            # Collect circumferences
            if hasattr(part, 'waist_c'):
                torso_circumferences.append(part.waist_c)
            if hasattr(part, 'wide_c') and 'arm' in part_name:
                arm_circumferences.append(part.wide_c)
            if hasattr(part, 'wide_c') and 'leg' in part_name:
                leg_circumferences.append(part.wide_c)
            if hasattr(part, 'stomach_content') and hasattr(part, 'stomach_capacity'):
                stomach_content += part.stomach_content
                stomach_capacity += part.stomach_capacity

        # Calculate height: torso, neck, and head lengths plus longest leg length
        height = this_player.get_height()

        # Calculate average or max values for circumferences, with fallback
        avg_torso_circumference = sum(torso_circumferences) / len(
            torso_circumferences) if torso_circumferences else 0
        max_arm_circumference = max(arm_circumferences) if arm_circumferences else 0
        max_leg_circumference = max(leg_circumferences) if leg_circumferences else 0

        # Format the output message with additional dimensions
        units = author_player.units
        response = (
            f"**{user.display_name}'s measurements**\n"
            f"Height: {format_quantity(height * ureg.meter, units)}\n"
            f"Weight: {format_quantity(total_weight * ureg.kilogram, units)}\n"
            f"Chest Circumference: {format_quantity(avg_torso_circumference * ureg.meter, units)}\n"
            f"Arm Circumference: {format_quantity(max_arm_circumference * ureg.meter, units)}\n"
            f"Leg Circumference: {format_quantity(max_leg_circumference * ureg.meter, units)}\n"
            f"Stomach Content: {format_quantity(stomach_content * ureg.liter, units)} / {format_quantity(stomach_capacity * ureg.liter, units)}\n "
        )
        # Send the response
        await ctx.send(embed=discord.Embed(description=response, color=0xBEBEFE))

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
    async def effects(self, ctx: Context, user: Member = None):
        """Shows the player's inventory as a numbered list."""
        if user is None:
            user = ctx.author
            this_player = await check_player_and_send_embed(ctx)
            if this_player is None:
                return
        else:
            user = user
            this_player: player.Player = util.get_player_from_member(ctx, user)

        # Sort effects by remaining duration (the shortest first, permanent ones last)
        sorted_effects = sorted(
            this_player.effects,
            key=lambda effect: effect.duration if effect.duration else float("inf")
        )

        # Format each effect with its name and expiration time
        effects_text = "\n".join(
            [
                f"- **{effect.effect_type.name.capitalize()}** (expires <t:{int((datetime.datetime.now() + datetime.timedelta(seconds=effect.duration)).timestamp())}:R>) "
                if effect.duration else f"- **{effect.effect_type.name.capitalize()}** (Permanent)"
                for effect in sorted_effects  # Iterating through the sorted list of effects
            ]
        ) if sorted_effects else "No active effects."

        embed = discord.Embed(title=f"{user.display_name}'s Effects", description=effects_text, color=0x00FF00)
        await ctx.send(embed=embed)

    @inventory_group.command(name="show", description="Displays your inventory")
    async def inventory_show(self, interaction: discord.Interaction):
        """Shows the player's inventory as a numbered list."""
        ctx = await commands.Context.from_interaction(interaction)
        this_player = await check_player_and_send_embed(ctx)
        if this_player is None:
            return

        inventory = this_player.get_inventory()

        if not inventory:
            embed = discord.Embed(description="Your inventory is empty!", color=0xFF0000)
            await interaction.response.send_message(embed=embed)
            return

        inventory_text = "\n".join(
            [f"{i + 1}. {thing.full_name} ({format_quantity(thing.size * ureg.kg, this_player.units)})" for i, thing in
             enumerate(inventory)]
        )

        embed = discord.Embed(title="Your Inventory", description=inventory_text, color=0x00FF00)
        embed.set_footer(text="Use /inventory use <number>, /inventory examine <number>, or /inventory delete <number>")
        await interaction.response.send_message(embed=embed)

    @inventory_group.command(name="use", description="Use an item from your inventory")
    @app_commands.describe(index="The number of the item in your inventory")
    async def inventory_use(self, interaction: discord.Interaction, index: int):
        """Uses an item from the inventory by its list number."""
        ctx = await commands.Context.from_interaction(interaction)
        this_player = await check_player_and_send_embed(ctx)
        if this_player is None:
            return

        inventory = this_player.get_inventory()
        if index < 1 or index > len(inventory):
            await interaction.response.send_message("Invalid item number!", ephemeral=True)
            return

        thing = inventory[index - 1]
        result = thing.use(this_player)  # Calls the item's use method
        embed = discord.Embed(description=result, color=0x00FF00)
        await interaction.response.send_message(embed=embed)

    @inventory_group.command(name="examine", description="Examine an item in your inventory")
    @app_commands.describe(index="The number of the item in your inventory")
    async def inventory_examine(self, interaction: discord.Interaction, index: int):
        """Shows details about an item from the inventory."""
        ctx = await commands.Context.from_interaction(interaction)
        this_player = await check_player_and_send_embed(ctx)
        if this_player is None:
            return

        inventory = this_player.get_inventory()
        if index < 1 or index > len(inventory):
            await interaction.response.send_message("Invalid item number!", ephemeral=True)
            return

        thing = inventory[index - 1]
        embed = discord.Embed(title=thing.name, description=thing.get_description(), color=0x00AAFF)
        await interaction.response.send_message(embed=embed)

    @inventory_group.command(name="delete", description="Delete an item from your inventory")
    @app_commands.describe(index="The number of the item in your inventory")
    async def inventory_delete(self, interaction: discord.Interaction, index: int):
        """Asks for confirmation before deleting an item."""
        ctx = await commands.Context.from_interaction(interaction)
        this_player = await check_player_and_send_embed(ctx)
        if this_player is None:
            return

        inventory = this_player.get_inventory()
        if index < 1 or index > len(inventory):
            await interaction.response.send_message("Invalid item number!", ephemeral=True)
            return

        thing = inventory[index - 1]

        # Send a confirmation message with buttons
        view = ConfirmDeleteView(interaction, this_player, thing, index - 1)
        embed = discord.Embed(
            description=f"Are you sure you want to delete **{thing.name}**?",
            color=0xFF0000
        )
        await interaction.response.send_message(embed=embed, view=view)

    @commands.hybrid_command(name="listbodyparts", description="List all your body parts and their properties.")
    @commands.is_owner()
    async def listbodyparts(self, ctx: Context):
        # Get player instance from the context
        this_player: player.Player = util.get_player_from_ctx(ctx)
        if this_player is None:
            embed = discord.Embed(description="Touch the tree first!", color=0xBEBEFE)
            await ctx.send(embed=embed)
            return

        # Initialize response list to gather information
        parts_info = []
        for part_name, part in this_player.body.items():
            part_description = f"**{part_name.capitalize()}**\n"

            # Collect details about each attribute
            for attr in dir(part):
                if not attr.startswith("__") and not callable(getattr(part, attr)):
                    value = getattr(part, attr)
                    part_description += f"  - {attr}: {value}\n"

            parts_info.append(part_description)

        # Join all part descriptions and send in the embed
        response = "\n".join(parts_info)
        embed = discord.Embed(title="Your Body Parts", description=response[:4000],
                              color=0xBEBEFE)  # Limit to Discord message length
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="cook", description="Cook a meal and add it to your inventory.")
    async def cook(self, ctx: commands.Context):
        """Starts the cooking process by showing a form to the player."""
        this_player = await check_player_and_send_embed(ctx)

        if this_player is None:
            return

        if ctx.interaction is None:
            await ctx.send("This command must be used as a slash command!")
            return

        await ctx.interaction.response.send_modal(CookMealModal(this_player, this_player.units))

    @commands.hybrid_command(name="breakfast", description="Eat breakfast and grow.")
    async def breakfast(self, ctx: Context):
        await meal(ctx)

    @commands.hybrid_command(name="lunch", description="Eat lunch and grow.")
    async def lunch(self, ctx: Context):
        await meal(ctx)

    @commands.hybrid_command(name="dinner", description="Eat dinner and grow.")
    async def dinner(self, ctx: Context):
        await meal(ctx)

    @commands.hybrid_command(name="dessert", description="Eat dessert and grow.")
    async def dessert(self, ctx: Context):
        await meal(ctx)

    @commands.hybrid_command(name="supper", description="Eat supper and grow.")
    async def supper(self, ctx: Context):
        await meal(ctx)

    @commands.hybrid_command(name="units", description="Set your preferred unit system.")
    async def units(self, ctx: commands.Context):
        """Handles the /set_units hybrid command."""
        grower = util.get_player_from_ctx(ctx)

        embed = discord.Embed(
            title="🌍 Choose Your Unit System",
            description=(
                "Select your preferred measurement system:\n"
                "🔹 **Metric**: Meters, kilograms, liters.\n"
                "🔹 **US Customary**: Feet, pounds, gallons.\n\n"
                "This setting will be used for displaying measurements."
            ),
            color=discord.Color.blue()
        )

        # Send the message with the view tied to the specific player
        await ctx.send(embed=embed, view=UnitSelectionView(grower))


async def setup(bot: commands.Bot) -> None:
    """Adds the Game cog and syncs commands, but does NOT register interactions again."""
    await bot.add_cog(Game(bot))  # No duplicate registration here
