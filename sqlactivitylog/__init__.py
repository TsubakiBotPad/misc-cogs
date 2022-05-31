from .sqlactivitylog import SqlActivityLogger

__red_end_user_data_statement__ = "All message edits/deletions less than 3 weeks old are saved."


async def setup(bot):
    n = SqlActivityLogger(bot)
    bot.add_cog(n) if not __import__('asyncio').iscoroutinefunction(bot.add_cog) else await bot.add_cog(n)
    bot.loop.create_task(n.init())
