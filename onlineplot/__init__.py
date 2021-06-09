from .onlineplot import OnlinePlot

__red_end_user_data_statement__ = "No personal data is stored."


def setup(bot):
    cog = OnlinePlot(bot)
    bot.add_cog(cog)
    bot.loop.create_task(cog.init())
    bot.loop.create_task(cog.restart_loop())
