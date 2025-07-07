from discord.ext import commands, tasks
import universe


class ClockCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.save_loaded = False  # Flag to track if save has been loaded
        self.tick.start()
        self.hourly_task.start()
        self.process_food.start()
        self.daily_task.start()

    @tasks.loop(seconds=1)
    async def tick(self):
        for u in universe.multiverse_instance:
            for player in u.players:
                player.tick_effects()

    @tasks.loop(hours=1)
    async def hourly_task(self):
        universe.save_data()

    @tasks.loop(hours=2)
    async def process_food(self):
        print("Processing food for all universes...")
        for u in universe.multiverse_instance:
            for player in u.players:
                player.digest()

    @tasks.loop(hours=24)
    async def daily_task(self):
        universe.delete_old_files()

    @hourly_task.before_loop
    @process_food.before_loop
    @daily_task.before_loop
    async def before_tasks(self):
        await self.bot.wait_until_ready()
        print("Waiting until the bot is ready before starting tasks...")

    @commands.Cog.listener()
    async def on_ready(self):
        print('ClockCog is ready.')

        if not self.save_loaded:  # Only load if it hasn't been loaded yet
            universe.load_most_recent_save()
            self.save_loaded = True  # Mark as loaded to prevent reloading


# Required setup function
async def setup(bot):
    await bot.add_cog(ClockCog(bot))
