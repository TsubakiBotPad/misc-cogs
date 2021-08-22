import logging
from io import BytesIO
from typing import Union

import discord
from discord import Object, User
from redbot.core import checks, commands
from redbot.core.utils.chat_formatting import box, inline, pagify
from tsutils.cog_settings import CogSettings
from tsutils.user_interaction import get_user_confirmation

logger = logging.getLogger('red.misc-cogs.globaladmin')


class GlobalAdmin(commands.Cog):
    """Set up authentication for admins for other cogs via tsutils"""
    def __init__(self, bot, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot

        self.settings = GlobalAdminSettings("globaladmin")

    async def red_get_data_for_user(self, *, user_id):
        """Get a user's personal data."""
        data = "No data is stored for user with ID {}.\n".format(user_id)
        return {"user_data.txt": BytesIO(data.encode())}

    async def red_delete_data_for_user(self, *, requester, user_id):
        """Delete a user's personal data.

        No personal data is stored in this cog.
        """
        return

    @commands.group(aliases=['ga', 'gadmin'])
    @checks.is_owner()
    async def globaladmin(self, ctx):
        """Global Admin Commands"""

    @globaladmin.group(aliases=['auths'])
    async def perms(self, ctx):
        """Perm commands

        Cogs automatically register their perms with gadmin; you don't need to add them"""

    def register_perm(self, perm_name, default=False):
        self.settings.add_perm(perm_name, default)

    @perms.command()
    async def reset(self, ctx, perm_name):
        """Restore defaults for a perm for all users"""
        if not await get_user_confirmation(ctx, "Are you sure you want to reset this perm to defaults?"):
            return
        self.settings.refresh_perm(perm_name)
        await ctx.tick()

    @perms.command()
    async def unregister(self, ctx, perm_name):
        """Completely remove a perm from storage"""
        if not await get_user_confirmation(ctx, "Are you sure you want to unregister this perm?"):
            return
        self.settings.refresh_perm(perm_name)
        self.settings.rm_perm(perm_name)
        await ctx.tick()

    @perms.command(name="list")
    async def perm_list(self, ctx):
        """List the avaliable perms"""
        msg = "Perms:\n"
        mlen = max([len(k) for k in self.settings.get_perms().keys()])
        for perm, default in self.settings.get_perms().items():
            msg += " - {}{}(default: {})\n".format(perm, " " * (mlen - len(perm) + 3), default)
        for page in pagify(msg):
            await ctx.send(box(page))

    @globaladmin.command(aliases=["setperm", "setadmin", "addadmin", "addperm"])
    async def grant(self, ctx, user: discord.User, perm, value: bool = True):
        """Grant a user a perm"""
        if self.settings.add_user_perm(user.id, perm, value):
            await ctx.send(inline("Invalid perm name."))
            return
        await ctx.tick()

    @globaladmin.command()
    async def deny(self, ctx, user: discord.User, perm, value: bool = False):
        """Deny a user a perm"""
        if self.settings.add_user_perm(user.id, perm, value):
            await ctx.send(inline("Invalid perm name."))
            return
        await ctx.tick()

    @globaladmin.command()
    async def listusers(self, ctx, perm_name):
        """List all users with a perm"""
        us = self.settings.get_users_with_perm(perm_name)
        us = [str(self.bot.get_user(u) or "Unknown ({})".format(u)) for u in us]
        if not us:
            await ctx.send(inline("No users have this perm."))
        for page in pagify("\n".join(us)):
            await ctx.send(box(page))
            
    def auth_check(self, user: Union[Object, User], perm_name: str, default: bool = False) -> bool:
        return self.settings.get_perm(user.id, perm_name, default=default)


class GlobalAdminSettings(CogSettings):
    def make_default_settings(self):
        config = {
            'perms': {},
            'users': {},
        }
        return config

    def add_user_perm(self, user_id, perm, value=True):
        if perm not in self.bot_settings['perms']:
            return -1
        if user_id not in self.bot_settings['users']:
            self.bot_settings['users'][user_id] = {}
        self.bot_settings['users'][user_id][perm] = value
        self.save_settings()

    def add_perm(self, perm, default=False):
        self.bot_settings['perms'][perm] = default
        self.save_settings()

    def rm_perm(self, perm):
        if perm in self.bot_settings['perms']:
            del self.bot_settings['perms'][perm]
        self.save_settings()

    def refresh_perm(self, perm):
        for user in self.bot_settings['users']:
            if perm in self.bot_settings['users'][user]:
                del self.bot_settings['users'][user][perm]
        self.save_settings()

    def rm_user_perm(self, user_id, perm):
        if perm not in self.bot_settings['perms']:
            return -1
        if user_id not in self.bot_settings['users']:
            return
        if perm not in self.bot_settings['users'][user_id]:
            return
        del self.bot_settings['users'][user_id][perm]
        self.save_settings()

    def get_perm(self, user_id, perm, default=False):
        defaults = {}
        defaults.update(self.bot_settings['perms'])
        defaults.update(self.bot_settings['users'].get(user_id, {}))
        return defaults.get(perm, default)

    def get_perms(self):
        return self.bot_settings['perms']

    def get_users_with_perm(self, perm):
        out = []
        for user in self.bot_settings['users']:
            if perm in self.bot_settings['users'][user]:
                out.append(user)
        return out
