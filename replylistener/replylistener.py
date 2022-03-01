import logging
import re
from io import BytesIO
from typing import Optional

import discord
from discordmenu.embed.components import EmbedAuthor, EmbedField, EmbedFooter, EmbedMain, EmbedThumbnail
from discordmenu.embed.view import EmbedView
from redbot.core import commands

logger = logging.getLogger('red.misc-cogs.replylistener')

LINK_REGEX = r'https?://discord.com/channels/(?:@me|\d+)/(\d+)/(\d+)'


class ReplyListener(commands.Cog):
    """Turn message links into nice embeds"""

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

    @commands.Cog.listener("on_message")
    async def on_link_only(self, message: discord.Message):
        if await self.bot.cog_disabled_in_guild(self, message.guild):
            return

        if (not (match := re.fullmatch(LINK_REGEX, message.content))) \
                or message.attachments or message.embeds:
            # Message is not just a link
            return

        cid, mid = map(int, match.groups())

        channel = self.bot.get_channel(cid)
        if channel is None:
            return
        try:
            ref_message = await channel.fetch_message(mid)
        except (discord.NotFound, discord.Forbidden):
            return

        if not message.content:
            return

        await message.channel.send(embed=self.message_to_embed(ref_message, message.author))

    @commands.Cog.listener("on_message")
    async def on_reply(self, message: discord.Message):
        if await self.bot.cog_disabled_in_guild(self, message.guild):
            return

        if not message.reference:
            # Message is not a reply
            return

        channel = self.bot.get_channel(message.reference.channel_id)
        if channel is None:
            return
        try:
            ref_message = await channel.fetch_message(message.reference.message_id)
        except (discord.NotFound, discord.Forbidden):
            return

        if not message.content:
            return

        await message.channel.send(embed=self.message_to_embed(ref_message, message.author))

    def message_to_embed(self, message: discord.Message, requester: discord.User) -> discord.Embed:
        return EmbedView(
            embed_main=EmbedMain(description=message.content),
            embed_author=EmbedAuthor(message.author.name, '', message.author.avatar_url),
            embed_footer=EmbedFooter(f"Quoted by {requester}", icon_url=requester.avatar_url),
        ).to_embed()
