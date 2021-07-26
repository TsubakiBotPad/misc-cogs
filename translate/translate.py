import logging
from io import BytesIO
from typing import Dict, Type, Optional

import discord
import romkan
from redbot.core import Config, checks, commands
from redbot.core.bot import Red
from redbot.core.utils.chat_formatting import inline

from translate.common.errors import BadTranslation, NoAPIKeyException
from translate.translators.azure_translate import AzureTranslate
from translate.translators.papago import Papago
from translate.translators.translator import Translator

logger = logging.getLogger('red.misc-cogs.translate')

SERVICE_TO_TRANSLATOR: Dict[str, Type[Translator]] = {
    'azure': AzureTranslate,
    'papago': Papago,
}


class Translate(commands.Cog):
    """Translation utilities."""

    def __init__(self, bot: Red):
        super().__init__()
        self.bot = bot
        self.config = Config.get_conf(self, identifier=724757473)
        self.config.register_global(service=None)

        self.translator = None

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
    async def kanrom(self, ctx, *, query):
        """Transliterates Kanji to Romaji"""
        await ctx.send(romkan.to_roma(query))

    async def build_service(self, service: Optional[str] = None):
        if service is None:
            service = await self.config.service()

        if service is None:
            return

        translator_class = SERVICE_TO_TRANSLATOR[service]
        self.translator = await translator_class.build(await self.bot.get_shared_api_tokens(service))

    @commands.group(name="translate", aliases=['translation'], invoke_without_command=True)
    async def translate_command(self, ctx, from_language, to_language, *, text):
        """Translates from one langauge to another

        Not all languages are supported on all services.

        Examples:
        [p]translate fr en Je ne peux parler français
        [p]translate cz en neumím česky
        """

        await self.send_translation(ctx, from_language, to_language, text)

    @translate_command.command()
    @checks.is_owner()
    async def setservice(self, ctx, service):
        if service not in SERVICE_TO_TRANSLATOR:
            await ctx.send(f"`{service}` is not a valid service."
                           f" It must be one of {', '.join(map(inline, SERVICE_TO_TRANSLATOR))}")
            return

        try:
            await self.build_service(service)
        except NoAPIKeyException as e:
            await ctx.send(f"You need to set API keys before setting this service."
                           f" You can set them with `{ctx.prefix}{e.fix_command}`.")
            return

        await self.config.service.set(service)
        await ctx.send(f"The current translation service has been set to `{service}`")

    @commands.command(aliases=['jaus', 'jpen', 'jpus'])
    async def jaen(self, ctx, *, query):
        """Translates from Japanese to English"""
        await self.send_translation(ctx, "ja", "en", query)

    @commands.command(aliases=['zhus'])
    async def zhen(self, ctx, *, query):
        """Translates from Chinese to English"""
        await self.send_translation(ctx, "zh", "en", query)

    async def send_translation(self, ctx, source, target, text):
        if self.translator is None:
            await ctx.send(f"Set up a translator via `{ctx.prefix}translate setservice` first!"
                           f" Avaliable services are: {', '.join(map(inline, SERVICE_TO_TRANSLATOR))}")
            return

        try:
            translation = await self.translate(source, target, text)
        except BadTranslation as e:
            await ctx.send("Translation failed. " + e.message)
            return
        except Exception as e:
            logger.exception("Translation failed.")
            await ctx.send("Translation failed. Please alert the bot owner.")
            return

        text = f"**Original**\n`{text}`\n\n**Translation**\n`{translation}`"
        if await self.bot.embed_requested(ctx.channel, ctx.author) \
                and ctx.me.permissions_in(ctx.channel).embed_links:
            await ctx.send(embed=discord.Embed(description=text))
        else:
            await ctx.send(text)

    async def translate(self, source: str, target: str, text: str) -> str:
        return await self.translator.translate(source, target, text)
