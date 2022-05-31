import asyncio

from redbot.core import errors

from .selfroleoverride import SelfRoleOverride

__red_end_user_data_statement__ = "No personal data is stored."


async def setup_after_ready(bot):
    await bot.wait_until_red_ready()
    if bot.get_cog("Admin") is None:
        raise errors.CogLoadError("Admin cog must be loaded to override selfrole.")
    bot.add_cog(SelfRoleOverride(bot)) if not __import__('asyncio').iscoroutinefunction(bot.add_cog) else await bot.add_cog(SelfRoleOverride(bot))


async def setup(bot):
    asyncio.create_task(setup_after_ready(bot))
