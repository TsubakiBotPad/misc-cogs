"""
Utilities for managing misbehaving users and facilitating administrator
communication about role changes.
"""

import discord
import logging
from collections import defaultdict
from collections import deque
from redbot.core import checks
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.utils.chat_formatting import box, inline, pagify
from tsutils import CogSettings
from io import BytesIO

logger = logging.getLogger('red.misc-cogs.baduser')

LOGS_PER_USER = 10


def opted_in(ctx):
    return ctx.guild.id in ctx.bot.get_cog("BadUser").settings.bu_enabled()


class BadUser(commands.Cog):
    """Allows for more specific punishments than regular discord including global strikes and positive/negative roles"""
    def __init__(self, bot: Red, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot

        self.settings = BadUserSettings("baduser")
        self.logs = defaultdict(lambda: deque(maxlen=LOGS_PER_USER))

    async def red_get_data_for_user(self, *, user_id):
        """Get a user's personal data."""
        udata = self.settings.get_user_data(user_id)

        data = "Stored data for user with ID {}:\n".format(user_id)
        if udata['gban']:
            data += (" - You are on the global banlist. "
                     "(This data is sensitive and cannot be cleared automatically due to abuse. "
                     "Please contact a bot owner to get this data cleared.)\n")
        if udata['baduser']:
            data += (" - You have been punished/banned in {} servers: "
                     "(This data is sensitive and cannot be cleared automatically due to abuse. "
                     "Please contact a bot owner to get this data cleared.)\n"
                     "").format(len(udata['baduser']))

        if not any(udata.values()):
            data = "No data is stored for user with ID {}.\n".format(user_id)

        return {"user_data.txt": BytesIO(data.encode())}

    async def red_delete_data_for_user(self, *, requester, user_id):
        """Delete a user's personal data.

        The personal data stored in this cog is for essential moderation use,
        so some data deletion requests can only be made by the bot owner and
        Discord itself.  If this is an issue, please contact a bot owner.
        """
        if requester not in ("discord_deleted_user", "owner"):
            self.settings.clear_user_data(user_id)
        else:
            self.settings.clear_user_data_full(user_id)

    @commands.group()
    @commands.guild_only()
    @checks.mod_or_permissions(manage_guild=True)
    async def baduser(self, ctx):
        """BadUser tools.

        The scope of this module has expanded a bit. It now covers both 'positive' and 'negative'
        roles. The goal is to assist coordination across moderators.

        When a user receives a negative role, a strike is automatically recorded for them. This
        captures their recent message history.

        You can specify a moderation channel for announcements. An announcement occurs on the
        following events:
        * User gains or loses a negative/positive role (includes a ping to @here)
        * User with a strike leaves the server
        * User with a strike joins the server (includes a ping to @here)

        Besides the automatic tracking, you can manually add strikes, display them, and clear them.
        """

    @baduser.command()
    @commands.guild_only()
    @commands.check(opted_in)
    @checks.mod_or_permissions(manage_guild=True)
    async def addnegativerole(self, ctx, *, role: discord.Role):
        """Designate a role as a 'punishment' role."""
        self.settings.add_punishment_role(ctx.guild.id, role.id)
        await ctx.send(inline('Added punishment role "' + role.name + '"'))

    @baduser.command()
    @commands.guild_only()
    @commands.check(opted_in)
    @checks.mod_or_permissions(manage_guild=True)
    async def rmnegativerole(self, ctx, *, role: discord.Role):
        """Cancels a role from 'punishment' status."""
        self.settings.rm_punishment_role(ctx.guild.id, role.id)
        await ctx.send(inline('Removed punishment role "' + role.name + '"'))

    @baduser.command()
    @commands.guild_only()
    @commands.check(opted_in)
    @checks.mod_or_permissions(manage_guild=True)
    async def addpositiverole(self, ctx, *, role: discord.Role):
        """Designate a role as a 'benefit' role."""
        self.settings.add_positive_role(ctx.guild.id, role.id)
        await ctx.send(inline('Added positive role "' + role.name + '"'))

    @baduser.command()
    @commands.guild_only()
    @commands.check(opted_in)
    @checks.mod_or_permissions(manage_guild=True)
    async def rmpositiverole(self, ctx, *, role: discord.Role):
        """Cancels a role from 'benefit' status."""
        self.settings.rm_positive_role(ctx.guild.id, role.id)
        await ctx.send(inline('Removed positive role "' + role.name + '"'))

    @baduser.command()
    @commands.guild_only()
    @commands.check(opted_in)
    @checks.mod_or_permissions(manage_guild=True)
    async def addneutralrole(self, ctx, *, role: discord.Role):
        """Designate a role as a notable but not ping-worthy role."""
        self.settings.add_neutral_role(ctx.guild.id, role.id)
        await ctx.send(inline('Added neutral role "' + role.name + '"'))

    @baduser.command()
    @commands.guild_only()
    @commands.check(opted_in)
    @checks.mod_or_permissions(manage_guild=True)
    async def rmneutralrole(self, ctx, *, role: discord.Role):
        """Cancels a role from notable but not ping-worthy status."""
        self.settings.rm_neutral_role(ctx.guild.id, role.id)
        await ctx.send(inline('Removed neutral role "' + role.name + '"'))

    @baduser.command()
    @commands.guild_only()
    @commands.check(opted_in)
    @checks.mod_or_permissions(manage_guild=True)
    async def setchannel(self, ctx, channel: discord.TextChannel):
        """Set the channel for moderation announcements."""
        self.settings.update_channel(ctx.guild.id, channel.id)
        await ctx.send(inline('Set the announcement channel'))

    @baduser.command()
    @commands.guild_only()
    @commands.check(opted_in)
    @checks.mod_or_permissions(manage_guild=True)
    async def clearchannel(self, ctx):
        """Clear the channel for moderation announcements."""
        self.settings.update_channel(ctx.guild.id, None)
        await ctx.send(inline('Cleared the announcement channel'))

    @baduser.command()
    @commands.guild_only()
    @commands.check(opted_in)
    @checks.mod_or_permissions(manage_guild=True)
    async def togglestrikeprivacy(self, ctx):
        """Change strike existance policy."""
        server = ctx.guild
        self.settings.set_strikes_private(server.id, not self.settings.get_strikes_private(server.id))
        output = '\nStrike existance is now ' + \
                 'private' if self.settings.get_strikes_private(server.id) else 'public'
        await ctx.send(inline(output))

    @baduser.command()
    @commands.guild_only()
    @commands.check(opted_in)
    @checks.mod_or_permissions(manage_guild=True)
    async def config(self, ctx):
        """Display the baduser configuration."""
        server = ctx.guild
        output = 'Punishment roles:\n'
        for role_id in self.settings.get_punishment_roles(server.id):
            role = server.get_role(role_id)
            if role is not None:
                output += '\t' + role.name + '\n'

        output += '\nPositive roles:\n'
        for role_id in self.settings.get_positive_roles(server.id):
            role = server.get_role(role_id)
            if role is not None:
                output += '\t' + role.name + '\n'

        output += '\nNeutral roles:\n'
        for role_id in self.settings.get_neutral_roles(server.id):
            role = server.get_role(role_id)
            if role is not None:
                output += '\t' + role.name + '\n'

        output += '\nStrike contents are private'
        output += '\nStrike existence is ' + \
                  ('private' if self.settings.get_strikes_private(server.id) else 'public')

        await ctx.send(box(output))

    @baduser.command()
    @commands.guild_only()
    @commands.check(opted_in)
    @checks.mod_or_permissions(manage_guild=True)
    async def strikes(self, ctx, user: discord.User):
        """Display the strike count for a user."""
        strikes = self.settings.count_user_strikes(ctx.guild.id, user.id)
        await ctx.send(box('User {} has {} strikes'.format(user.name, strikes)))

    @baduser.command()
    @commands.guild_only()
    @commands.check(opted_in)
    @checks.mod_or_permissions(manage_guild=True)
    async def addstrike(self, ctx, user: discord.User, *, strike_text: str):
        """Manually add a strike to a user."""
        timestamp = str(ctx.message.created_at)[:-7]
        msg = 'Manually added by {} ({}): {}'.format(
            ctx.author.name, timestamp, strike_text)
        server_id = ctx.guild.id
        self.settings.update_bad_user(server_id, user.id, msg)
        strikes = self.settings.count_user_strikes(server_id, user.id)
        await ctx.send(box('Done. User {} now has {} strikes'.format(user.name, strikes)))

    @baduser.command()
    @commands.guild_only()
    @commands.check(opted_in)
    @checks.mod_or_permissions(manage_guild=True)
    async def clearstrikes(self, ctx, user: discord.User):
        """Clear all strikes for a user."""
        self.settings.clear_user_strikes(ctx.guild.id, user.id)
        await ctx.send(box('Cleared strikes for {}'.format(user.name)))

    @baduser.command()
    @commands.guild_only()
    @commands.check(opted_in)
    @checks.mod_or_permissions(manage_guild=True)
    async def printstrikes(self, ctx, user: discord.User):
        """Display all strikes for a user."""
        strikes = self.settings.get_user_strikes(ctx.guild.id, user.id)
        if not strikes:
            await ctx.send(box('No strikes for {}'.format(user.name)))
            return

        for idx, strike in enumerate(strikes):
            await ctx.send(inline('Strike {} of {}:'.format(idx + 1, len(strikes))))
            await ctx.send(box(strike))

    @baduser.command()
    @commands.guild_only()
    @commands.check(opted_in)
    @checks.mod_or_permissions(manage_guild=True)
    async def deletestrike(self, ctx, user: discord.User, strike_num: int):
        """Delete a specific strike for a user."""
        strikes = self.settings.get_user_strikes(ctx.guild.id, user.id)
        if not strikes or len(strikes) < strike_num:
            await ctx.send(box('Strike not found for {}'.format(user.name)))
            return

        strike = strikes[strike_num - 1]
        strikes.remove(strike)
        self.settings.set_user_strikes(ctx.guild.id, user.id, strikes)
        await ctx.send(inline('Removed strike {}. User has {} remaining.'.format(strike_num, len(strikes))))
        await ctx.send(box(strike))

    @baduser.command()
    @commands.guild_only()
    @commands.check(opted_in)
    @checks.mod_or_permissions(manage_guild=True)
    async def report(self, ctx):
        """Displays a report of information on bad users for the server."""
        cur_server = ctx.guild
        user_id_to_ban_server = defaultdict(list)
        user_id_to_baduser_server = defaultdict(list)
        error_messages = list()
        for server in self.bot.guilds:
            if server.id == cur_server.id:
                continue

            if self.settings.get_strikes_private(server.id):
                error_messages.append("Server '{}' set its strikes private".format(server.name))
                continue

            try:
                ban_list = await server.bans()
            except discord.Forbidden:
                ban_list = list()
                error_messages.append("Server '{}' refused access to ban list".format(server.name))

            for banentry in ban_list:
                user_id_to_ban_server[banentry.user.id].append(server.id)

            baduser_list = self.settings.get_bad_users(server.id)
            for user_id in baduser_list:
                user_id_to_baduser_server[user_id].append(server.id)

        bad_users = self.settings.get_bad_users(cur_server.id)

        baduser_entries = list()
        otheruser_entries = list()

        for member in cur_server.members:
            local_strikes = self.settings.get_user_strikes(cur_server.id, member.id)
            other_baduser_servers = user_id_to_baduser_server[member.id]
            other_banned_servers = user_id_to_ban_server[member.id]

            if not len(local_strikes) and not len(other_baduser_servers) and not len(other_banned_servers):
                continue

            tmp_msg = "{} ({})".format(member.name, member.id)
            if other_baduser_servers:
                tmp_msg += "\n\tbad user in {} other servers".format(len(other_baduser_servers))
            if other_banned_servers:
                tmp_msg += "\n\tbanned from {} other servers".format(len(other_banned_servers))

            if len(local_strikes):
                tmp_msg += "\n\t{} strikes in this server".format(len(local_strikes))
                for strike in local_strikes:
                    tmp_msg += "\n\t\t{}".format(strike.splitlines()[0])
                baduser_entries.append(tmp_msg)
            else:
                otheruser_entries.append(tmp_msg)

        other_server_count = len(self.bot.guilds) - 1
        other_ban_count = len([x for x, l in user_id_to_ban_server.items() if len(l)])
        other_baduser_count = len([x for x, l in user_id_to_baduser_server.items() if len(l)])
        msg = "Across {} other servers, {} users are banned and {} have baduser entries".format(
            other_server_count, other_ban_count, other_baduser_count)

        msg += "\n\n{} baduser entries for this server".format(len(baduser_entries))
        msg += "\n" + "\n".join(baduser_entries)
        msg += "\n\n{} entries for users with no record in this server".format(
            len(otheruser_entries))
        msg += "\n" + "\n".join(otheruser_entries)

        if error_messages:
            msg += "\n\nSome errors occurred:"
            msg += "\n" + "\n".join(error_messages)

        for page in pagify(msg):
            await ctx.send(box(page))

    @baduser.command()
    @checks.is_owner()
    async def addban(self, ctx, user_id: int, *, reason: str):
        """Add a banned user"""
        self.settings.add_banned_user(user_id, reason)
        await ctx.tick()

    @baduser.command()
    @checks.is_owner()
    async def rmban(self, ctx, user_id: int):
        """Remove a banned user"""
        user_id = str(user_id)
        self.settings.rm_banned_user(user_id)
        await ctx.tick()

    @baduser.command()
    @checks.is_owner()
    async def opt_in(self, ctx):
        """Opt this server into baduser"""
        self.settings.add_bu_enabled(ctx.guild.id)
        await ctx.tick()

    @baduser.command()
    @checks.mod_or_permissions(manage_guild=True)
    async def opt_out(self, ctx):
        """Opt this server out of baduser"""
        self.settings.rm_bu_enabled(ctx.guild.id)
        await ctx.tick()

    @commands.Cog.listener('on_message')
    async def log_message(self, message):
        if message.author.id == self.bot.user.id or isinstance(message.channel, discord.abc.PrivateChannel):
            return

        if message.guild.id not in self.settings.bu_enabled():
            return

        author = message.author
        content = message.clean_content
        channel = message.channel
        timestamp = str(message.created_at)[:-7]
        log_msg = '[{}] {} ({}): {}/{}'.format(timestamp, author.name,
                                               author.id, channel.name, content)
        self.logs[author.id].append(log_msg)

    @commands.Cog.listener('on_member_ban')
    async def mod_ban(self, guild, user):
        if guild.id not in self.settings.bu_enabled():
            return
        await self.record_bad_user(user, 'BANNED', guild=guild)

    @commands.Cog.listener('on_member_remove')
    async def mod_user_left(self, member):
        if member.guild.id not in self.settings.bu_enabled():
            return
        strikes = self.settings.count_user_strikes(member.guild.id, member.id)
        if strikes:
            msg = 'FYI: A user with {} strikes just left the server: {} ({})'.format(
                strikes, member.name, member.id)
            update_channel = self.settings.get_channel(member.guild.id)
            if update_channel is not None:
                channel_obj = member.guild.get_channel(update_channel)
                await channel_obj.send(msg)

    @commands.Cog.listener('on_member_join')
    async def mod_user_join(self, member):
        if member.guild.id not in self.settings.bu_enabled():
            return
        update_channel = self.settings.get_channel(member.guild.id)
        if update_channel is None:
            return

        channel_obj = member.guild.get_channel(update_channel)
        strikes = self.settings.count_user_strikes(member.guild.id, member.id)
        if strikes:
            msg = 'Hey @here a user with {} strikes just joined the server: {} ({})'.format(
                strikes, member.mention, member.id)
            await channel_obj.send(msg, allowed_mentions=discord.AllowedMentions(everyone=True))

        local_ban = self.settings.banned_users().get(member.id, None)
        if local_ban:
            msg = 'Hey @here locally banned user {} (for: {}) just joined the server'.format(
                member.mention, local_ban)
            await channel_obj.send(msg, allowed_mentions=discord.AllowedMentions(everyone=True))

    @commands.Cog.listener('on_member_update')
    async def check_punishment(self, before, after):
        if before.guild.id not in self.settings.bu_enabled():
            return

        if before.roles == after.roles:
            return

        new_roles = set(after.roles).difference(before.roles)
        removed_roles = set(before.roles).difference(after.roles)

        bad_role_ids = self.settings.get_punishment_roles(after.guild.id)
        positive_role_ids = self.settings.get_positive_roles(after.guild.id)
        neutral_role_ids = self.settings.get_neutral_roles(after.guild.id)

        for role in new_roles:
            if role.id in bad_role_ids:
                await self.record_bad_user(after, role.name)
                return

            if role.id in positive_role_ids:
                await self.record_role_change(after, role.name, True)
                return

            if role.id in neutral_role_ids:
                await self.record_role_change(after, role.name, True, send_ping=False)
                return

        for role in removed_roles:
            if role.id in positive_role_ids:
                await self.record_role_change(after, role.name, False)
                return
            if role.id in neutral_role_ids:
                await self.record_role_change(after, role.name, False, send_ping=False)
                return

    async def record_bad_user(self, member, role_name, guild=None):
        if guild is None:
            guild = member.guild

        latest_messages = self.logs.get(member.id, "")
        msg = 'Name={} Nick={} ID={} Joined={} Role={}\n'.format(
                                    member.name,
                                    member.display_name,
                                    member.id,
                                    member.joined_at if isinstance(member, discord.Member) else 'N/A',
                                    role_name)
        msg += '\n'.join(latest_messages)
        self.settings.update_bad_user(guild.id, member.id, msg)
        strikes = self.settings.count_user_strikes(guild.id, member.id)

        update_channel = self.settings.get_channel(guild.id)
        if update_channel is not None:
            channel_obj = guild.get_channel(update_channel)
            await channel_obj.send(inline('Detected bad user'))
            await channel_obj.send(box(msg))
            followup_msg = 'Hey @here please leave a note explaining why this user is punished'
            await channel_obj.send(followup_msg, allowed_mentions=discord.AllowedMentions(everyone=True))
            await channel_obj.send('This user now has {} strikes'.format(strikes))

            try:
                dm_msg = ('You were assigned the punishment role "{}" in the server "{}".\n'
                          'The Mods will contact you shortly regarding this.\n'
                          'Attempting to clear this role yourself will result in punishment.').format(role_name, guild.name)
                await member.send(box(dm_msg))
                await channel_obj.send('User successfully notified')
            except Exception as e:
                await channel_obj.send('Failed to notify the user! I might be blocked\n' + box(str(e)))

    async def record_role_change(self, member, role_name, is_added, send_ping=True, guild=None):
        if guild is None:
            guild = member.guild
        msg = 'Detected role {} : Name={} Nick={} ID={} Joined={} Role={}'.format(
                                        "Added" if is_added else "Removed",
                                        member.name,
                                        member.display_name,
                                        member.id,
                                        member.joined_at if isinstance(member, discord.Member) else 'N/A',
                                        role_name)

        update_channel = self.settings.get_channel(guild.id)
        if update_channel is not None:
            channel_obj = guild.get_channel(update_channel)
            try:
                await channel_obj.send(inline(msg))
                if send_ping:
                    followup_msg = 'Hey @here please leave a note explaining why this role was modified'
                    await channel_obj.send(followup_msg, allowed_mentions=discord.AllowedMentions(everyone=True))
            except:
                logger.warning('Failed to notify in {} {}'.format(update_channel, msg))


class BadUserSettings(CogSettings):
    def make_default_settings(self):
        config = {
            'servers': {},
            'banned_users': {},
            'opted_in': [],
        }
        return config

    def guild_configs(self):
        return self.bot_settings['servers']

    def get_guild(self, server_id):
        configs = self.guild_configs()
        if server_id not in configs:
            configs[server_id] = {}
        return configs[server_id]

    def get_bad_users(self, server_id):
        server = self.get_guild(server_id)
        if 'badusers' not in server:
            server['badusers'] = {}
        return server['badusers']

    def get_punishment_roles(self, server_id):
        server = self.get_guild(server_id)
        if 'role_ids' not in server:
            server['role_ids'] = []
        return server['role_ids']

    def add_punishment_role(self, server_id, role_id):
        role_ids = self.get_punishment_roles(server_id)
        if role_id not in role_ids:
            role_ids.append(role_id)
        self.save_settings()

    def rm_punishment_role(self, server_id, role_id):
        role_ids = self.get_punishment_roles(server_id)
        if role_id in role_ids:
            role_ids.remove(role_id)
        self.save_settings()

    def get_positive_roles(self, server_id):
        server = self.get_guild(server_id)
        if 'positive_role_ids' not in server:
            server['positive_role_ids'] = []
        return server['positive_role_ids']

    def add_positive_role(self, server_id, role_id):
        role_ids = self.get_positive_roles(server_id)
        if role_id not in role_ids:
            role_ids.append(role_id)
        self.save_settings()

    def rm_positive_role(self, server_id, role_id):
        role_ids = self.get_positive_roles(server_id)
        if role_id in role_ids:
            role_ids.remove(role_id)
        self.save_settings()

    def add_neutral_role(self, server_id, role_id):
        role_ids = self.get_neutral_roles(server_id)
        if role_id not in role_ids:
            role_ids.append(role_id)
        self.save_settings()

    def get_neutral_roles(self, server_id):
        server = self.get_guild(server_id)
        if 'neutral_role_ids' not in server:
            server['neutral_role_ids'] = []
        return server['neutral_role_ids']

    def rm_neutral_role(self, server_id, role_id):
        role_ids = self.get_neutral_roles(server_id)
        if role_id in role_ids:
            role_ids.remove(role_id)
        self.save_settings()

    def update_bad_user(self, server_id, user_id, msg):
        badusers = self.get_bad_users(server_id)
        if user_id not in badusers:
            badusers[user_id] = []

        badusers[user_id].append(msg)
        self.save_settings()

    def count_user_strikes(self, server_id, user_id):
        badusers = self.get_bad_users(server_id)
        if user_id not in badusers:
            return 0
        else:
            return len(badusers[user_id])

    def set_user_strikes(self, server_id, user_id, strikes):
        badusers = self.get_bad_users(server_id)
        badusers[user_id] = strikes
        self.save_settings()

    def clear_user_strikes(self, server_id, user_id):
        badusers = self.get_bad_users(server_id)
        badusers.pop(user_id, None)
        self.save_settings()

    def get_user_strikes(self, server_id, user_id):
        badusers = self.get_bad_users(server_id)
        return badusers.get(user_id, [])

    def update_channel(self, server_id, channel_id):
        server = self.get_guild(server_id)
        if channel_id is None:
            if 'update_channel' in server:
                server.pop('update_channel')
                self.save_settings()
            return

        server['update_channel'] = channel_id
        self.save_settings()

    def get_channel(self, server_id):
        server = self.get_guild(server_id)
        return server.get('update_channel')

    def get_strikes_private(self, server_id):
        server = self.get_guild(server_id)
        return server.get('strikes_private', False)

    def set_strikes_private(self, server_id, strikes_private):
        server = self.get_guild(server_id)
        server['strikes_private'] = strikes_private
        self.save_settings()

    def banned_users(self):
        return self.bot_settings['banned_users']

    def add_banned_user(self, user_id: int, reason: str):
        self.banned_users()[user_id] = reason
        self.save_settings()

    def rm_banned_user(self, user_id: int):
        self.banned_users().pop(user_id, None)
        self.save_settings()

    def bu_enabled(self):
        return [int(gid) for gid in self.bot_settings['opted_in']]

    def add_bu_enabled(self, gid: int):
        self.bot_settings['opted_in'].append(gid)
        self.save_settings()

    def rm_bu_enabled(self, gid: int):
        if str(gid) in self.bot_settings['opted_in']:
            self.bot_settings['opted_in'].remove(str(gid))
        self.save_settings()

    def get_user_data(self, uid):
        o = {
            "gban": "",
            "baduser": 0,
        }
        if str(uid) in self.bot_settings['banned_users']:
            o['gban'] = self.bot_settings['banned_users'][str(uid)]
        for gid in self.bot_settings['servers']:
            if str(uid) in self.bot_settings['servers'][gid]["badusers"]:
                o['baduser'] += 1
        return o

    def clear_user_data(self, uid):
        # Do nothing
        return

    def clear_user_data_full(self, uid):
        if str(uid) in self.bot_settings['banned_users']:
            del self.bot_settings['banned_users'][str(uid)]
        for gid in self.bot_settings['servers']:
            if str(uid) in self.bot_settings['servers'][gid]["badusers"]:
                del self.bot_settings['servers'][gid]["badusers"][str(uid)]
        self.save_settings()
