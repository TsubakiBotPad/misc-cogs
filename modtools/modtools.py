from io import BytesIO

import discord
from redbot.core import checks, commands
from redbot.core.utils.chat_formatting import box, inline, pagify
from tsutils.user_interaction import send_cancellation_message


class ModTools(commands.Cog):
    """Some chill commands for mods"""

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

    @commands.command()
    @checks.bot_has_permissions(manage_nicknames=True)
    async def revertname(self, ctx):
        """Unsets your nickname"""
        try:
            await ctx.author.edit(nick=None)
            await ctx.tick()
        except discord.Forbidden:
            await send_cancellation_message(ctx,
                                            "Sorry, I can't revert your nickname because you have a role that is higher than mine!")

    @commands.command()
    @commands.guild_only()
    @checks.mod_or_permissions(manage_guild=True)
    async def mentionable(self, ctx, role: discord.Role):
        """Toggle the mentionability of a role."""
        try:
            new_mentionable = not role.mentionable
            await role.edit(mentionable=new_mentionable)
            await ctx.send(inline('Role is now {}mentionable'.format('' if new_mentionable else 'un')))
        except Exception as ex:
            await ctx.send(inline('Error: failed to alter role'))

    @commands.command()
    @checks.mod_or_permissions(manage_guild=True)
    async def onlinecount(self, ctx):
        """Counts online members of a guild"""
        gonline = gmobile = conline = cmobile = 0
        for member in ctx.guild.members:
            gonline += member.status is discord.Status.online
            gmobile += member.is_on_mobile()
        for member in ctx.channel.members:
            conline += member.status is discord.Status.online
            cmobile += member.is_on_mobile()
        await ctx.send(box("There are {} members online ({} online on mobile).\n"
                           "There are {} members online in this channel ({} online on mobile).")
                       .format(gonline, gmobile, conline, cmobile))

    @commands.command()
    async def servercount(self, ctx):
        """Check how many servers this bot is in"""
        await ctx.send("{} is in {} servers.".format(self.bot.user.name, len(self.bot.guilds)))

    @commands.command(aliases=['usersearch'])
    @checks.mod_or_permissions(manage_messages=True)
    async def usernamesearch(self, ctx, search):
        """Lists all users who have a specified string in their name"""
        users = []
        for member in ctx.guild.members:
            if search.lower() in member.name.lower():
                users.append("{} - {}".format(member.mention, member.id))
        if users:
            msg = "\n".join(users)
            for page in pagify(msg):
                await ctx.send(page)
        else:
            await ctx.send("No users found with string `{}`".format(search))
