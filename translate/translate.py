import json
import logging
import uuid
from io import BytesIO

import aiohttp
import discord
import romkan
from redbot.core import Config, checks, commands
from redbot.core.bot import Red
from redbot.core.utils.chat_formatting import inline

logger = logging.getLogger('red.misc-cogs.translate')


class Translate(commands.Cog):
    """Translation utilities."""

    def __init__(self, bot: Red, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot
        self.config = Config.get_conf(self, identifier=724757473)
        self.config.register_global(a_api_key=None)

        self.aservice = None

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
    @checks.is_owner()
    async def translation(self, context):
        """Translation utilities."""

    async def build_service(self):
        self.aservice = await self.config.a_api_key()

    @commands.command(aliases=['jaus', 'jpen', 'jpus'])
    @checks.bot_has_permissions(embed_links=True)
    async def jaen(self, ctx, *, query):
        """Translates from Japanese to English"""
        await self.translate_to_embed(ctx, "ja", "en", query)

    @commands.command(aliases=['zhus'])
    @checks.bot_has_permissions(embed_links=True)
    async def zhen(self, ctx, *, query):
        """Translates from Chinese to English"""
        await self.translate_to_embed(ctx, "zh", "en", query)

    @commands.command()
    @checks.bot_has_permissions(embed_links=True)
    async def translate(self, ctx, from_language, to_language, *, query):
        """Translates from one langauge to another"""
        try:
            await self.translate_to_embed(ctx, from_language, to_language, query)
        except KeyError:
            await ctx.send("Invalid query.")

    @commands.command()
    async def kanrom(self, ctx, *, query):
        """Transliterates Kanji to Romanji"""
        await ctx.send(romkan.to_roma(query))

    async def a_translate_lang(self, source, target, query):
        endpoint = "https://api.cognitive.microsofttranslator.com"

        path = '/translate'
        constructed_url = endpoint + path

        params = {
            'api-version': '3.0',
            'from': source,
            'to': target,
        }
        headers = {
            'Ocp-Apim-Subscription-Key': self.aservice,
            'Content-type': 'application/json',
            'X-ClientTraceId': str(uuid.uuid4())
        }
        body = [{'text': query}]

        async with aiohttp.ClientSession() as session:
            async with session.post(constructed_url, params=params, headers=headers, json=body) as resp:
                res = json.loads(await resp.read())

        return res[0]['translations'][0]['text']

    async def translate_to_embed(self, ctx, source, target, query):
        if not self.aservice:
            await ctx.send(inline('Set up an API key first!'))
            return

        translation = await self.a_translate_lang(source, target, query)
        await ctx.send(
            embed=discord.Embed(description='**Original**\n`{}`\n\n**Translation**\n`{}`'.format(query, translation)))

    @translation.command()
    async def setakey(self, ctx, api_key):
        """Sets the azure api key."""
        await self.config.a_api_key.set(api_key)
        await ctx.tick()

    @translation.command()
    async def getakey(self, ctx):
        """Gets the azure api key."""
        await ctx.author.send(await self.config.a_api_key())
