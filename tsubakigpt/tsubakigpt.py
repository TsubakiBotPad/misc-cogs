import os
import random
import re
import time
from io import BytesIO
from typing import Dict

import discord
import pandas as pd
from redbot.core import commands
from redbot.core.data_manager import bundled_data_path


class TsubakiGPT(commands.Cog):
    """A fun bot AI!"""

    def __init__(self, bot, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot
        self.words = pd.read_csv(os.path.join(bundled_data_path(self), "sentiment.csv"),
                                 index_col=0)['sentiment']

    async def red_get_data_for_user(self, *, user_id):
        """Get a user's personal data."""
        return {"user_data.txt": BytesIO("No data is stored for user with ID {}.\n".encode())}

    async def red_delete_data_for_user(self, *, requester, user_id):
        """Delete a user's personal data."""
        return

    def get_temperature(self) -> float:
        secs = time.time() - 1680310800
        total_seconds = 108000
        return 1.0 - secs*2/total_seconds

    def get_sentence(self, temperature: float, add_words: Dict[str, float], n: int) -> str:
        weights = 1 - (self.words - temperature).abs()
        weights = weights[weights >= 0]
        ret = random.choices(weights.index, weights, k=n)
        for word, chance in add_words.items():
            if random.random() < chance:
                ret.append(word)
        random.shuffle(ret)
        for i in range(len(ret)-1):
            if random.random() < .05:
                ret[i] += ','
            elif random.random() < .05:
                ret[i] += random.choice('.!?') + ' '
        sentence = " ".join(ret)
        sentence = sentence[0].upper() + sentence[1:]
        sentence = re.sub(r'[.?!] {2}[a-z]', lambda m: m.group().upper(), sentence)
        sentence += random.choice('.!?')
        return sentence

    @commands.Cog.listener('on_message')
    async def on_message(self, message: discord.Message):
        if await self.bot.cog_disabled_in_guild(self, message.guild):
            return
        myname = message.guild.me.name.lower() if message.guild is not None else "tsubaki"
        if not (message.content.lower().startswith(f"hello {myname}")
                or message.content.lower().startswith(f"hey {myname}")
                or message.content.lower().startswith(f"hi {myname}")):
            return
        words = {
            message.author.name: .4,
            'Tsubaki': .4,
            'Miru': .05,
            'Aradia': .05,
            'River': .05,
            'Puzzle & Dragons': .1,
        }
        sentence = self.get_sentence(self.get_temperature(), words, random.randint(10, 20))
        await message.channel.send(sentence)
