import discord
import logging
from io import BytesIO
from redbot.core import checks, commands, Config, modlog
from redbot.core.utils.chat_formatting import box, inline, pagify

logger = logging.getLogger('red.misc-cogs.grantrole')

class GrantRole(commands.Cog):
    """Grant roles on user join or reaction add"""
    def __init__(self, bot, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot
        self.config = Config.get_conf(self, identifier=624772073)
        self.config.register_guild(on_join=[], on_react={})

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
        """Add an onjoin role"""
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
        """Remove an onjoin role"""
        async with self.config.guild(ctx.guild).on_join() as on_join:
            if role.id not in on_join:
                await ctx.send("This role isn't assigned on join.")
                return
            on_join.remove(role.id)
        await ctx.tick()

    @onjoin.command(name="list")
    async def onjoin_list(self, ctx):
        """List onjoin roles"""
        o = []
        for role_id in await self.config.guild(ctx.guild).on_join():
            o.append("#{}".format(ctx.guild.get_role(role_id) or "deleted_role"))
        await ctx.send(box("\n".join(o)))

    @grantrole.group()
    async def onreact(self, ctx):
        """Manipulate roles granted on emoji react"""

    @onreact.command(name="add")
    async def onreact_add(self, ctx, message: discord.Message, emoji, role: discord.Role):
        """Add a role on a reaction"""
        try:
            emoji = await commands.EmojiConverter().convert(ctx, emoji)
        except commands.BadArgument:
            if emoji not in emoji_module.UNICODE_EMOJI:
                await ctx.send("I do not have access to emoji `{}`".format(emoji))
                return

        if not await self.can_assign(ctx, role):
            return
        await message.add_reaction(emoji)
        async with self.config.guild(ctx.guild).on_react() as on_react:
            on_react[str(message.id)] = on_react.get(str(message.id), {})
            on_react[str(message.id)][str(emoji.id)] = role.id
        await ctx.tick()

    @onreact.command(name="remove")
    async def onreact_remove(self, ctx, message: discord.Message, emoji):
        """Remove a role from a reaction"""
        try:
            emoji = await commands.EmojiConverter().convert(ctx, emoji)
        except commands.BadArgument:
            if emoji not in emoji_module.UNICODE_EMOJI:
                await ctx.send("I do not have access to emoji `{}`".format(emoji))
                return

        async with self.config.guild(ctx.guild).on_react() as on_react:
            if not on_react.get(str(message.id)) or not on_react.get(str(message.id), {}).get(str(emoji.id)):
                await ctx.send("That emoji isn't mapped to a role.")
                return
            del on_react[str(message.id)][str(emoji.id)]
        await ctx.tick()

    @onreact.command(name="list")
    async def onreact_list(self, ctx, message: discord.Message):
        """List all emoji for a message"""
        roles = await self.config.guild(message.guild).on_react()
        if str(message.id) not in roles:
            await ctx.send("That message isn't configured with onreact")
            return
        emojis = roles[str(message.id)]
        msg = []
        for eid,rid in emojis.items():
            e = self.bot.get_emoji(int(eid))
            r = ctx.guild.get_role(rid)
            if None not in (e, r):
                msg.append("{}: {}".format(str(e), r.mention))
        await ctx.send("\n".join(msg))

    @onreact.command(name="serverlist")
    async def onreact_serverlist(self, ctx):
        """List all grantrole setups on this server"""
        async with ctx.typing():
            roles = await self.config.guild(ctx.guild).on_react()
            msg = []
            for mid in roles:
                for channel in ctx.guild.text_channels:
                    try:
                        message = await channel.fetch_message(int(mid))
                    except discord.errors.NotFound:
                        continue
                    emojis = roles[mid]
                    smsg = []
                    for eid,rid in emojis.items():
                        e = self.bot.get_emoji(int(eid))
                        r = ctx.guild.get_role(rid)
                        if None not in (e, r):
                            smsg.append("\n\t{}: {}".format(str(e), r.mention))
                    if smsg:
                        msg.append(message.jump_url + "".join(smsg))
                    break
        for page in pagify("\n\n".join(msg)):
            await ctx.send(page)
        if not msg:
            await ctx.send("onreact is not enabled on this server.")

    @onreact.command(name="catchup")
    async def onreact_catchup(self, ctx, message: discord.Message):
        """Catchup on a message (in case bot goes down)"""
        roles = await self.config.guild(message.guild).on_react()
        if str(message.id) not in roles:
            await ctx.send("That message isn't configured with onreact")
            return
        emojis = roles[str(message.id)]
        for r in message.reactions:
            if str(r.emoji.id) in emojis:
                role = ctx.guild.get_role(emojis[str(r.emoji.id)])
                async for member in r.users():
                    await member.add_roles(role, reason="On React Role Catchup")
        await ctx.tick()

    @commands.Cog.listener('on_member_join')
    async def on_member_join(self, member):
        if not hasattr(member, 'guild') or await self.bot.cog_disabled_in_guild(self, member.guild):
            return
        roles = await self.config.guild(member.guild).on_join()
        try:
            for role in roles:
                r = member.guild.get_role(int(role))
                if r is not None:
                    await member.add_roles(r, reason="On Join Role Grant")
        except discord.Forbidden:
            logger.exception("Unable to add roles in guild: {}".format(guild.id))

    @commands.Cog.listener('on_raw_reaction_add')
    async def on_reaction_add(self, payload):
        if not payload.guild_id \
                  or payload.member.bot \
                  or await self.bot.cog_disabled_in_guild(self, payload.member.guild):
            return
        roles = await self.config.guild(payload.member.guild).on_react()
        try:
            emoji = payload.emoji if isinstance(payload.emoji, str) else str(payload.emoji.id)
            role = roles.get(str(payload.message_id), {}).get(emoji)
            if role is None:
                return
            await payload.member.add_roles(payload.member.guild.get_role(role), reason="On React Role Grant")
        except discord.Forbidden:
            logger.exception("Unable to add roles in guild: {}".format(payload.guild_id))

    @commands.Cog.listener('on_raw_reaction_remove')
    async def on_reaction_remove(self, payload):
        member = self.bot.get_guild(payload.guild_id).get_member(payload.user_id)
        if not payload.guild_id \
                  or member.bot \
                  or await self.bot.cog_disabled_in_guild(self, member.guild):
            return
        roles = await self.config.guild(member.guild).on_react()
        try:
            emoji = payload.emoji.name if isinstance(payload.emoji, discord.PartialEmoji) else str(payload.emoji.id)
            role = roles.get(str(payload.message_id), {}).get(emoji)
            if role is None:
                return
            await member.remove_roles(member.guild.get_role(role), reason="On React Role Grant")
        except discord.Forbidden:
            logger.exception("Unable to remove roles in guild: {}".format(payload.guild_id))

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
