from .timecog import TimeCog

__red_end_user_data_statement__ = "Reminders are stored."


def setup(bot):
    n = TimeCog(bot)
    bot.add_cog(n)
