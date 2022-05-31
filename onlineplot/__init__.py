from .onlineplot import OnlinePlot

__red_end_user_data_statement__ = "No personal data is stored."


async def setup(bot):
    cog = OnlinePlot(bot)
    bot.add_cog(cog) if not __import__('asyncio').iscoroutinefunction(bot.add_cog) else await bot.add_cog(cog)
    bot.loop.create_task(cog.init())
