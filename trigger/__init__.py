from .trigger import Trigger

__red_end_user_data_statement__ = "Triggers are stored persistantly."


async def setup(bot):
    n = Trigger(bot)
    bot.loop.create_task(n.load_triggers())
    bot.add_cog(n) if not __import__('asyncio').iscoroutinefunction(bot.add_cog) else await bot.add_cog(n)
