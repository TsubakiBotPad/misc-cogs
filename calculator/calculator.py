"""
A cloned and improved version of paddo's calculator cog.
"""

import asyncio
import discord
import re
import sys
from io import BytesIO
from functools import reduce
from redbot.core import Config, checks, commands
from redbot.core.utils.chat_formatting import box, inline, humanize_number
from tsutils.helper_functions import timeout_after

ACCEPTED_TOKENS = (r'[\[\]\-()*+/0-9=.,% |&<>~_^]|>=|<=|==|!=|factorial|randrange|isfinite|copysign'
                   r'|radians|isclose|degrees|randint|lgamma|choice|random|round|log1p|log10|ldexp'
                   r'|isnan|isinf|hypot|gamma|frexp|floor|expm1|atanh|atan2|asinh|acosh|False|range'
                   r'|tanh|sqrt|sinh|modf|log2|fmod|fabs|erfc|cosh|ceil|atan|asin|acos|else|True'
                   r'|fsum|tan|sin|pow|nan|log|inf|gcd|sum|exp|erf|cos|for|not|abs|and|ans|pi|in|is|or'
                   r'|if|e|j|x')

ALTERED_TOKENS = {'^': '**', '_': 'ans'}

HELP_MSG = '''
This calculator works by first validating the content of your query against a whitelist, and then
executing a python eval() on it, so some common syntax wont work.  Here is the full symbol whitelist:
'''


class Calculator(commands.Cog):
    """Calculate expressions via python exec, but safely so users can do it too!"""
    def __init__(self, bot, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot
        self.config = Config.get_conf(self, identifier=857907)
        self.config.register_user(ans={})

        """
        CONFIG: Config
        |   USERS: Config
        |   |   ans: channel_id -> Any
        """

    async def red_get_data_for_user(self, *, user_id):
        """Get a user's personal data."""
        udata = await self.config.user_from_id(user_id).ans()

        data = "You have previous answers stored in {} channels.\n".format(len(udata))

        if not udata:
            data = "No data is stored for user with ID {}.\n".format(user_id)

        return {"user_data.txt": BytesIO(data.encode())}

    async def red_delete_data_for_user(self, *, requester, user_id):
        """Delete a user's personal data."""
        await self.config.user_from_id(user_id).clear()

    @commands.group()
    async def helpcalc(self, ctx):
        """Whispers info on how to use the calculator."""
        help_msg = HELP_MSG + '\n' + ACCEPTED_TOKENS
        try:
            await ctx.author.send(box(help_msg))
        except discord.Forbidden:
            await ctx.send("Failed to send to user.  I might be blocked.")

    @commands.command(aliases=['calc', 'math'])
    @checks.bot_has_permissions(embed_links=True)
    async def calculator(self, ctx, *, inp):
        """Evaluate equations. Use helpcalc for more info."""
        inp = inp.lower()
        unaccepted = re.sub(ACCEPTED_TOKENS, '', inp)
        for token in ALTERED_TOKENS:
            inp = inp.replace(token, ALTERED_TOKENS[token])

        if unaccepted:
            err_msg = 'Found unexpected symbols inside the input: {}'.format(", ".join(unaccepted))
            help_msg = 'Use {0.prefix}helpcalc for info on how to use this command'
            await ctx.send(inline(err_msg + '\n' + help_msg.format(ctx)))
            return

        ans = (await self.config.user(ctx.author).ans()).get(str(ctx.channel.id))

        if re.search(r'\bans\b', inp) and ans is None:
            await ctx.send("You don't have a previous result saved.")
            return

        try:
            timeout_after(.2)(eval)(ans)
        except Exception:
            if re.search(r'\bans\b', inp):
                await ctx.send(f"The previous saved result ({ans}) was invalid.")
                return
            ans = "None"

        if re.sub(ACCEPTED_TOKENS, '', ans):
            if re.search(r'\bans\b', inp):
                await ctx.send(f"The previous saved result ({ans}) was invalid.")
                return
            ans = "None"

        cmd = '''{} -c "from math import *;from random import *;ans = {};print(eval('{}'), end='', flush=True)"'''.format(
            sys.executable, ans, inp)

        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=2)
            if stderr:
                await ctx.send(inline(stderr.decode("utf-8").strip().split('\n')[-1]))
                return
            calc_result = stdout.decode('utf-8').strip()
        except asyncio.TimeoutError:
            await ctx.send(inline('Command took too long to execute. Quit trying to break the bot.'))
            return

        if len(calc_result) > 1024:
            await ctx.send(inline("The result is obnoxiously long!  Try a request under 1k characters!"))
        elif len(calc_result) > 0:
            if re.fullmatch(r'0\.\d+', calc_result):
                calc_result = str(round(float(calc_result), 3))

            em = discord.Embed(color=discord.Color.greyple())
            em.add_field(name='Input', value='`{}`'.format(inp))
            em.add_field(name='Result', value=calc_result)
            if re.fullmatch(r'-?\d{5,}\.?\d*', calc_result):
                em.add_field(name='Result (Fancy)', value=humanize_number(float(calc_result)), inline=False)
            async with self.config.user(ctx.author).ans() as ans:
                if calc_result is not None:
                    ans[ctx.channel.id] = calc_result
            await ctx.send(embed=em)

    @commands.command()
    @checks.bot_has_permissions(embed_links=True)
    async def add(self, ctx, *inp: int):
        """Adds a string of numbers"""
        if not inp:
            await ctx.send_help()
            return
        em = discord.Embed(color=discord.Color.greyple())
        em.add_field(name='Input', value='`{}`'.format('+'.join(map(str, inp))))
        em.add_field(name='Result', value=str(sum(inp)))
        if abs(sum(inp)) >= 1e5:
            em.add_field(name='Result (Fancy)', value=humanize_number(sum(inp)))
        await ctx.send(embed=em)

    @commands.command()
    @checks.bot_has_permissions(embed_links=True)
    async def multiply(self, ctx, *inp: int):
        """Multiplies a string of numbers"""
        if not inp:
            await ctx.send_help()
            return
        em = discord.Embed(color=discord.Color.greyple())
        result = reduce(lambda x, y: x * y, inp, 1)
        em.add_field(name='Input', value='`{}`'.format('*'.join(map(str, inp))))
        em.add_field(name='Result', value=str(result))
        if abs(result) >= 1e5:
            em.add_field(name='Result (Fancy)', value=humanize_number(result))
        await ctx.send(embed=em)
