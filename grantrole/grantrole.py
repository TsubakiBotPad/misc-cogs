import discord
import logging
from redbot.core import checks, commands, Config, modlog
from redbot.core.utils.chat_formatting import box, inline, pagify

logger = logging.getLogger('red.misc-cogs.grantrole')

class GrantRole(commands.Cog):
    def __init__(self, bot, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot
        self.config = Config.get_conf(self, identifier=624772073)
        self.config.register_guild(messages={}, on_join=[], on_react={})

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
    @checks.mod_or_permissions(manage_roles=True)
    async def grantrole(self, ctx):
        """Grant roles on triggers"""

    @grantrole.group()
    async def onjoin(self, ctx):
        """Manipulate roles granted on join"""

    @onjoin.command(name="add")
    async def onjoin_add(self, ctx, role: discord.Role):
        if not await self.can_assign(ctx, role):
            return
        async with self.config.guild(ctx.guild).on_join() as on_join:
            if role.id in on_join:
                await ctx.send("This role is already assigned on join.")
                return
            on_join.append(role.id)
        await ctx.tick()

    @onjoin.command(name="remove")
    async def onjoin_remove(self, ctx, role: discord.Role):
        async with self.config.guild(ctx.guild).on_join() as on_join:
            if role.id not in on_join:
                await ctx.send("This role isn't assigned on join.")
                return
            on_join.remove(role.id)
        await ctx.tick()

    @onjoin.command(name="list")
    async def onjoin_list(self, ctx):
        o = []
        for role_id in await self.config.guild(ctx.guild).on_join():
            o.append("#{}".format(ctx.guild.get_role(role_id) or "deleted_role"))
        await ctx.send(box("\n".join(o)))

    @grantrole.group()
    async def onreact(self, ctx):
        """Manipulate roles granted on emoji react"""

    @onreact.command(name="add")
    async def onreact_add(self, ctx, message: discord.Message, emoji: discord.Emoji, role: discord.Role):
        """Add a role on a reaction"""
        if not await self.can_assign(ctx, role):
            return
        await message.add_reaction(emoji)
        async with self.config.guild(ctx.guild).on_react() as on_react:
            on_react[str(message.id)] = on_react.get(str(message.id), {})
            on_react[str(message.id)][str(emoji.id)] = role.id
        await ctx.tick()

    @onreact_add.error
    async def onreact_error(self, ctx, error):
        if isinstance(error, commands.errors.ConversionFailure):
            await ctx.send(("I do not have access to `{}`.  Please add me to the"
                            " server it's hosted in or use a different emoji.".format(error.argument)))
        elif isinstance(error, discord.ext.commands.UserInputError):
            await ctx.send_help()
        else:
            raise error

    @onreact.command(name="remove")
    async def onreact_remove(self, ctx, message: discord.Message, emoji: discord.Emoji):
        """Remove a role from a reaction"""
        await message.add_reaction(emoji)
        async with self.config.guild(ctx.guild).on_react() as on_react:
            if not on_react.get(str(message.id)) or not on_react.get(str(message.id), {}).get(str(emoji.id)):
                await ctx.send("That emoji isn't mapped to a role.")
                return
            del on_react[str(message.id)][str(emoji.id)]
        await ctx.tick()

    @commands.Cog.listener('on_member_join')
    async def on_member_join(self, member):
        if not hasattr(member, 'guild') or await self.bot.cog_disabled_in_guild(self, member.guild):
            return
        roles = await self.config.guild(member.guild).on_join()
        try:
            await member.add_roles(*roles, reason="On Join Role Grant")
        except discord.Forbidden:
            logger.exception("Unable to add roles in guild: {}".format(guild.id))

    @commands.Cog.listener('on_reaction_add')
    async def on_reaction_add(self, reaction, member):
        if not hasattr(member, 'guild') or await self.bot.cog_disabled_in_guild(self, member.guild):
            return
        roles = await self.config.guild(member.guild).on_react()
        try:
            emoji = reaction.emoji if isinstance(reaction.emoji, str) else str(reaction.emoji.id)
            role = roles.get(str(reaction.message.id), {}).get(emoji)
            if role is None:
                return
            await member.add_roles(reaction.message.guild.get_role(role), reason="On React Role Grant")
        except discord.Forbidden:
            logger.exception("Unable to add roles in guild: {}".format(guild.id))

    @commands.Cog.listener('on_reaction_remove')
    async def on_reaction_remove(self, reaction, member):
        if await self.bot.cog_disabled_in_guild(self, member.guild):
            return
        roles = await self.config.guild(member.guild).on_react()
        try:
            emoji = reaction.emoji if isinstance(reaction.emoji, str) else str(reaction.emoji.id)
            role = roles.get(str(reaction.message.id), {}).get(emoji)
            if role is None:
                return
            await member.remove_roles(reaction.message.guild.get_role(role), reason="On React Role Removal")
        except discord.Forbidden:
            logger.exception("Unable to add roles in guild: {}".format(guild.id))

    async def can_assign(self, ctx, role):
        if ctx.author.id == ctx.guild.owner_id:
            return True
        if ctx.author.top_role < role:
            await ctx.send("You're not high enough on the heirarchy enough assign this role.")
            return False
        if ctx.me.top_role < role:
            await ctx.send("I'm not high enough on the heirarchy enough assign this role.")
            return False
        return True
