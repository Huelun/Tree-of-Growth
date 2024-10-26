import platform
import random

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands
from discord.ext.commands import Context

import player
import universe


class Game(commands.Cog, name="game"):
    def __init__(self, bot) -> None:
        self.bot = bot


@commands.hybrid_command(
    name="touchtree", description="Join the game and receive the blessing of growth."
)
async def touchtree(self, context: Context) -> None:
    this_universe: universe.Universe = universe.multiverse_instance.id_to_universe(context.message.id)
    this_player_id = context.author.id
    if this_player_id in this_universe.players:
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
    if universe.multiverse_instance.get_universe_from_id():
        embed = discord.Embed(description="A universe already exists in this channel.", color=0xBEBEFE)
    else:
        universe.multiverse_instance.create_universe(Context.channel.id, name)
        embed = discord.Embed(description="Created a new universe.", color=0xBEBEFE)
    await context.send(embed=embed)


async def setup(bot) -> None:
    await bot.add_cog(Game(bot))
