import logging
import re
import unicodedata
from io import BytesIO

from redbot.core import checks
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.utils.chat_formatting import inline

import discord

logger = logging.getLogger('red.misc-cogs.emoji')


class EmojiCog(commands.Cog):
    """Steal some emoji with this cog."""

    def __init__(self, bot: Red, *args, **kwargs):
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

    @commands.command()
    @checks.mod_or_permissions(manage_emojis=True)
    @checks.bot_has_permissions(manage_emojis=True)
    async def stealemoji(self, ctx, *, emojis):
        """Steal some emoji and add them to this server \N{CAT FACE WITH WRY SMILE} \N{SMILING FACE WITH HORNS}"""
        try:
            m = await commands.MessageConverter().convert(ctx, emojis)
            emojis = m.content
        except commands.MessageNotFound:
            pass

        emojis = [await commands.PartialEmojiConverter().convert(ctx, e) for e in
                  re.findall(r'<a?:\w+:\d+>', emojis)]

        if not emojis:
            await ctx.send_help()
            return

        ae = list(ctx.guild.emojis) + emojis
        if len([e for e in ae if not e.animated]) > ctx.guild.emoji_limit:
            await ctx.send("Not enough emoji slots")
        if len([e for e in ae if e.animated]) > ctx.guild.emoji_limit:
            await ctx.send("Not enough animated emoji slots")

        async with ctx.typing():
            for emoji in emojis:
                if emoji.name in [e.name for e in ctx.guild.emojis]:
                    continue
                await ctx.guild.create_custom_emoji(name=emoji.name, image=await emoji.url.read())
        await ctx.tick()

    @commands.command()
    async def unicodename(self, ctx, glyph):
        """Get the name of a unicode (non-custom) emoji or glyph (set of one or more unicode characters)"""
        if len(glyph) > 5:
            await ctx.send("The input must be a single unicode (non-custom) emoji.")
            return
        await ctx.send(inline(''.join(f'\\N{{{unicodedata.name(c)}}}' for c in glyph)))
