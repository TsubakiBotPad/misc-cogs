from .memes import Memes

__red_end_user_data_statement__ = "All stored data is anonymized."


async def setup(bot):
    bot.add_cog(Memes(bot)) if not __import__('asyncio').iscoroutinefunction(bot.add_cog) else await bot.add_cog(Memes(bot))
