from .streamcopy import StreamCopy

__red_end_user_data_statement__ = "No personal data is stored."


def setup(bot):
    n = StreamCopy(bot)
    bot.loop.create_task(n.refresh_stream())
    bot.add_cog(n)
