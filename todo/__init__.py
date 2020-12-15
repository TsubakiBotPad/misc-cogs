from .todo import Todo

__red_end_user_data_statement__ = "Todo lists are stored."


def setup(bot):
    bot.add_cog(Todo(bot))
    pass
