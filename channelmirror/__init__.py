from .channelmirror import ChannelMirror

__red_end_user_data_statement__ = "No personal data is stored."


async def setup(bot):
    n = ChannelMirror(bot)
    bot.add_cog(n) if not __import__('asyncio').iscoroutinefunction(bot.add_cog) else await bot.add_cog(n)
