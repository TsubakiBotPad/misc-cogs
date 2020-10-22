import asyncio
import discord
import sys
import re
from redbot.core import checks, commands, modlog
from redbot.core.utils.chat_formatting import box, inline, pagify


class TrUtils(commands.Cog):
    """Owner Utilities"""
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

    @commands.command()
    @checks.is_owner()
    async def freload(self, ctx, cmd, *, args=""):
        """Run a command after reloading its base cog."""
        full_cmd = "{}{} {}".format(ctx.prefix, cmd, args)
        cmd = self.bot.get_command(cmd)
        if cmd is None:
            await ctx.send("Invalid Command: {}".format(full_cmd))
            return
        _send = ctx.send

        async def fakesend(*args, **kwargs):
            if "Reloaded " in args[0]:
                return
            await _send(*args, **kwargs)

        ctx.send = fakesend
        await self.bot.get_cog("Core").reload(ctx, cmd.cog.__module__.split('.')[0])

        ctx.send = _send
        ctx.message.content = full_cmd
        await self.bot.process_commands(ctx.message)

    @commands.command()
    async def delaycommand(self, ctx, time, *, command):
        """Run a command after waiting a period of time.

        [p]delaycommand 30s which sonia
        [p]delaycommand 5m forceindexreload
        """
        if not re.match(r'\d+[ms]?', time):
            await ctx.send("Invalid time: {}".format(time))
            return

        if time.endswith('s'):
            time = int(time[:-1])
        elif time.endswith('m'):
            time = int(time[:-1]) * 60
        else:
            time = int(time)

        if time > 60 * 15:
            await ctx.send("Time must be less than 15 minutes.")
            return

        cname = []
        for sc in command.split():
            if self.bot.get_command(" ".join(cname) + " " + sc) is None:
                break
            cname.append(sc)

        cmd = self.bot.get_command(" ".join(cname))
        if cmd is None:
            await ctx.send("Invalid Command. \nNOTE: Aliases aren't valid with this command")
            return
        if not await cmd.can_run(ctx):
            await ctx.send("You do not have permission to run the command `{}`".format(" ".join(cname)))

        await ctx.tick()
        await asyncio.sleep(time)

        ctx.message.content = ctx.prefix + command
        await self.bot.process_commands(ctx.message)

    @commands.command()
    @checks.is_owner()
    async def pipupdate(self, ctx, module="Red-DiscordBot", updatepip=True):
        async with ctx.typing():
            process = await asyncio.create_subprocess_exec(
                sys.executable, "-m", "pip", "install", "-U", module,

                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = (bts.decode() if bts else "" for bts in await process.communicate())

        if stderr.startswith("WARNING: You are using pip version"):
            if updatepip:
                await ctx.send(stderr.split('You should consider')[0] + '\n\nUpdating pip...')
                await self.pipupdate(ctx, 'pip', False)
            stderr = ""

        if stderr:
            await ctx.author.send("Error updating:\n" + stderr)
            await ctx.send(inline("Error (sent via DM)"))
        else:
            await ctx.tick()
