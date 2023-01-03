import logging
import re
from io import BytesIO

import discord
from contextlib2 import suppress
from discordmenu.embed.components import EmbedAuthor, EmbedFooter, EmbedMain
from discordmenu.embed.view import EmbedView
from redbot.core import commands
from tsutils.menu.view.closable_embed import ClosableEmbedViewState
from tsutils.query_settings.query_settings import QuerySettings

from linklistener.menu.closable_embed import ClosableEmbedMenu
from linklistener.view.link_listener_view import LinkListenerViewProps, LinkListenerView

logger = logging.getLogger('red.misc-cogs.linklistener')

LINK_REGEX = r'https?://discord.com/channels/(?:@me|\d+)/(\d+)/(\d+)'


class LinkListener(commands.Cog):
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

        if message.author.bot:
            return

        if not re.search(LINK_REGEX, message.content):
            return

        cid, mid = map(int, re.search(LINK_REGEX, message.content).groups())
        channel = self.bot.get_channel(cid)
        if channel is None:
            return
        try:
            ref_message = await channel.fetch_message(mid)
        except (discord.NotFound, discord.Forbidden):
            return

        if not ref_message.content:
            if ref_message.author == self.bot.user and ref_message.embeds:
                return await message.channel.send(embeds=ref_message.embeds)
            return
        ctx = await self.bot.get_context(message)
        menu = ClosableEmbedMenu.menu()
        props = LinkListenerViewProps(ref_message.author.name, ref_message.jump_url, ref_message.author.avatar,
                                      ref_message.content, message.author)
        qs = await QuerySettings.extract_raw(message.author, self.bot, "")
        state = ClosableEmbedViewState(message.author.id, ClosableEmbedMenu.MENU_TYPE, "", qs,
                                       LinkListenerView.VIEW_TYPE, props)
        return await menu.create(ctx, state)
