from .todo import Todo

__red_end_user_data_statement__ = "Todo lists are stored."


async def setup(bot):
    bot.add_cog(Todo(bot)) if not __import__('asyncio').iscoroutinefunction(bot.add_cog) else await bot.add_cog(Todo(bot))
    pass
