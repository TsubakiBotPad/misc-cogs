import asyncio
from typing import Optional

import discord
import logging
import prettytable
import tsutils
from collections import defaultdict
from collections import deque
from datetime import datetime
from io import BytesIO
from redbot.core import checks, commands, Config
from redbot.core.utils.chat_formatting import box, inline, pagify
from tsutils import CogSettings

try:
    import re2 as re
except ImportError:
    try:
        import regex as re
    except ImportError:
        import re

logger = logging.getLogger('red.misc-cogs.automod')

LOGS_PER_CHANNEL_USER = 5

AUTOMOD_HELP = r"""
Automod works by creating named global patterns, and then applying them in
specific channels as either whitelist or blacklist rules. This allows you
to customize what text can be typed in a channel. Text from moderators is
always ignored by this cog.

Check out {0.prefix}automod patterns to see the current server-specific list of patterns.

Each pattern has an 'include' component and an 'exclude' component. If text
matches the include, then the rule matches. If it subsequently matches the
exclude, then it does not match.

Here's an example pattern:
Rule Name                              Include regex        Exclude regex
-----------------------------------------------------------------------------
messages must start with a room code   ^\d{4}\s?\d{4}.*     .*test.*

This pattern will match values like:
  12345678 foo fiz
  1234 5678 bar baz

However, if the pattern contains 'test', it won't match:
  12345678 foo fiz test bar baz

To add the pattern, you'd use the following command:
[p]automod addpattern "messages must start with a room code" "^\d{4}\s?\d{4}.*" ".*test.*"

Remember that to bundle multiple words together you need to surround the
argument with quotes, as above.

Once you've added a pattern, you need to enable it in a channel using one
of {0.prefix}addwhitelist or {0.prefix}addblacklist, e.g.:
  {0.prefix}automod addwhitelist "messages must start with a room code"

If a channel has any whitelists, then text typed in the channel must match
AT LEAST one whitelist, or it will be deleted. If ANY blacklist is matched
the text will be deleted.

You can see the configuration for the server using {0.prefix}automod list

You can also prevent users from spamming images using {0.prefix}automod imagelimit
"""

EMOJIS = {
    'tips': [
        '\N{THUMBS UP SIGN}',
        '\N{THUMBS DOWN SIGN}',
        '\N{EYES}',
    ],
    'eyes': [
        '\N{EYES}',
    ]
}


def linked_img_count(message):
    return len(message.embeds) + len(message.attachments)


class AutoMod(commands.Cog):
    """Uses regex pattern matching to filter message content and set limits on users"""

    def __init__(self, bot, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot

        self.config = Config.get_conf(self, identifier=4770700)
        self.config.register_guild(patterns={}, watchdog_phrases={}, watched_users={}, watchdog_channel_id=None)
        self.config.register_channel(whitelist=[], blacklist=[], image_limit=0, autoemoji=[])
        self.config.register_role(image_immune=False)

        self.settings = AutoMod2Settings("automod2", bot)
        self.channel_user_logs = defaultdict(lambda: deque(maxlen=LOGS_PER_CHANNEL_USER))

        self.server_user_last = defaultdict(dict)
        self.server_phrase_last = defaultdict(dict)

    async def red_get_data_for_user(self, *, user_id):
        """Get a user's personal data."""
        watchlisted = 0
        watchdogs = 0
        phrases_set = 0

        for gid in await self.config.all_guilds():
            watched_users = await self.config.guild_from_id(gid).watched_users()
            if str(user_id) in watched_users:
                watchlisted += 1
            for user in watched_users:
                if watched_users[user]['request_user_id'] == user_id:
                    watchdogs += 1
            phrases = await self.config.guild_from_id(gid).phrases()
            for phrase in phrases:
                if phrases[phrase]['request_user_id'] == user_id:
                    phrases_set += 1

        data = f"Stored data for user with ID {user_id}:\n"
        if watchdogs:
            data += f" - You have setup watchdogs for {watchdogs} user(s).\n"
        if phrases_set:
            data += f" - You have created {phrases_set} phrase(s).\n"
        if watchlisted:
            data += (f" - You have been watchlisted in {watchlisted} servers. "
                     f"(This data is sensitive and cannot be cleared automatically due to abuse. "
                     f"Please contact a bot owner to get this data cleared.)\n")

        if not (watchdogs or phrases_set or watchlisted):
            data = f"No data is stored for user with ID {user_id}.\n"

        return {"user_data.txt": BytesIO(data.encode())}

    async def red_delete_data_for_user(self, *, requester, user_id):
        """Delete a user's personal data.

        The personal data stored in this cog is for essential moderation use,
        so some data deletion requests can only be made by the bot owner and
        Discord itself.  If this is an issue, please contact a bot owner.
        """
        for gid in await self.config.all_guilds():
            async with self.config.guild_from_id(gid).watchdog_phrases() as phrases:
                for phrase in phrases:
                    if phrases[phrase]['request_user_id'] == user_id:
                        phrases[phrase]['request_user_id'] = -1
            async with self.config.guild_from_id(gid).watched_users() as watched_users:
                for user in watched_users:
                    if watched_users[user]['request_user_id'] == user_id:
                        watched_users[user]['request_user_id'] = -1

        if requester in ("discord_deleted_user", "owner"):
            for gid in await self.config.all_guilds():
                async with self.config.guild_from_id(gid).watched_users() as watched_users:
                    if str(user_id) in watched_users:
                        del watched_users[str(user_id)]

    @commands.command()
    @checks.mod_or_permissions(manage_guild=True)
    async def automodhelp(self, ctx):
        """Sends you info on how to use automod."""
        for page in pagify(AUTOMOD_HELP.format(ctx.prefix)):
            await ctx.author.send(box(page))

    @commands.group(aliases=['automod2'])
    @commands.guild_only()
    @checks.mod_or_permissions(manage_guild=True)
    async def automod(self, ctx):
        """AutoMod tools.

        This cog works by creating named global patterns, and then applying them in
        specific channels as either whitelist or blacklist rules.

        For more information, use [p]automodhelp
        """

    @automod.command()
    @commands.guild_only()
    @checks.mod_or_permissions(manage_guild=True)
    async def addpattern(self, ctx, name, include_pattern, exclude_pattern='', error=None):
        """Add a pattern for use in this server."""
        if error is not None:
            await ctx.send('Too many inputs detected, check your quotes')
            return
        try:
            re.compile(include_pattern)
            re.compile(exclude_pattern)
        except Exception as ex:
            await ctx.send(inline(str(ex)))
            return
        async with self.config.guild(ctx.guild).patterns() as patterns:
            patterns[name] = {'include_pattern': include_pattern, 'exclude_pattern': exclude_pattern, 'uses': 0}
        await ctx.tick()

    @automod.command()
    @commands.guild_only()
    @checks.mod_or_permissions(manage_guild=True)
    async def rmpattern(self, ctx, *, name):
        """Remove a pattern from this server. Pattern must not be in use."""
        async with self.config.guild(ctx.guild).patterns() as patterns:
            if name not in patterns:
                await ctx.send(f"Rule '{name}' is undefined.")
                return
            if patterns[name]['uses']:
                await ctx.send(f"Rule '{name}' is in use.")
                return
            del patterns[name]
        await ctx.tick()

    @automod.command()
    @commands.guild_only()
    @checks.mod_or_permissions(manage_guild=True)
    async def addwhitelist(self, ctx, channel: Optional[discord.TextChannel] = None, *, name):
        """Add the named pattern as a whitelist for the given channel (this channel if not specified)."""
        name = name.strip('"')
        channel = channel or ctx.channel
        async with self.config.guild(channel.guild).patterns() as patterns:
            if name in patterns:
                await ctx.send(f"Rule '{name}' is undefined.")
                return
            async with self.config.channel(channel).whitelist() as whitelist:
                if name not in whitelist:
                    whitelist.append(name)
                    patterns[name]['uses'] += 1
        await ctx.tick()

    @automod.command()
    @commands.guild_only()
    @checks.mod_or_permissions(manage_guild=True)
    async def rmwhitelist(self, ctx, channel: Optional[discord.TextChannel] = None, *, name):
        """Remove the named pattern as a whitelist for the given channel (this channel if not specified)."""
        name = name.strip('"')
        channel = channel or ctx.channel

        async with self.config.guild(channel.guild).patterns() as patterns:
            async with self.config.channel(channel).whitelist() as whitelist:
                if name not in whitelist:
                    await ctx.send(f"Rule '{name}' is undefined.")
                    return
                whitelist.remove(name)
                patterns[name]['uses'] -= 1
        await ctx.tick()

    @automod.command()
    @commands.guild_only()
    @checks.mod_or_permissions(manage_guild=True)
    async def addblacklist(self, ctx, channel: Optional[discord.TextChannel] = None, *, name):
        """Add the named pattern as a blacklist for the given channel (this channel if not specified)."""
        name = name.strip('"')
        channel = channel or ctx.channel
        async with self.config.guild(channel.guild).patterns() as patterns:
            if name in patterns:
                await ctx.send(f"Rule '{name}' is undefined.")
                return
            async with self.config.channel(channel).blacklist() as blacklist:
                if name not in blacklist:
                    blacklist.append(name)
                    patterns[name]['uses'] += 1
        await ctx.tick()

    @automod.command()
    @commands.guild_only()
    @checks.mod_or_permissions(manage_guild=True)
    async def rmblacklist(self, ctx, channel: Optional[discord.TextChannel] = None, *, name):
        """Remove the named pattern as a blacklist for the given channel (this channel if not specified)."""
        name = name.strip('"')
        channel = channel or ctx.channel

        async with self.config.guild(channel.guild).patterns() as patterns:
            async with self.config.channel(channel).blacklist() as blacklist:
                if name not in blacklist:
                    await ctx.send(f"Rule '{name}' is undefined.")
                    return
                blacklist.remove(name)
                patterns[name]['uses'] -= 1
        await ctx.tick()

    @automod.command(name="list")
    @commands.guild_only()
    @checks.mod_or_permissions(manage_guild=True)
    async def am2_list(self, ctx):
        """List the whitelist/blacklist configuration for the current guild."""
        output = 'AutoMod configs\n'
        for channel in ctx.guild.channels:
            whitelists = await self.config.channel(channel).whitelist()
            blacklists = await self.config.channel(channel).blacklist()
            image_limit = await self.config.channel(channel).image_limit()
            auto_emojis = await self.config.channel(channel).autoemoji()

            if len(whitelists + blacklists + auto_emojis) + image_limit == 0:
                continue

            output += '\n#{}'.format(channel.name)
            output += '\n\tWhitelists'
            for name in whitelists:
                output += '\t\t{}\n'.format(name)
            output += '\n\tBlacklists'
            for name in blacklists:
                output += '\t\t{}\n'.format(name)
            output += '\n\tImage Limit: {}'.format(image_limit)
            output += '\n\tAuto Emojis: {}'.format(", ".join(auto_emojis))
        for page in pagify(output):
            await ctx.send(box(page))

    @automod.command()
    @commands.guild_only()
    @checks.mod_or_permissions(manage_guild=True)
    async def patterns(self, ctx):
        """List the registered patterns."""
        patterns = await ctx.config.guild(ctx.guild).patterns()
        output = 'AutoMod patterns for this server\n\n'
        output += self.patternsToTableText(patterns.values())
        for page in pagify(output):
            await ctx.send(box(page))

    @automod.command()
    @commands.guild_only()
    @checks.mod_or_permissions(manage_guild=True)
    async def imagelimit(self, ctx, channel: Optional[discord.TextChannel] = None, limit: int = None):
        """Prevents users from spamming images in a channel.

        If a user attempts to link/attach more than <limit> images in the active channel
        within the the lookback window (currently 5), all those messages are deleted.

        Set to 0 to clear.

        Set to -1 to enable image only.
        """
        channel = channel or ctx.channel

        if limit is None:
            await ctx.send('You must specify a limit')
            return
        await self.config.channel(channel).image_limit.set(limit)
        if limit == 0:
            await ctx.send('Limit cleared')
        elif limit == -1:
            await ctx.send('I will only allow images in this channel')
        else:
            await ctx.send('I will delete excess images in this channel')

    @commands.Cog.listener('on_message')
    async def mod_message_images(self, message):
        if message.author.id == self.bot.user.id or isinstance(message.channel, discord.DMChannel):
            return
        elif message.channel.permissions_for(message.author).manage_messages:
            return
        image_limit = await self.config.channel(message.channel).image_limit()
        if image_limit == 0:
            return
        elif image_limit > 0:
            key = (message.channel.id, message.author.id)
            self.channel_user_logs[key].append(message)

            user_logs = self.channel_user_logs[key]
            count = 0
            for m in user_logs:
                if (datetime.utcnow() - m.created_at).total_seconds() < 300:  # only check messages in past 300 seconds
                    count += linked_img_count(m)
            if count <= image_limit:
                return

            for m in list(user_logs):
                if (datetime.utcnow() - m.created_at).total_seconds() < 300:  # don't delete images from over 300s
                    if linked_img_count(m) > 0:
                        try:
                            await m.delete()
                        except Exception:
                            pass
                        try:
                            user_logs.remove(m)
                        except Exception:
                            pass

            msg = f'{message.author.mention} Upload multiple images to an imgur gallery #endimagespam'
            alert_msg = await message.channel.send(msg)
            await asyncio.sleep(10)
            await alert_msg.delete()
        else:
            if len(message.embeds) or len(message.attachments):
                return
            msg = f'Your message in {message.channel.name} was deleted for not containing an image'
            await self.deleteAndReport(message, msg)

    @commands.Cog.listener('on_message_edit')
    async def mod_message_edit(self, before, after):
        await self.mod_message(after)

    @commands.Cog.listener('on_message')
    async def mod_message(self, message):
        if isinstance(message.channel, discord.abc.PrivateChannel):
            return
        if message.author.bot or not isinstance(message.author, discord.Member):
            return
        if message.channel.permissions_for(message.author).manage_messages:
            return

        whitelists = await self.config.channel(message.channel).whitelist()
        blacklists = await self.config.channel(message.channel).blacklist()

        msg_content = message.clean_content
        for name in blacklists:
            pattern = (await self.config.guild(message.guild).patterns())[name]
            include_pattern = pattern['include_pattern']
            exclude_pattern = pattern['exclude_pattern']

            if not matchesIncludeExclude(include_pattern, exclude_pattern, msg_content):
                continue

            await self.deleteAndReport(message,
                                       box(f'Your message in {message.channel.name} was deleted for violating'
                                           f' the following policy: {name}\nMessage content: {msg_content}'))

        if whitelists:
            failed_whitelists = []
            for name in whitelists:
                pattern = (await self.config.guild(message.guild).patterns())[name]
                include_pattern = pattern['include_pattern']
                exclude_pattern = pattern['exclude_pattern']

                if matchesIncludeExclude(include_pattern, exclude_pattern, msg_content):
                    return
                failed_whitelists.append(name)
            await self.deleteAndReport(message, box(f'Your message in {message.channel.name} was deleted for violating'
                                                    f' the following policy: {",".join(failed_whitelists)}'
                                                    f'\nMessage content: {msg_content}'))

    @automod.command()
    @commands.guild_only()
    @checks.mod_or_permissions(manage_guild=True)
    async def autoemojis(self, ctx, *emoji):
        """Will automatically add a set of emojis to all messages sent in this channel.

        Add `[noemoji]` to a message to suppress emoji addition."""
        # TODO: Validate emoji
        await self.config.channel(ctx.channel).autoemoji.set(emoji)
        if not emoji:
            await ctx.send('Auto emojis cleared')
        else:
            await ctx.send('Autoemojis is configured for this channel.')

    @commands.Cog.listener('on_message')
    async def add_auto_emojis(self, message):
        if message.author.id == self.bot.user.id or isinstance(message.channel, discord.abc.PrivateChannel):
            return
        emoji_list = await self.config.channel(message.channel).autoemoji()
        if '[noemojis]' in message.content:
            return
        for emoji in emoji_list:
            await message.add_reaction(emoji)

    @commands.group()
    @commands.guild_only()
    @checks.mod_or_permissions(manage_guild=True)
    async def watchdog(self, ctx):
        """User monitoring tools."""

    @watchdog.command()
    @commands.guild_only()
    @checks.mod_or_permissions(manage_guild=True)
    async def printconfig(self, ctx):
        """Print the watchdog configuration."""
        msg = 'Watchdog config:'
        watchdog_channel_id = await self.config.guild(ctx.guild).watchdog_channel_id()
        if watchdog_channel_id:
            watchdog_channel = self.bot.get_channel(watchdog_channel_id)
            if watchdog_channel:
                msg += '\nChannel: ' + watchdog_channel.name
            else:
                msg += '\nChannel configured but not found'
        else:
            msg += '\nChannel not set'

        msg += '\n\nUsers'
        for user_id, user_settings in (await self.config.guild(ctx.guild).watched_users()).items():
            user_id = int(user_id)
            user_cooldown = user_settings['cooldown']
            request_user_id = user_settings['request_user_id']
            reason = user_settings['reason'] or 'no reason'

            request_user = ctx.guild.get_member(request_user_id)
            request_user_txt = request_user.name if request_user else '???'
            member = ctx.guild.get_member(user_id)
            if user_cooldown and member:
                msg += '\n{} ({})\n\tcooldown {}\n\tby {} because [{}]'.format(
                    member.name, member.id, user_cooldown, request_user_txt, reason)

        msg += '\n\nPhrases'
        for name, phrase_settings in (await self.config.guild(ctx.guild).phrases()).items():
            phrase_cooldown = phrase_settings['cooldown']
            request_user_id = phrase_settings['request_user_id']
            phrase = phrase_settings['phrase']

            request_user = ctx.guild.get_member(request_user_id)
            request_user_txt = request_user.name if request_user else '???'
            if phrase_cooldown:
                msg += '\n{} -> {}\n\tcooldown {}\n\tby {}'.format(
                    name, phrase, phrase_cooldown, request_user_txt)

        for page in pagify(msg):
            await ctx.send(box(page))

    @watchdog.command()
    @commands.guild_only()
    @checks.mod_or_permissions(manage_guild=True)
    async def user(self, ctx, user: discord.User, cooldown: int = None, *, reason: str = ''):
        """Keep an eye on a user.

        Whenever the user speaks in this server, a note will be printed to the watchdog
        channel, subject to the specified cooldown in seconds. Set to 0 to clear.
        """
        if cooldown is None:
            user_settings = (await self.config.guild(ctx.guild).watched_users()).get(str(user.id), {})
            existing_cd = user_settings.get('cooldown', 0)
            if existing_cd == 0:
                await ctx.send('No watchdog for that user')
            else:
                await ctx.send(f'Watchdog set with cooldown of {existing_cd} seconds')
        else:
            async with self.config.guild(ctx.guild).watched_users() as watched_users:
                if cooldown == 0:
                    if str(user.id) in watched_users:
                        del watched_users[str(user.id)]
                    await ctx.send(f'Watchdog cleared for {user.name}')
                else:
                    if not reason:
                        await ctx.send("You must supply a reason.")
                        return
                    watched_users[str(user.id)] = {
                        'request_user_id': ctx.author.id,
                        'cooldown': cooldown,
                        'reason': reason,
                    }
                    await ctx.send('Watchdog set on {user.name} with cooldown of {cooldown} seconds')

    @watchdog.command()
    @commands.guild_only()
    @checks.mod_or_permissions(manage_guild=True)
    async def phrase(self, ctx, name: str, cooldown: int, *, phrase: str = None):
        """Keep an eye out for a phrase (regex).

        Whenever the regex is matched, a note will be printed to the watchdog
        channel, subject to the specified cooldown in seconds.

        Name is descriptive. Set a cooldown of 0 to clear.
        """
        server_id = ctx.guild.id
        async with self.config.guild(ctx.guild).phrases() as phrases:
            if cooldown == 0:
                if phrase in phrases:
                    del phrases[phrase]
                await ctx.send(f'Watchdog phrase cleared for {name}')
                return

            try:
                re.compile(phrase)
            except Exception as ex:
                await ctx.send(inline(str(ex)))
                return

            if cooldown < 300:
                await ctx.send('Overriding cooldown to minimum (300 seconds)')
                cooldown = 300
            phrases[name] = {
                'request_user_id': ctx.author.id,
                'cooldown': cooldown,
                'phrase': phrase,
            }
            self.server_phrase_last[server_id][name] = None
            await ctx.send(f'Watchdog named {name} set on {phrase} with cooldown of {cooldown} seconds')

    @watchdog.command()
    @commands.guild_only()
    @checks.mod_or_permissions(manage_guild=True)
    async def channel(self, ctx, channel: discord.TextChannel = None):
        """Set the announcement channel."""
        channel = channel or ctx.channel
        await self.config.guild(ctx.guild).watchdog_channel_id.set(channel.id)
        await ctx.tick()

    @commands.Cog.listener('on_message')
    async def mod_message_watchdog(self, message):
        if message.author.id == self.bot.user.id or isinstance(message.channel, discord.abc.PrivateChannel):
            return
        if await self.config.guild(message.guild).watchdog_channel_id() is None:
            return

        await self.mod_message_watchdog_user(message)
        await self.mod_message_watchdog_phrase(message)

    async def mod_message_watchdog_user(self, message):
        user_id = message.author.id
        server_id = message.guild.id
        watchdog_channel_id = await self.config.guild(message.guild).watchdog_channel_id()
        user_settings = (await self.config.guild(message.guild).watched_users()).get(str(message.author.id))

        if user_settings is None:
            return

        cooldown = user_settings['cooldown']
        if cooldown <= 0:
            return

        request_user_id = user_settings['request_user_id']
        reason = user_settings['reason'] or 'no reason'

        request_user = message.guild.get_member(request_user_id)
        request_user_txt = request_user.mention if request_user else '???'

        now = datetime.utcnow()
        last_spoke_at = self.server_user_last[server_id].get(message.author.id)
        self.server_user_last[server_id][message.author.id] = now
        time_since = (now - last_spoke_at).total_seconds() if last_spoke_at else 9999

        report = time_since > cooldown
        if not report:
            return

        output_msg = '**Watchdog:** {} spoke in {} ({} monitored because [{}])\n{}'.format(
            message.author.mention, message.channel.mention,
            request_user_txt, reason, box(message.clean_content))
        await self._watchdog_show(watchdog_channel_id, output_msg)

    async def mod_message_watchdog_phrase(self, message):
        server_id = message.guild.id
        watchdog_channel_id = await self.config.guild(message.guild).watchdog_channel_id()

        for name, phrase_settings in (await self.config.guild(message.guild).phrases()).items():
            cooldown = phrase_settings['cooldown']
            request_user_id = phrase_settings['request_user_id']
            phrase = phrase_settings['phrase']

            if cooldown <= 0:
                continue

            now = datetime.utcnow()
            last_spoke_at = self.server_phrase_last[server_id].get(name)
            time_since = (now - last_spoke_at).total_seconds() if last_spoke_at else 9999

            report = time_since > cooldown
            if not report:
                continue

            p = re.compile(phrase, re.IGNORECASE | re.MULTILINE | re.DOTALL)
            if p.match(message.clean_content):
                self.server_phrase_last[server_id][name] = now
                output_msg = '**Watchdog:** {} spoke in {} `(rule [{}] matched phrase [{}])`\n{}'.format(
                    message.author.mention, message.channel.mention,
                    name, phrase, box(message.clean_content))
                await self._watchdog_show(watchdog_channel_id, output_msg)
                return

    async def _watchdog_show(self, watchdog_channel_id, output_msg):
        try:
            watchdog_channel = self.bot.get_channel(watchdog_channel_id)
            await watchdog_channel.send(output_msg)
        except Exception as ex:
            logger.exception('failed to watchdog')

    async def deleteAndReport(self, delete_msg, outgoing_msg):
        try:
            await delete_msg.delete()
            try:
                await delete_msg.author.send(outgoing_msg)
            except discord.Forbidden:
                pass
        except Exception as e:
            logger.exception('Failure while deleting message from {}, tried to send : {}'.format(
                delete_msg.author.name, outgoing_msg))

    def patternsToTableText(self, patterns):
        tbl = prettytable.PrettyTable(["Rule Name", "Include regex", "Exclude regex"])
        tbl.hrules = prettytable.HEADER
        tbl.vrules = prettytable.NONE
        tbl.align = "l"

        for value in patterns:
            tbl.add_row([value['name'], value['include_pattern'], value['exclude_pattern']])

        return tsutils.strip_right_multiline(tbl.get_string())


def starts_with_code(txt):
    # ignore spaces before or in code
    txt = txt.replace(' ', '')
    # ignore tilde, some users use them to cross out rooms
    txt = txt.replace('~', '')
    if len(txt) < 8:
        return False
    return pad_checkdigit(txt[0:8])


def pad_checkdigit(n):
    n = str(n)
    checkdigit = int(n[7])
    checksum = 7
    for idx in range(0, 7):
        checksum += int(n[idx])
    calcdigit = checksum % 10
    return checkdigit == calcdigit


CUSTOM_PATTERNS = {
    'starts_with_code': starts_with_code,
    'pad_checkdigit': pad_checkdigit,
}


def matchesIncludeExclude(include_pattern, exclude_pattern, txt):
    if matchesPattern(include_pattern, txt):
        return not matchesPattern(exclude_pattern, txt)
    return False


def matchesPattern(pattern, txt):
    if not len(pattern):
        return False

    try:
        if pattern[0] == pattern[-1] == ':':
            check_method = CUSTOM_PATTERNS.get(pattern[1:-1])
            if check_method:
                return check_method(txt)
    except Exception:
        return False

    p = re.compile(pattern, re.IGNORECASE | re.MULTILINE | re.DOTALL)
    return p.match(txt)


class AutoMod2Settings(CogSettings):
    def make_default_settings(self):
        return {'configs': {}}
