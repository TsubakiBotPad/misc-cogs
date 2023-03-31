from .tsubakigpt import TsubakiGPT

__red_end_user_data_statement__ = "No user data is stored."


async def setup(bot):
    await bot.add_cog(TsubakiGPT(bot))
