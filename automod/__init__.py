from .automod import AutoMod

__red_end_user_data_statement__ = "This cog stores id of users manually marked as problematic."


async def setup(bot):
    bot.add_cog(AutoMod(bot)) if not __import__('asyncio').iscoroutinefunction(bot.add_cog) else await bot.add_cog(AutoMod(bot))
