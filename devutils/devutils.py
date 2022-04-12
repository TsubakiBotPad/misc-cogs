import asyncio
import re
import sys
from io import BytesIO

from redbot.core import checks, commands
from tsutils.user_interaction import send_confirmation_message, send_cancellation_message


class DevUtils(commands.Cog):
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

    @commands.command(aliases=['freload', 'creload'])
    @checks.is_owner()
    async def rlthen(self, ctx, command, *, arguments=""):
        """Run a command after reloading its base cog."""
        full_cmd = "{}{} {}".format(ctx.prefix, command, arguments)
        command = self.bot.get_command(command)
        if command is None:
            await ctx.send("Invalid Command: {}".format(full_cmd))
            return
        _send = ctx.send

        async def fakesend(text, *args, **kwargs):
            if "Reloaded " in text:
                return
            await _send(text, *args, **kwargs)

        ctx.send = fakesend
        await self.bot.get_cog("Core").reload(ctx, command.cog.__module__.split('.')[0])

        ctx.send = _send
        ctx.message.content = full_cmd
        await self.bot.process_commands(ctx.message)

    @commands.command(aliases=['delaysend'])
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

        if command.startswith(ctx.prefix):
            command = command[len(ctx.prefix):]

        cname_parts = []
        for part in command.split():
            if self.bot.get_command(" ".join(cname_parts) + " " + part) is None:
                break
            cname_parts.append(part)

        resolved_command = " ".join(cname_parts)

        cmd = self.bot.get_command(resolved_command)
        if cmd is None:
            resolved_command_message = f'`{resolved_command}`' if resolved_command else "the empty string"
            await send_cancellation_message(ctx,
                                            f"`{command}` (resolved to {resolved_command_message}) is not a valid command.\n"
                                            f"Aliases aren't valid with this command. Bot prefix is optional. "
                                            f"Time must be given in seconds or minutes as a one-letter abbreviation, e.g. `5m`.")
            return
        if not await cmd.can_run(ctx):
            await send_cancellation_message(ctx, f"You do not have permission to run the command `{resolved_command}`")

        await ctx.tick()
        await asyncio.sleep(time)

        ctx.message.content = ctx.prefix + command
        await self.bot.process_commands(ctx.message)

    @commands.command(aliases=["pipupgrade"])
    @checks.is_owner()
    async def pipupdate(self, ctx, module, updatepip: bool = True):
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
            await send_cancellation_message(ctx, "Error updating:\n" + stderr)
        else:
            lines = stdout.split('\n')
            last_line = lines[-1]
            if 'Successfully installed' in last_line:
                return await send_confirmation_message(ctx, last_line)
            else:
                return await send_cancellation_message(ctx, lines[0])

    @commands.command()
    async def relast(self, ctx):
        async for message in ctx.channel.history(limit=200):
            b = False
            if message.author == ctx.author and "relast" not in message.content:
                for prefix in await self.bot.get_valid_prefixes():
                    if message.content.startswith(prefix) \
                            and self.bot.get_command(message.content[len(prefix):]):
                        b = True
                        break
                if b:
                    break
        else:
            await ctx.send("Your most recent message could not be found.")
            return
        await self.bot.process_commands(message)
