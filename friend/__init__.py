from .friend import Friend

__red_end_user_data_statement__ = "Manually added friends are stored by user ID."


def setup(bot):
    bot.add_cog(Friend(bot))
