import asyncio
import datetime
import discord
import logging
from io import BytesIO
from redbot.core import Config, checks, commands, modlog
from redbot.core.bot import Red
from redbot.core.utils.chat_formatting import inline
from tsutils import confirm_message

logger = logging.getLogger('red.misc-cogs.globalban')


class GlobalBan(commands.Cog):
    def __init__(self, bot: Red, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config = Config.get_conf(self, identifier=1437847847)
        self.config.register_global(banned={}, opted=[])
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

    @commands.group()
    async def globalban(self, ctx):
        """Global ban related commands."""

    @globalban.command()
    @checks.admin_or_permissions(administrator=True)
    async def optin(self, ctx):
        """Opt your server in to the Global Ban system."""
        if not await confirm_message("This will ban all users on the global"
                                     " ban list. Are you sure you want to opt in?"):
            return

        async with self.config.opted() as opted:
            opted.append(ctx.guild.id)
        async with ctx.typing():
            await self.update_gbs()
        await ctx.tick()

    @globalban.command()
    @checks.admin_or_permissions(administrator=True)
    async def optout(self, ctx):
        """Opt your server out of the Global Ban system."""
        if not await confirm_message("This will remove all bans that intersect"
                                     " with the global ban list. Are you sure"
                                     " you want to opt out?"):
            return

        async with self.config.opted() as opted:
            while ctx.guild.id in opted:
                opted.remove(ctx.guild.id)
        async with ctx.typing():
            await self.remove_gbs_guild(ctx.guild.id)
        await ctx.tick()

    @globalban.command()
    @checks.is_owner()
    @checks.bot_has_permissions(ban_members=True)
    async def ban(self, ctx, user: int, *, reason=""):
        """Globally Ban a user across all opted-in servers."""
        async with self.config.banned() as banned:
            banned[str(user)] = reason
        async with ctx.typing():
            await self.update_gbs()
        await ctx.tick()

    @globalban.command()
    @checks.is_owner()
    @checks.bot_has_permissions(ban_members=True)
    async def unban(self, ctx, user: int):
        """Globally Unban a user across all opted-in servers."""
        user = str(user)
        async with self.config.banned() as banned:
            if user in banned:
                del banned[user]
        async with ctx.typing():
            await self.remove_gbs_user(user)
        await ctx.tick()

    async def update_gbs(self):
        for gid in await self.config.opted():
            guild = self.bot.get_guild(int(gid))
            for uid, reason in (await self.config.banned()).items():
                try:
                    if uid in [b.user.id for b in await guild.bans()]:
                        continue
                except (AttributeError, discord.Forbidden):
                    continue
                m = guild.get_member(int(uid))
                try:
                    if m is None:
                        try:
                            await guild.ban(discord.Object(id=uid), reason="GlobalBan", delete_message_days=0)
                        except discord.errors.NotFound:
                            pass
                    else:
                        await guild.ban(m, reason="GlobalBan", delete_message_days=0)
                    await modlog.create_case(bot=self.bot,
                                             guild=guild,
                                             created_at=datetime.datetime.now(datetime.timezone.utc),
                                             action_type="globalban",
                                             user=m,
                                             reason='GlobalBan')
                except discord.Forbidden:
                    logger.warning("Failed to ban user with ID {} in guild {}".format(uid, guild.name))

    async def remove_gbs_guild(self, gid):
        guild = self.bot.get_guild(int(gid))
        for ban in await guild.bans():
            user = b.user
            if user.id not in await self.config.banned():
                continue
            try:
                await guild.unban(user)
            except discord.Forbidden:
                pass

    async def remove_gbs_user(self, uid):
        for gid in await self.config.opted():
            guild = self.bot.get_guild(int(gid))
            users = [b.user for b in await guild.bans() if b.user.id == int(uid)]
            if users:
                try:
                    await guild.unban(users[0])
                except discord.Forbidden:
                    pass
