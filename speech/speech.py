import asyncio
import ctypes.util
import logging
import os
from io import BytesIO

import discord
from azure.cognitiveservices.speech import SpeechConfig, SpeechSynthesizer
from redbot.core import checks, commands
from redbot.core.bot import Red
from redbot.core.utils.chat_formatting import inline
from tsutils.cog_settings import CogSettings
from tsutils.helper_functions import corowrap

logger = logging.getLogger('red.misc-cogs.speech')

try:
    if not discord.opus.is_loaded():
        discord.opus.load_opus(ctypes.util.find_library('opus'))
except:  # Missing opus
    logger.warning('Failed to load opus')
    opus = None
else:
    opus = True

SPOOL_PATH = "/tmp/misc-cogs/speech/spool.mp3"

TSUBAKI_SSML = """
<speak version="1.0" xmlns="https://www.w3.org/2001/10/synthesis" xmlns:mstts="https://www.w3.org/2001/mstts" xml:lang="en-US">
  <voice name="zh-CN-XiaoxiaoNeural">
    <prosody rate="-30.00%" pitch="-1Hz">
      <mstts:express-as style="calm" styledegree="2">
        {text}
      </mstts:express-as>
    </prosody>
  </voice>
</speak>"""

class Speech(commands.Cog):
    """Speech utilities."""

    def __init__(self, bot: Red, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot
        self.settings = SpeechSettings("speech")

        self.aservice = None
        self.try_setup_apis()
        self.busy = False

    async def red_get_data_for_user(self, *, user_id):
        """Get a user's personal data."""
        data = "No data is stored for user with ID {}.\n".format(user_id)
        return {"user_data.txt": BytesIO(data.encode())}

    async def red_delete_data_for_user(self, *, requester, user_id):
        """Delete a user's personal data.

        No personal data is stored in this cog.
        """
        return

    def try_setup_apis(self):
        api_key = self.settings.get_azure_key()
        if api_key:
            try:
                self.aservice = SpeechConfig(subscription=api_key, region="eastus")
            except:
                logger.warning('Azure speech setup failed.  Check your API key.')

    @commands.group()
    @checks.is_owner()
    async def speech(self, ctx):
        """Speech utilities."""

    @commands.command()
    async def vcsay(self, ctx, *, text):
        """Speak into the current user's voice channel."""
        if not self.aservice:
            await ctx.send('Set up an Azure API key file first via `{}setapikey!`'.format(ctx.prefix))
            return

        voice = ctx.author.voice
        if not voice:
            await ctx.send(inline('You must be in a voice channel to use this command'))
            return

        channel = voice.channel

        if len(text) > 300:
            await ctx.send(inline('Command is too long'))
            return

        await self.speak(ctx, channel, text)


    async def speak(self, ctx, channel, text: str):
        if self.busy:
            await ctx.send(inline('Sorry, saying something else right now'))
            return False
        else:
            self.busy = True

        audio_data = None
        audio_data = self.azure_text_to_speech(text)

        if audio_data is None:
            await ctx.send(inline("There are no avaliable services"))
            return

        try:
            os.makedirs(os.path.dirname(SPOOL_PATH), exist_ok=True)
            with open(SPOOL_PATH, 'wb') as out:
                out.write(audio_data)

            await self.play_path(channel, SPOOL_PATH)
            return True
        finally:
            self.busy = False
        return False

    async def play_path(self, channel, audio_path: str):
        existing_vc = channel.guild.voice_client
        if existing_vc:
            await existing_vc.disconnect(force=True)

        voice_client = None
        try:
            voice_client = await channel.connect()
            await asyncio.sleep(.5)
            b_options = '-guess_layout_max 0 -v 16'
            a_options = ''

            audio_source = discord.FFmpegPCMAudio(audio_path, options=a_options, before_options=b_options)
            voice_client.play(audio_source, after=corowrap(voice_client.disconnect(), self.bot.loop))
            return True
        except Exception as e:
            logger.exception("Exception:")
            if voice_client:
                try:
                    await voice_client.disconnect()
                except:
                    pass
            return False

    @speech.command()
    @checks.is_owner()
    async def setapikey(self, ctx, api_key):
        """Sets the azure api key."""
        self.settings.set_azure_key(api_key)
        await ctx.tick()

    def azure_text_to_speech(self, text):
        try:
            synthesizer = SpeechSynthesizer(speech_config=self.aservice, audio_config=None)
            ssml = TSUBAKI_SSML.format(text=text)
            result = synthesizer.speak_ssml_async(ssml).get()
            data = result.audio_data
            if not data:
                logger.error(str(result.cancellation_details))
            return data
        except Exception as e:
            logger.exception("Azure Text to Speech Failiure:")


class SpeechSettings(CogSettings):
    def make_default_settings(self):
        config = {
            'azure_api_key': ''
        }
        return config

    def get_azure_key(self):
        return self.bot_settings.get('azure_api_key')

    def set_azure_key(self, api_key):
        self.bot_settings['azure_api_key'] = api_key
        self.save_settings()

    def valid_keys(self):
        return any(self.bot_settings.values())
