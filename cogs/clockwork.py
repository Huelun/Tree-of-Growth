from discord.ext import commands, tasks
import universe


def initial_setup():
    # Actions to perform on initialisation
    print("Bot has restarted and the cog is initialized.")
    universe.load_most_recent_save()


class ClockCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        initial_setup()
        self.hourly_task.start()

    @tasks.loop(hours=1)
    async def hourly_task(self):
        universe.save_data()

    @tasks.loop(hours=2)
    async def process_food(self):
        for u in universe.multiverse_instance:
            for grower in u.players:
                grower.digest()

    @tasks.loop(hours=24)
    async def daily_task(self):
        universe.delete_old_files()

    @hourly_task.before_loop
    async def before_hourly_task(self):
        await self.bot.wait_until_ready()
        print("Waiting until the bot is ready before starting the hourly task...")

    @commands.Cog.listener()
    async def on_ready(self):
        print(f'ClockworkCog is ready.')


# Required setup function
async def setup(bot):
    await bot.add_cog(ClockCog(bot))
