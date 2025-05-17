import os
import tracemalloc

import discord
import psutil
from discord import app_commands
from discord.ext import commands


class MemoryMonitor(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="memory", help="Shows bot's memory usage")
    async def memory(self, ctx):
        await ctx.defer()  # Prevents command timeout

        process = psutil.Process(os.getpid())
        mem_usage = process.memory_info().rss / (1024 ** 2)  # Convert to MB
        total_mem = psutil.virtual_memory().total / (1024 ** 2)  # Total system RAM in MB

        embed = discord.Embed(
            title="🖥️ Memory Usage",
            description=f"**Bot Memory:** {mem_usage:.2f} MB\n**Total System Memory:** {total_mem:.2f} MB",
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="memtrace", help="Shows top memory allocations")
    @app_commands.describe(
        lines="The number of top memory-consuming lines to display (default is 5).",
        only_local="If True, only shows lines from your codebase (cogs and local files). Default is False."
    )
    async def memtrace(self, ctx, lines: int = 5, only_local: bool = False):
        """
        Shows the top memory-consuming lines.
        - Default: Shows top 5 lines.
        - Use `!memtrace 10` to show more lines.
        - Use `!memtrace 10 True` to only show lines from your codebase (cogs and local files).
        """
        await ctx.defer()  # Prevents command timeout
        if not tracemalloc.is_tracing():
            await ctx.send("🔴 Memory tracking is not enabled. Use `tracemalloc.start()` at bot startup.")
            return

        snapshot = tracemalloc.take_snapshot()
        top_stats = snapshot.statistics("lineno")

        # Define your local project directory (adjust if needed)
        local_path = os.getcwd()  # Gets the bot's main directory

        # Filter results to only local files if requested
        if only_local:
            top_stats = [stat for stat in top_stats if local_path in stat.traceback[0].filename]

        # Ensure we have at least some results
        if not top_stats:
            await ctx.send("✅ No significant memory usage found in your local files.")
            return

        # Ensure the requested number of lines is within bounds
        lines = max(1, min(len(top_stats), lines))

        message = f"**Top {lines} memory-consuming lines:**\n"
        for stat in top_stats[:lines]:
            # Shorten the file paths to make them cleaner and hide internal directory structure
            file_path = stat.traceback[0].filename
            if only_local:
                file_path = file_path.replace(local_path, ".")  # Hide the internal directory path in local mode
            else:
                # When not filtering to only local files, you can make the paths more concise
                file_path = os.path.basename(file_path)  # This keeps only the file name

            line_info = f"`{file_path}:{stat.traceback[0].lineno}` → {stat.size / 1024:.1f} KB"
            message += f"{line_info}\n"

        total = sum(stat.size for stat in top_stats[:lines])
        message += f"\n**Total tracked memory:** {total / 1024:.1f} KB"

        await ctx.send(message)


async def setup(bot):
    await bot.add_cog(MemoryMonitor(bot))
