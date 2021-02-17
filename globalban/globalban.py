import datetime
import logging
from io import BytesIO

import discord
from redbot.core import Config, checks, commands, modlog
from redbot.core.bot import Red
from redbot.core.utils.chat_formatting import inline, pagify, box
from tsutils import confirm_message

logger = logging.getLogger('red.misc-cogs.globalban')


class GlobalBan(commands.Cog):
    def __init__(self, bot: Red, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config = Config.get_conf(self, identifier=1437847847)
        self.config.register_global(banned={}, opted=[])
        self.config.register_guild(banlist=[])
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

    @commands.group(aliases=['gban'])
    async def globalban(self, ctx):
        """Global ban related commands."""

    @globalban.command()
    @checks.admin_or_permissions(administrator=True)
    async def optin(self, ctx):
        """Opt your server in to the Global Ban system."""
        async with self.config.opted() as opted:
            if ctx.guild.id in opted:
                await ctx.send("This guild is already opted in.")
                return
            if not await confirm_message(ctx, "This will ban all users on the global"
                                              " ban list. Are you sure you want to opt in?"):
                return
            opted.append(ctx.guild.id)
        await self.config.guild(ctx.guild).banlist.set([be.user.id for be in await ctx.guild.bans()])
        async with ctx.typing():
            await self.update_gbs()
        await ctx.tick()

    @globalban.command()
    @checks.admin_or_permissions(administrator=True)
    async def optout(self, ctx):
        """Opt your server out of the Global Ban system."""
        async with self.config.opted() as opted:
            if ctx.guild.id not in opted:
                await ctx.send("This guild is already opted out.")
                return
            if not await confirm_message(ctx, "This will remove all bans that intersect"
                                              " with the global ban list. Are you sure"
                                              " you want to opt out?"):
                return
            opted.remove(ctx.guild.id)
        async with ctx.typing():
            await self.remove_gbs_guild(ctx.guild.id)
        await ctx.tick()

    @globalban.command()
    @checks.is_owner()
    @checks.bot_has_permissions(ban_members=True)
    async def ban(self, ctx, user_id: int, *, reason=''):
        """Globally Ban a user across all opted-in servers."""
        async with self.config.banned() as banned:
            banned[str(user_id)] = reason
        async with ctx.typing():
            await self.update_gbs()
        await ctx.tick()

    @globalban.command()
    @checks.is_owner()
    async def editreason(self, ctx, user_id: int, *, reason=""):
        """Edit a user's ban reason."""
        async with self.config.banned() as banned:
            if str(user_id) not in banned:
                await ctx.send("This user is not banned.")
                return
            if reason == "" and not await confirm_message(ctx, "Are you sure you want to remove the reason?"):
                return
            banned[str(user_id)] = reason
        await ctx.tick()

    @globalban.command()
    @checks.is_owner()
    @checks.bot_has_permissions(ban_members=True)
    async def unban(self, ctx, user_id: int):
        """Globally Unban a user across all opted-in servers."""
        async with self.config.banned() as banned:
            if str(user_id) in banned:
                del banned[str(user_id)]
        async with ctx.typing():
            await self.remove_gbs_user(user_id)
        await ctx.tick()

    @globalban.command(name="list")
    @checks.is_owner()
    async def _list(self, ctx):
        o = '\n'.join(k + '\t' + v for k, v in (await self.config.banned()).items())
        if not o:
            await ctx.send(inline("There are no banned users."))
            return
        for page in pagify(o):
            await ctx.send(box(page))

    async def update_gbs(self):
        for gid in await self.config.opted():
            guild = self.bot.get_guild(int(gid))
            if guild is None:
                continue
            for uid, reason in (await self.config.banned()).items():
                try:
                    if int(uid) in [b.user.id for b in await guild.bans()]:
                        async with self.config.guild(guild).banlist() as banlist:
                            if int(uid) not in banlist:
                                banlist.append(uid)
                        continue
                except (AttributeError, discord.Forbidden):
                    logger.exception(f"Error with guild with id '{gid}'")
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
            user = ban.user
            if str(user.id) not in await self.config.banned() or \
                    user.id in await self.config.guild(guild).banlist():
                continue
            try:
                await guild.unban(user)
            except discord.Forbidden:
                pass

    async def remove_gbs_user(self, uid):
        for gid in await self.config.opted():
            guild = self.bot.get_guild(int(gid))
            if guild is None:
                continue
            if uid in await self.config.guild(guild).banlist():
                continue
            try:
                users = [b.user for b in await guild.bans() if b.user.id == int(uid)]
            except (AttributeError, discord.Forbidden):
                logger.exception(f"Error with guild with id '{gid}'")
                continue
            if users:
                try:
                    await guild.unban(users[0])
                except discord.Forbidden:
                    pass
