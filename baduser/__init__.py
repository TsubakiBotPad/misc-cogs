from .baduser import BadUser

__red_end_user_data_statement__ = "All users last 10 messages are stored in memory, and when a user is marked as problematic, their last 10 messages are stored perminently for logging purposes."


async def setup(bot):
    bot.add_cog(BadUser(bot)) if not __import__('asyncio').iscoroutinefunction(bot.add_cog) else await bot.add_cog(BadUser(bot))
