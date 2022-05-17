import re
from io import BytesIO

import discord
from redbot.core import Config, checks, commands
from redbot.core.bot import Red
from redbot.core.utils.chat_formatting import box, inline


class MsgUtils(commands.Cog):
    """Utilities to view raw messages"""
    def __init__(self, bot: Red, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot

        self.config = Config.get_conf(self, identifier=735549377175)
        self.config.register_user(last_command="")

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
    @checks.mod_or_permissions(manage_messages=True)
    async def editmsg(self, ctx, channel: discord.TextChannel, msg_id: int, *, new_msg: str):
        """Given a channel and an ID for a message printed in that channel, replaces it.

        To find a message ID, enable developer mode in Discord settings and
        click the ... on a message.
        """
        try:
            msg = await channel.fetch_message(msg_id)
        except discord.NotFound:
            await ctx.send(inline('Cannot find that message, check the channel and message id'))
            return
        except discord.Forbidden:
            await ctx.send(inline('No permissions to do that'))
            return
        if msg.author.id != self.bot.user.id:
            await ctx.send(inline('Can only edit messages I own'))
            return

        await msg.edit(content=new_msg)
        await ctx.tick()

    @commands.command()
    @checks.mod_or_permissions(manage_messages=True)
    async def dumpchannel(self, ctx, channel: discord.TextChannel, msg_id: int = None):
        """Given a channel and an ID for a message printed in that channel, dumps it
        boxed with formatting escaped and some issues cleaned up.

        To find a message ID, enable developer mode in Discord settings and
        click the ... on a message.
        """
        await self._dump(ctx, channel, msg_id)

    @commands.command()
    async def dumpmsg(self, ctx, msg_id: int = None):
        """Given an ID for a message printed in the current channel, dumps it
        boxed with formatting escaped and some issues cleaned up.

        To find a message ID, enable developer mode in Discord settings and
        click the ... on a message.
        """
        await self._dump(ctx, ctx.channel, msg_id)

    async def _dump(self, ctx, channel: discord.TextChannel = None, msg_id: int = None):
        if msg_id:
            try:
                msg = await channel.fetch_message(msg_id)
            except discord.NotFound:
                await ctx.send("Invalid message id")
                return
        else:
            msg_limit = 2 if channel == ctx.channel else 1
            async for message in channel.history(limit=msg_limit):
                msg = message
        content = msg.content.strip()
        content = re.sub(r'<(:[0-9a-z_]+:)\d{18}>', r'\1', content, flags=re.IGNORECASE)
        content = box(content.replace('`', u'\u200b`'))
        await ctx.send(content)

    @commands.command()
    async def dumpmsgexact(self, ctx, msg_id: int):
        """Given an ID for a message printed in the current channel, dumps it
        boxed with formatting escaped.

        To find a message ID, enable developer mode in Discord settings and
        click the ... on a message.
        """
        msg = await ctx.channel.fetch_message(msg_id)
        content = msg.content.strip()
        content = box(content.replace('`', u'\u200b`'))
        await ctx.send(content)

    @commands.command(aliases=['%'])
    async def repeatlast(self, ctx, *, rest=''):
        """Repeat your most recent command"""
        last_command = await self.config.user(ctx.author).last_command()
        ctx.message.content = f"{ctx.prefix}{last_command} {rest}"
        await self.bot.process_commands(ctx.message)

    @commands.Cog.listener('on_message')
    async def log_recent(self, message):
        content = message.content
        for prefix in await self.bot.get_valid_prefixes():
            if content.startswith(prefix):
                content = content[len(prefix):]
                break
        else:
            return

        if self.bot.get_command(content) == self.repeatlast:
            args = content.split(" ", 1)[1]
            content = (await self.config.user(message.author).last_command()) + " " + args

        await self.config.user(message.author).last_command.set(content)
