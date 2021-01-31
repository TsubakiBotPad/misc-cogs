import asyncio
import logging
import random
from io import BytesIO

import discord
from redbot.core import checks, Config
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.utils.chat_formatting import box, inline, pagify

logger = logging.getLogger('red.misc-cogs.streamcopy')


class StreamCopy(commands.Cog):
    """Show which members are streaming and opt members in and out of being public for the guild"""

    def __init__(self, bot: Red, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot

        self.config = Config.get_conf(self, identifier=5723477047)
        self.config.register_global(opted_in=[])
        self.config.register_guild(streamer_rid=None)

        self.current_user_id = None

    async def red_get_data_for_user(self, *, user_id):
        """Get a user's personal data."""
        data = "No data is stored for user with ID {}.\n".format(user_id)
        return {"user_data.txt": BytesIO(data.encode())}

    async def red_delete_data_for_user(self, *, requester, user_id):
        """Delete a user's personal data.

        No personal data is stored in this cog.
        """
        return

    async def refresh_stream(self):
        await self.bot.wait_until_ready()
        while self == self.bot.get_cog('StreamCopy'):
            try:
                await self.do_refresh()
                await self.do_ensure_roles()
            except Exception as e:
                logger.exception("Error: ")

            await asyncio.sleep(60 * 3)
        logger.info("done refresh_stream")

    @commands.group()
    @checks.mod_or_permissions(manage_guild=True)
    async def streamcopy(self, ctx):
        """Utilities for reacting to users gaining/losing streaming status."""

    @streamcopy.command()
    @commands.guild_only()
    async def setstreamerrole(self, ctx, *, role: discord.Role):
        """Sets the streamer role."""
        await self.config.guild(ctx.guild).streamer_rid.set(role.id)
        await ctx.send(inline('Done. Make sure that role is below the bot in the hierarchy'))

    @streamcopy.command()
    @commands.guild_only()
    async def clearstreamerrole(self, ctx):
        """Removes the streamer role."""
        await self.config.guild(ctx.guild).streamer_rid.set(None)
        await ctx.tick()

    @streamcopy.command()
    @checks.is_owner()
    async def adduser(self, ctx, user: discord.User):
        """Opts a user into streamcopy"""
        async with self.config.opted_in() as users:
            if user.id not in users:
                users.append(user.id)
        await ctx.tick()

    @streamcopy.command()
    @checks.is_owner()
    async def rmuser(self, ctx, user):
        """Opts a user out of streamcopy"""
        try:
            user = await commands.MemberConverter().convert(ctx, user).id
        except commands.BadArgument:
            try:
                user = int(user)
            except ValueError:
                await ctx.send(inline("Invalid user id."))
                return
        async with self.config.opted_in() as users:
            if user not in users:
                await ctx.send("User is not already opted in")
                return
            users.remove(user)
        await ctx.tick()

    @streamcopy.command()
    @checks.is_owner()
    async def list(self, ctx):
        """Lists all users who are opted into streamcopy"""
        output = []
        for uid in await self.config.opted_in():
            user = self.bot.get_user(uid)
            if user is None:
                output.append("Deleted User ({})".format(uid))
            else:
                output.append("({}) : {}".format('+' if self.is_playing(user) else '-', user.name))

        for page in pagify('\n'.join(output)):
            await ctx.send(box(page))

    @streamcopy.command()
    @checks.is_owner()
    async def refresh(self, ctx):
        """Refreshes the streamcopy cog data"""
        other_stream = await self.do_refresh()
        if other_stream:
            await ctx.send(inline('Updated stream'))
        else:
            await ctx.send(inline('Could not find a streamer'))

    @commands.Cog.listener('on_member_update')
    async def check_stream(self, before, after):
        await self.ensure_user_streaming_role(after.guild, after)

        try:
            tracked_users = await self.config.opted_in()
            if after.id not in tracked_users:
                return

            if self.is_playing(after):
                await self.copy_playing(after.activity)
                return

            await self.do_refresh()
        except Exception:
            logger.exception("Stream checking failed")

    async def ensure_user_streaming_role(self, guild, user):
        user_is_playing = self.is_playing(user)
        streamer_role = await self.config.guild(guild).streamer_rid()
        if streamer_role is None:
            return
        user_has_streamer_role = streamer_role in user.roles
        if user_is_playing and not user_has_streamer_role:
            await user.add_roles(streamer_role)
        elif not user_is_playing and user_has_streamer_role:
            await user.remove_roles(streamer_role)

    async def do_refresh(self):
        other_stream = await self.find_stream()
        if other_stream:
            await self.copy_playing(other_stream)
        else:
            await self.bot.change_presence(activity=None)
        return other_stream

    async def do_ensure_roles(self):
        for guild in self.bot.guilds:
            for member in guild.members:
                await self.ensure_user_streaming_role(member.guild, member)

    async def find_stream(self):
        user_ids = await self.config.opted_in()
        games = [x.activity for x in self.bot.get_all_members() if x.id in user_ids and self.is_playing(x)]
        random.shuffle(games)
        return games[0] if games else None

    def is_playing(self, member):
        return member and member.activity == discord.ActivityType.streaming and member.activity.url

    async def copy_playing(self, stream):
        new_stream = discord.Game(name=stream.name, url=stream.url, type=stream.type)
        await self.bot.change_presence(activity=new_stream)
