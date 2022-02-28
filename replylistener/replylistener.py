import logging
import re
from io import BytesIO
from typing import Optional

import discord
from discordmenu.embed.components import EmbedField, EmbedMain
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
    async def on_message(self, message: discord.Message):
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

        if ref_message is None
        if not (channel := self.bot.get_channel(cid)) \
                or not (ref_message := await channel.fetch_message(mid)):
            # Link does not point to a valid message
            return

        return EmbedView(
            EmbedMain(
                title=ref_message.author.name,
                description=get_description(props.score)
            ),
            embed_fields=[
                EmbedField('Matched Name Tokens', Box(props.name_tokens)),
                EmbedField('Matched Modifier Tokens', Box(props.modifier_tokens)),
                EmbedField('Equally-scoring matches', Box(props.lower_priority_monsters)),
            ],
            embed_footer=embed_footer_with_state(state),
        )
