import asyncio
import logging
import re
from io import BytesIO

import discord
from redbot.core import checks, commands
from redbot.core.bot import Red
from redbot.core.utils.chat_formatting import box, inline
from tsutils.emoji import char_to_emoji, fix_emojis_for_server, replace_emoji_names_with_code

logger = logging.getLogger('red.misc-cogs.fancysay')


class FancySay(commands.Cog):
    """Allows the user to make the bot say things in a variety of ways."""
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

    @commands.group()
    async def fancysay(self, ctx):
        """Make the bot say fancy things (via embeds)."""

    @commands.guild_only()
    @checks.mod_or_permissions(manage_messages=True)
    @fancysay.command()
    async def pingrole(self, ctx, role: discord.Role, *, text):
        """[p]fancysay pingrole rolename this is the text to ping

        1) Converts a role to mentionable
        2) Posts the message + ping in the current channel
        3) Sets the role to unmentionable
        4) Deletes the input message

        The role must be unmentionable before this command for safety.
        """
        if role.mentionable:
            await ctx.send(inline('Error: role is already mentionable'))
            return

        try:
            await role.edit(mentionable=True)
        except Exception as ex:
            await ctx.send(inline('Error: failed to set role mentionable'))
            if ex.text == "Missing Permissions":
                message = await ctx.send(inline('Make sure this bot\'s role is higher than the one you\'re mentioning'))
                await asyncio.sleep(3)
                await message.delete()
            return

        await ctx.message.delete()
        await asyncio.sleep(1)
        await ctx.send('From {}:\n{}\n{}'.format(ctx.author.mention, role.mention, text))

        try:
            await role.edit(mentionable=False)
        except Exception as ex:
            await ctx.send(inline('Error: failed to set role unmentionable'))
            return

    @fancysay.command()
    async def emoji(self, ctx, *, text):
        """Speak the provided text as emojis, deleting the original request if in a guild"""
        if ctx.guild is not None:
            if not ctx.author.guild_permissions.manage_messages:
                await ctx.send("You can only use this command in DMs!")
                return
            await ctx.message.delete()
        new_msg = ""
        for char in text:
            if char.isalpha():
                new_msg += char_to_emoji(char) + ' '
            elif char == ' ':
                new_msg += '  '
            elif char.isspace():
                new_msg += char

        if len(new_msg):
            await ctx.send(new_msg)

    @commands.command()
    @checks.mod_or_permissions(add_reactions=True)
    async def emojireact(self, ctx, *, text):
        """React to a message with emoji"""
        EXTRA = {
            "a": ["\N{NEGATIVE SQUARED LATIN CAPITAL LETTER A}"],
            "b": ["\N{NEGATIVE SQUARED LATIN CAPITAL LETTER B}"],
            "o": ["\N{NEGATIVE SQUARED LATIN CAPITAL LETTER O}"],
        }

        *text, message_t = text.split()
        try:
            message = await commands.MessageConverter().convert(ctx, message_t)
            text = "".join(text)
        except:
            message = None
            text = "".join(text + [message_t])

        if message is None:
            message = (await ctx.channel.history(limit=2).flatten())[1]

        text = re.sub(r'[^a-z0-9]', '', text.lower())

        if len(message.reactions) + len(text) > 20:
            await ctx.send("I don't have enough room to spell this.")
            return

        for char in text:
            if text.count(char) > len(EXTRA.get(char, [])) + 1:
                await ctx.send("It is not possible to make this using emoji.")
                return

        await ctx.message.delete()


        used = ""
        for char in text:
            emote = ([char_to_emoji(char)] + EXTRA.get(char, []))[used.count(char)]
            await message.add_reaction(emote)
            used += char


    @fancysay.command(aliases=['tdif'])
    @commands.guild_only()
    @checks.mod_or_permissions(manage_messages=True)
    @checks.bot_has_permissions(embed_links=True)
    async def title_description_image_footer(self, ctx, title, description, image, footer):
        """[title] [description] [image_url] [footer_text]

        You must specify a title. You can omit any of description, image, or footer.
        To omit an item use empty quotes. For the text fields, wrap your text in quotes.
        The bot will automatically delete your 'say' command if it can

        e.g. say with all fields:
        fancysay title_description_image_footer "My title text" "Description text" "xyz.com/image.png" "source: xyz.com"

        e.g. say with only title and image:
        fancysay title_descirption_image_footer "My title" "" "xyz.com/image.png" ""
        """
        
        embed = discord.Embed()
        if len(title):
            embed.title = title
        if len(description):
            embed.description = description
        if len(image):
            embed.set_image(url=image)
        if len(footer):
            embed.set_footer(text=footer)

        try:
            await ctx.send(embed=embed)
            await ctx.message.delete()
        except Exception as error:
            await ctx.send(box(error.text))

    @commands.command(aliases=["parrot", "repeat"])
    @checks.mod_or_permissions(manage_messages=True)
    async def say(self, ctx, *, message):
        """Make the bot parrot a phrase."""
        message = self.emojify(message)
        await ctx.send(message)

    @commands.command(aliases=["testparrot", "testrepeat"])
    @checks.mod_or_permissions(manage_messages=True)
    async def testsay(self, ctx, *, message):
        """Make the bot parrot a phrase without smart emoji replacements."""
        await ctx.send(message)

    @commands.command()
    @checks.mod_or_permissions(manage_messages=True)
    async def mask(self, ctx, *, message):
        """Sends a message as the bot."""
        message = self.emojify(message)
        await ctx.message.delete()
        await ctx.send(message)

    @commands.command()
    @checks.mod_or_permissions(manage_messages=True)
    async def yell(self, ctx, *, message):
        """Yells some text."""
        message = self.emojify(message)
        await ctx.send(message.upper().rstrip(",.!?") + "!!!!!!")

    def emojify(self, message):
        emojis = list()
        for guild in self.bot.guilds:
            emojis.extend(guild.emojis)
        message = replace_emoji_names_with_code(emojis, message)
        return fix_emojis_for_server(emojis, message)
