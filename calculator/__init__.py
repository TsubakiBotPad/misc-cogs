from .calculator import Calculator

__red_end_user_data_statement__ = "The most recent answer in each channel is stored."


async def setup(bot):
    bot.add_cog(Calculator(bot)) if not __import__('asyncio').iscoroutinefunction(bot.add_cog) else await bot.add_cog(Calculator(bot))
