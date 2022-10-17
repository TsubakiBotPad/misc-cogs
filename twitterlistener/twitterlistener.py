import asyncio
from contextlib import suppress
import re
from io import BytesIO
from redbot.core import Config, checks, commands
from PIL import Image
import discord
import requests


class TwitterListener(commands.Cog):
    """Images from Twitter Post"""

    def __init__(self, bot, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot

        self.config = Config.get_conf(self, identifier=10100779)
        self.config.register_channel(enabled=False)

    async def red_get_data_for_user(self, *, user_id):
        """Get a user's personal data."""
        data = "No data is stored for user with ID {}.\n".format(user_id)
        return {"user_data.txt": BytesIO(data.encode())}

    async def red_delete_data_for_user(self, *, requester, user_id):
        """Delete a user's personal data.

        No personal data is stored in this cog.
        """
        return

    @commands.Cog.listener('on_message')
    async def on_message(self, message):
        channel = message.channel
        content = message.content
        author = message.author
        if not await self.config.channel(channel).enabled():
            return
        if message.guild is None:  # dms
            return
        if message.author == self.bot.user:  # dont reply to self
            return
        if await self.is_command(message):  # skip commands
            return
        links = re.findall(r'(https?://twitter[^\s]+)', content)
        if len(links) == 0:
            return
        new_msg = content
        for link in links:
            new_msg = new_msg.replace(link, f'[Twitter Link]({link})')
        send_embed = discord.Embed(description=new_msg)
        send_embed.set_author(name=author.display_name, icon_url=author.display_avatar.url)
        await channel.send(embed=send_embed)
        # discord takes a few seconds to generate the embed for new posts
        await asyncio.sleep(3)
        embeds = message.embeds
        for embed in embeds:
            if (embed.image):
                img = Image.open(requests.get(embed.image.proxy_url, stream=True).raw)
                with BytesIO() as image_binary:
                    img.save(image_binary, 'PNG')
                    image_binary.seek(0)
                    await channel.send(file=discord.File(fp=image_binary, filename='image.png'))
        with suppress(discord.HTTPException):
            await message.delete()

    @commands.group(aliases=['twtlistener'])
    async def twitterlistener(self, ctx):
        """Commands pertaining to Twitter Listener"""

    @twitterlistener.command()
    @checks.admin_or_permissions(manage_messages=True)
    async def enable(self, ctx):
        """Enable Twitter listener in this channel"""
        await self.config.channel(ctx.channel).enabled.set(True)
        await ctx.send("Enabled Twitter listener in this channel.")

    @twitterlistener.command()
    @checks.admin_or_permissions(manage_messages=True)
    async def disable(self, ctx):
        """Disable Twitter listener in this channel"""
        await self.config.channel(ctx.channel).enabled.set(False)
        await ctx.send("Disabled Twitter listener in this channel.")

    async def is_command(self, msg):
        prefixes = await self.bot.get_valid_prefixes()
        for p in prefixes:
            if msg.content.startswith(p):
                return True
        return False
