import base64
import discord
import io
import os
import re
from redbot.core import checks, commands, data_manager, Config
from redbot.core.utils.chat_formatting import box, inline, pagify
from tsutils import CogSettings


class Memes(commands.Cog):
    """Custom memes."""

    def __init__(self, bot, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot

        self.config = Config.get_conf(self, identifier=73735)
        self.config.register_guild(memes={})
        self.settings = MemesSettings("memes")

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
    @commands.guild_only()
    @checks.mod_or_permissions(administrator=True)
    async def addmeme(self, ctx, command: str, *, text):
        """Adds a meme

        Example:
        [p]addmeme yourmeme Text you want

        Memes can be enhanced with arguments:
        https://twentysix26.github.io/Red-Docs/red_guide_command_args/
        """
        command = command.lower()
        if command in self.bot.all_commands.keys():
            await ctx.send("That meme is already a standard command.")
            return

        async with self.config.guild(ctx.guild).memes() as cmdlist:
            if command in cmdlist:
                await ctx.send("That command already exists. Use editmeme [command] [text]")
                return
            cmdlist[command] = text
        await ctx.tick()

    @commands.command()
    @commands.guild_only()
    @checks.mod_or_permissions(administrator=True)
    async def editmeme(self, ctx, command: str, *, text):
        """Edits a meme

        Example:
        [p]editmeme yourcommand Text you want
        """
        command = command.lower()
        async with self.config.guild(ctx.guild).memes() as cmdlist:
            if command not in cmdlist:
                await ctx.send("That command doesn't exist. Use addmeme [command] [text]")
                return
            cmdlist[command] = text
        await ctx.tick()

    @commands.command()
    @commands.guild_only()
    @checks.mod_or_permissions(administrator=True)
    async def delmeme(self, ctx, command: str):
        """Deletes a meme

        Example:
        [p]delmeme yourcommand"""
        command = command.lower()
        async with self.config.guild(ctx.guild).memes() as cmdlist:
            if command not in cmdlist:
                await ctx.send("That meme doesn't exist.")
                return
            del cmdlist[command]
        await ctx.tick()

    @commands.command()
    @commands.guild_only()
    @checks.mod_or_permissions(administrator=True)
    async def setmemerole(self, ctx, role: discord.Role):
        """Sets the meme role

        Example:
        [p]setmemerole Regular"""

        self.settings.setPrivileged(ctx.guild.id, role.id)
        await ctx.tick()

    @commands.command()
    @commands.guild_only()
    async def memes(self, ctx):
        """Shows custom memes list"""
        cmdlist = await self.config.guild(ctx.guild).memes()
        msg = "Custom memes:\n"
        for cmd in sorted([cmd for cmd in cmdlist.keys()]):
            msg += " {}{}\n".format(ctx.prefix, cmd)
        for page in pagify(msg):
            await ctx.author.send(box(page))

    @commands.Cog.listener('on_message')
    async def checkCC(self, message):
        if len(message.content) < 2 or isinstance(message.channel, discord.abc.PrivateChannel):
            return

        guild = message.guild
        prefix = await self.get_prefix(message)

        if not prefix:
            return

        # MEME CODE
        role_id = self.settings.getPrivileged(guild.id)
        if role_id is not None:
            role = guild.get_role(role_id)
            if role not in message.author.roles:
                return

        # MEME CODE
        cmdlist = await self.config.guild(ctx.guild).memes()
        cmd = message.content[len(prefix):]
        if cmd in cmdlist.keys():
            cmd = cmdlist[cmd]
            cmd = self.format_cc(cmd, message)
            await message.channel.send(cmd)
        elif cmd.lower() in cmdlist.keys():
            cmd = cmdlist[cmd.lower()]
            cmd = self.format_cc(cmd, message)
            await message.channel.send(cmd)

    async def get_prefix(self, message):
        for p in await self.bot.get_prefix(message):
            if message.content.startswith(p):
                return p
        return False

    def format_cc(self, command, message):
        results = re.findall(r"\{([^}]+)\}", command)
        for result in results:
            param = self.transform_parameter(result, message)
            command = command.replace("{" + result + "}", param)
        return command

    def transform_parameter(self, result, message):
        """
        For security reasons only specific objects are allowed
        Internals are ignored

        Credit:
        https://github.com/Cog-Creators/Red-DiscordBot/blob/V3/develop/redbot/cogs/customcom/customcom.py#L734-L758
        """
        raw_result = "{" + result + "}"
        objects = {
            "message": message,
            "author": message.author,
            "channel": message.channel,
            "server": message.guild
        }
        if result in objects:
            return str(objects[result])
        try:
            first, second = result.split(".")
        except ValueError:
            return raw_result
        if first in objects and not second.startswith("_"):
            first = objects[first]
        else:
            return raw_result
        return str(getattr(first, second, raw_result))


class MemesSettings(CogSettings):
    def make_default_settings(self):
        config = {
            'configs': {}
        }
        return config

    def guildConfigs(self):
        return self.bot_settings['configs']

    def getGuild(self, guild_id: int):
        configs = self.guildConfigs()
        if guild_id not in configs:
            configs[guild_id] = {}
        return configs[guild_id]

    def getPrivileged(self, guild_id: int):
        guild = self.getGuild(guild_id)
        return guild.get('privileged')

    def setPrivileged(self, guild_id: int, role_id: int):
        guild = self.getGuild(guild_id)
        guild['privileged'] = role_id
        self.save_settings()
