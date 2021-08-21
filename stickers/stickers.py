import re
from collections import defaultdict
from io import BytesIO
from typing import Any

from discord import Forbidden
from discordmenu.embed.components import EmbedBodyImage, EmbedFooter, EmbedMain
from discordmenu.embed.view import EmbedView
from redbot.core import Config, commands
from redbot.core.bot import Red
from redbot.core.utils.chat_formatting import box, pagify
from tsutils.cog_settings import CogSettings
from tsutils.cogs.globaladmin import auth_check


class Stickers(commands.Cog):
    """Sticker commands."""

    def __init__(self, bot: Red, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot

        self.settings = StickersSettings("stickers")

        self.config = Config.get_conf(self, identifier=57137325)
        self.config.register_global(stickers={})

        GADMIN_COG: Any = self.bot.get_cog("GlobalAdmin")
        if GADMIN_COG:
            GADMIN_COG.register_perm("stickeradmin")

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
    @auth_check("stickeradmin")
    async def sticker(self, context):
        """Global stickers."""

    @sticker.command(usage="<command> [subcommand] <link>")
    async def add(self, ctx, command, subcommand, link=None):
        """Adds a sticker

        Example:
        !stickers add "whale happy" link_to_happy_whale
        """
        if link is None:
            link = subcommand
        else:
            command = f"{command} {subcommand}"
        if command.count(" ") > 1:
            return await ctx.send("You can't have more than one space.")

        command = command.lower()
        if command.split(" ")[0] in self.bot.all_commands.keys():
            return await ctx.send("That is already a standard command.")

        async with self.config.stickers() as stickers:
            stickers[command] = link
        await ctx.tick()

    @sticker.command()
    async def delete(self, ctx, *, command):
        """Deletes a sticker

        Example:
        !stickers delete "whale happy" """
        command = command.lower().strip()
        async with self.config.stickers() as stickers:
            if command not in stickers:
                return await ctx.send("That sticker doesn't exist")
            del stickers[command]
        await ctx.tick()

    @commands.command()
    async def stickers(self, ctx):
        """Shows all stickers"""
        stickers = await self.config.stickers()

        if not stickers:
            return await ctx.send("There are no stickers yet")

        prefixes_list = defaultdict(list)
        other_list = list()

        for sticker in stickers:
            if (match := re.fullmatch(r'(.+) (.+)', sticker)):
                grp = match.group(1)
                prefixes_list[grp].append(match.group(2))
            else:
                other_list.append(sticker)

        msg = "Stickers:\n"
        for cmd in sorted(other_list):
            msg += f" {ctx.prefix}{cmd}\n"

        msg += "\nSticker Packs:\n"
        for prefix in sorted(prefixes_list):
            msg += f" {ctx.prefix}{prefix} [...]\n  "

            for suffix in sorted(prefixes_list[prefix]):
                msg += f" {suffix}"
            msg += "\n\n"

        for page in pagify(msg):
            await ctx.author.send(box(page))

    @commands.Cog.listener("on_message")
    async def check_for_sticker_request(self, message):
        prefix = (await self.bot.get_prefix(message))[0]
        if not message.content.startswith(prefix):
            return

        cmdlist = await self.config.stickers()
        cmd = message.content[len(prefix):].strip()
        if cmd.lower() in cmdlist.keys():
            await message.channel.send(embed=EmbedView(
                embed_main=EmbedMain(),
                embed_body_image=EmbedBodyImage(cmdlist[cmd.lower()]),
                embed_footer=EmbedFooter(message.content + ' posted by ' + message.author.name),
            ).to_embed())
            try:
                await message.delete()
            except Forbidden:
                pass


class StickersSettings(CogSettings):
    def make_default_settings(self):
        config = {
            'admins': [],
            'c_commands': {}
        }
        return config
