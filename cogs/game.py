import discord
from discord.ext import commands
from discord.ext.commands import Context
from units import ureg

import player
import universe


async def meal(ctx: Context):
    grower: player.Player = get_player_from_ctx(ctx)
    if grower is None:
        embed = discord.Embed(description="Touch the tree first!", color=0xBEBEFE)
        await ctx.send(embed=embed)
        return
    amount = grower.get_mass() / 51 / 5
    weight_before = grower.get_mass()
    height_before = grower.get_height()
    if grower.can_eat(amount):
        grower.feed(amount)
        delta_h = grower.get_height() - height_before
        delta_w = grower.get_mass() - weight_before
        message = f"You have grown {delta_h:.2f~P} in height and became {delta_w:.2f~P} more massive."
    else:
        message = "You are too full to eat."
    await ctx.send(embed=discord.Embed(description=message, color=0xBEBEFE))


class Game(commands.Cog, name="game"):
    def __init__(self, bot) -> None:
        self.bot = bot

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
    async def size(self, ctx: Context):
        this_player: player.Player = get_player_from_ctx(ctx)
        if this_player is None:
            embed = discord.Embed(description="Touch the tree first!", color=0xBEBEFE)
            await ctx.send(embed=embed)
            return
        player.check_serializability(this_player)
        total_weight = this_player.get_mass()
        torso_circumferences = []
        arm_circumferences = []
        leg_circumferences = []

        # Iterate through body parts
        for part_name, part in this_player.body.items():
            # Collect circumferences
            if hasattr(part, 'waist_c'):
                torso_circumferences.append(part.waist_c)
            elif hasattr(part, 'wide_c') and 'arm' in part_name:
                arm_circumferences.append(part.wide_c)
            elif hasattr(part, 'wide_c') and 'leg' in part_name:
                leg_circumferences.append(part.wide_c)

        # Calculate height: torso, neck, and head lengths plus longest leg length
        height = this_player.get_height()

        # Calculate average or max values for circumferences, with fallback
        avg_torso_circumference = sum(torso_circumferences) / len(
            torso_circumferences) if torso_circumferences else 0 * ureg.centimeter
        max_arm_circumference = max(arm_circumferences) if arm_circumferences else 0 * ureg.centimeter
        max_leg_circumference = max(leg_circumferences) if leg_circumferences else 0 * ureg.centimeter

        # Format the output message with additional dimensions
        response = (
            f"**Measurements**\n"
            f"Height: {height:.2f~P}\n"
            f"Weight: {total_weight:.2f~P}\n"
            f"Avg Chest Circumference: {avg_torso_circumference:.2f~P}\n"
            f"Max Arm Circumference: {max_arm_circumference:.2f~P}\n"
            f"Max Leg Circumference: {max_leg_circumference:.2f~P}\n"
        )

        # Send the response
        await ctx.send(embed=discord.Embed(description=response, color=0xBEBEFE))

    @commands.hybrid_command(name="listbodyparts", description="List all your body parts and their properties.")
    async def listbodyparts(self, ctx: Context):
        # Get player instance from the context
        this_player: player.Player = get_player_from_ctx(ctx)
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

                    # Check if it's a pint Quantity for unit formatting
                    if isinstance(value, ureg.Quantity):
                        part_description += f"  - {attr}: {value:.2f~P}\n"
                    else:
                        part_description += f"  - {attr}: {value}\n"

            parts_info.append(part_description)

        # Join all part descriptions and send in the embed
        response = "\n".join(parts_info)
        embed = discord.Embed(title="Your Body Parts", description=response[:4000],
                              color=0xBEBEFE)  # Limit to Discord message length
        await ctx.send(embed=embed)

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


def get_player_from_ctx(ctx):
    # Get the universe based on the channel ID
    this_universe = universe.multiverse_instance.get_universe_from_id(ctx.channel.id)
    if this_universe is None:
        return None  # Universe not found for this channel
    # Retrieve the player based on the author ID
    return this_universe.get_player_by_id(ctx.author.id)


async def setup(bot) -> None:
    await bot.add_cog(Game(bot))
