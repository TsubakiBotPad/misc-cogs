from .timecog import TimeCog

__red_end_user_data_statement__ = "Reminders are stored."


async def setup(bot):
    n = TimeCog(bot)
    bot.add_cog(n) if not __import__('asyncio').iscoroutinefunction(bot.add_cog) else await bot.add_cog(n)
