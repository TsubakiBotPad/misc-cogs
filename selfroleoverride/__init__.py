from .selfroleoverride import *
from redbot.core import errors

__red_end_user_data_statement__ = "No personal data is stored."


def setup(bot):
    if bot.get_cog("Admin") is None:
        raise errors.CogLoadError("Admin cog must be loaded to override selfrole.")
        
    pdb = SelfRoleOverride(bot)
    bot.add_cog(pdb)
