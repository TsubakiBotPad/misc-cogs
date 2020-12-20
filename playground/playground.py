from io import BytesIO
from redbot.core import commands
import discord.ext


def make_gatekeeping_check(condition, failmessage):
    def gatekeep_check(**kwargs):
        def decorator(command):
            @command.before_invoke
            async def hook(instance, ctx):
                if not condition(ctx, **kwargs):
                    await ctx.send(failmessage)
                    raise discord.ext.commands.CheckFailure()
            return command
        return decorator
    return gatekeep_check

check = lambda ctx, l="A": ctx.author.nick.startswith(l)

gate_to_donor = make_gatekeeping_check(check, "Permission denied")

class Playground(commands.Cog):
    """A temporary place for test commands that don't last long."""
    def __init__(self, bot, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot

    async def red_get_data_for_user(self, *, user_id):
        """Get a user's personal data."""
        data = "No data is stored for user with ID {}.\n".format(user_id)
        return {"user_data.txt": BytesIO(data.encode())}

    async def red_delete_data_for_user(self, *, requester, user_id):
        """Delete a user's personal data.

        No personal data is stored in this cog.
        """
        return
    
    @gate_to_donor(l="F")
    @commands.command()
    async def test_command(self, ctx):
        await ctx.send("Permission granted")
