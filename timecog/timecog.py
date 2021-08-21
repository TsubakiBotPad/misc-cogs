import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone
from io import BytesIO
from typing import Any, Optional, Tuple

import discord
import pytz
import time
import tsutils
from dateutil.relativedelta import relativedelta
from discord import User
from redbot.core import Config, checks, commands
from redbot.core.bot import Red
from redbot.core.utils.chat_formatting import box, inline, pagify

logger = logging.getLogger('red.misc-cogs.timecog')

tz_lookup = dict([(pytz.timezone(x).localize(datetime.now()).tzname(), pytz.timezone(x))
                  for x in pytz.all_timezones])

time_at_regeces = [
    r'^\s*(?:(?:(?P<year>\d{4})[-/])?(?P<month>\d+)[-/](?P<day>\d+) )?(?:(?P<hour>\d+):?(?P<minute>\d\d)? ?(?P<merid>pm|am)?)? \"?(?P<input>.*)\"?$',
]

time_in_regeces = [
    r'^\s*((?:-?\d+ ?(?:m|h|d|w|y|s)\w* ?)+|now)\b (.+)$',  # One tinstr
    r'^\s*((?:-?\d+ ?(?:m|h|d|w|y|s)\w* ?)+)\b\s*(?:\||in|start(?:ing)? in)\s*((?:-?\d+ ?(?:m|h|d|w|y|s)\w* ?)+|now)\b (.*)$',
    # Unused
]

exact_tats = [
    r'^\s*(?P<year>\d{4})[-/](?P<month>\d+)[-/](?P<day>\d+) (?P<hour>\d+):(?P<minute>\d\d) ?(?P<merid>pm|am)?\s*$',
    r'^\s*(?P<year>\d{4})[-/](?P<month>\d+)[-/](?P<day>\d+)\s*$',
    r'^\s*(?P<month>\d+)[-/](?P<day>\d+)\s*$',
    r'^\s*(?P<hour>\d+):(?P<minute>\d\d) ?(?P<merid>\d?pm|am)?\s*$',
    r'^\s*(?P<hour>\d+) ?(?P<merid>\d?pm|am)\s*$',
]

exact_tins = [
    r'^\s*((?:-?\d+ ?(?:m|h|d|w|y|s)\w* ?)+)$',  # One tinstr
]

DT_FORMAT = "%A, %b %-d, %Y at %-I:%M %p"
SHORT_DT_FORMAT = "%b %-d, %Y at %-I:%M %p"


class TimeCog(commands.Cog):
    """Utilities pertaining to time"""

    def __init__(self, bot: Red, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config = Config.get_conf(self, identifier=7173306)
        self.config.register_user(reminders=[], tz='', show_tz=True)
        self.config.register_guild(schedules={})

        """
        CONFIG: Config
        |   USERS: Config
        |   |   reminders: list
        |   |   |   REMINDER: tuple
        |   |   |   |   TIME: int (timestamp)
        |   |   |   |   TEXT: str
        |   |   |   |   INTERVAL: Optional[int]
        |   |   |   |   CHAN_ID: int
        |   |   tz: str (tzstr)
        |   CHANNELS: Config
        |   |   schedules: dict
        |   |   |   NAME: dict
        |   |   |   |   start: int (timestamp) (unused)
        |   |   |   |   time: int (timestamp)
        |   |   |   |   end: int (timestamp)
        |   |   |   |   interval: int (seconds)
        |   |   |   |   enabled: bool
        |   |   |   |   channels: list (cids)
        |   |   |   |   message: str
        """

        self._reminder_loop = bot.loop.create_task(self.reminderloop())

        self.bot = bot

    async def red_get_data_for_user(self, *, user_id):
        """Get a user's personal data."""
        udata = await self.config.user_from_id(user_id).reminders()

        data = "You have {} reminder(s) set.\n".format(len(udata))

        if not udata:
            data = "No data is stored for user with ID {}.\n".format(user_id)

        return {"user_data.txt": BytesIO(data.encode())}

    async def red_delete_data_for_user(self, *, requester, user_id):
        """Delete a user's personal data."""
        await self.config.user_from_id(user_id).clear()

    def cog_unload(self):
        self._reminder_loop.cancel()

    async def restart_loop(self):
        while True:
            try:
                await asyncio.sleep(60 * 60)
                if self._reminder_loop.done():
                    logger.info("Refreshing TimeCog loop...")
                    e = self._reminder_loop.exception()
                    if e:
                        logger.error("Exception in TimeCog loop: {!r}".format(e))
                    self._reminder_loop = self.bot.loop.create_task(self.reminderloop())
            except Exception:
                pass

    async def remindme_parse(self, ctx, timestr):
        """Reminds you to do something at a specified time

        [p]remindme 2020-04-13 06:12 Do something!
        [p]remindme 5 weeks Do something!
        [p]remindme 4:13 PM Do something!
        [p]remindme 2020-05-03 Do something!
        [p]remindme 04-13 Do something!
        """

        user_timezone, set_tz = await self.get_timezone(ctx.author)

        for ar in time_at_regeces:
            match = re.search(ar, timestr, re.IGNORECASE)
            if not match or re.match(r"\d+ [^ap][^m]", timestr, re.IGNORECASE):
                continue
            match = match.groupdict()

            if not set_tz:
                await ctx.send(
                    "Please configure your personal timezone with `{0.prefix}pref timezone` first.".format(ctx))
                return

            now = datetime.now(tz=user_timezone)
            defaults = {
                'year': now.year,
                'month': now.month,
                'day': now.day,
                'hour': now.hour,
                'minute': 0,
                'merid': 'AM'
            }
            if not any([match[k] for k in defaults]):
                continue
            defaults.update({k: v for k, v in match.items() if v})
            text = defaults.pop('input')
            for key in defaults:
                if key not in ['merid']:
                    defaults[key] = int(defaults[key])
            if defaults['merid'].lower() == 'pm' and defaults['hour'] <= 12:
                defaults['hour'] += 12
            elif defaults['merid'] == 'NONE' and defaults['hour'] < now.hour:
                defaults['hour'] += 12
            if defaults['hour'] >= 24:
                defaults['day'] += int(defaults['hour'] // 24)
                defaults['hour'] = defaults['hour'] % 24
            del defaults['merid']
            try:
                rmtime = user_timezone.localize(datetime(**defaults))
            except ValueError as e:
                await ctx.send(inline(str(e).capitalize()))
                return
            if rmtime < now:
                rmtime += timedelta(days=1)
            rmtime = rmtime.astimezone(pytz.utc).replace(tzinfo=None)
            break
        else:
            ir = time_in_regeces[0]
            match = re.search(ir, timestr, re.IGNORECASE)
            if not match:  # Only use the first one
                raise commands.UserFeedbackCheckFailure("Invalid time string: " + timestr)
            tinstrs, text = match.groups()
            rmtime = datetime.utcnow()
            try:
                rmtime += tin2tdelta(tinstrs)
            except OverflowError:
                raise commands.UserFeedbackCheckFailure(
                    inline("That's way too far in the future!  Please keep it in your lifespan!"))

        if rmtime < (datetime.utcnow() - timedelta(seconds=1)):
            raise commands.UserFeedbackCheckFailure(inline("You can't set a reminder in the past!  If only..."))

        return rmtime, text

    @commands.group(aliases=['remindmeat', 'remindmein'], invoke_without_command=True)
    async def remindme(self, ctx, *, timestr):
        rmtime, text = await self.remindme_parse(ctx, timestr)
        user_timezone, set_tz = await self.get_timezone(ctx.author)
        user_show_tz = await self.config.user(ctx.author).show_tz()

        async with self.config.user(ctx.author).reminders() as rms:
            rms.append((rmtime.timestamp(), text, -1, 0))

        response = "I will tell you " + format_rm_time(ctx.channel, rmtime, text, user_timezone, user_show_tz)
        if not set_tz:
            response += '. Configure your personal timezone with `{0.prefix}pref timezone` for accurate times.'.format(
                ctx)
        await ctx.send(response)

    @commands.command()
    @checks.mod_or_permissions(manage_messages=True)
    async def remindmehere(self, ctx, *, timestr):
        rmtime, text = await self.remindme_parse(ctx, timestr)
        user_timezone, set_tz = await self.get_timezone(ctx.author)
        user_show_tz = await self.config.user(ctx.author).show_tz()

        async with self.config.user(ctx.author).reminders() as rms:
            rms.append((rmtime.timestamp(), text, -1, ctx.channel.id))

        response = "In this channel, I will tell you " + format_rm_time(ctx.channel, rmtime, text, user_timezone,
                                                                        user_show_tz)
        if not set_tz:
            response += '. Configure your personal timezone with `{0.prefix}pref timezone` for accurate times.'.format(
                ctx)
        await ctx.send(response)

    @remindme.command(hidden=True)
    async def now(self, ctx, *, reminder):
        await ctx.author.send(reminder)

    @remindme.command()
    async def every(self, ctx, *, text):
        """Reminds you to do something at a specified time at a specified interval

        [p]remindme every 1d Do something!
        [p]remindme every 1d in 3 minutes Do something!
        [p]remindme every 1 week | 3 minutes something!
        """
        match = re.search(time_in_regeces[1], text, re.IGNORECASE)
        if match:
            tinstrs, tinstart, reminder = match.groups()
        else:
            match = re.search(time_in_regeces[0], text, re.IGNORECASE)
            if not match:
                await ctx.send("Invalid interval")
                return
            tinstart = "now"
            tinstrs, reminder = match.groups()
        start = (datetime.utcnow() + tin2tdelta(tinstart)).timestamp()
        async with self.config.user(ctx.author).reminders() as rms:
            rms.append((start, reminder, tin2tdelta(tinstrs).seconds, 0))
        user_show_tz = await self.config.user(ctx.author).show_tz()
        m = await ctx.send("I will tell you {} and every {} seconds after that."
                           "".format(format_rm_time(
            ctx.channel,
            datetime.utcnow() + tin2tdelta(tinstart),
            reminder,
            (await self.get_timezone(ctx.author))[0],
            user_show_tz),
            tin2tdelta(tinstrs).seconds))

    @remindme.command(aliases=["list"])
    async def get(self, ctx):
        """Get a list of all pending reminders"""
        rlist = sorted((await self.config.user(ctx.author).reminders()), key=lambda x: x[0])
        if not rlist:
            await ctx.send(inline("You have no pending reminders!"))
            return
        tz, _ = await self.get_timezone(ctx.author)
        user_show_tz = await self.config.user(ctx.author).show_tz()
        o = []
        for c, rm in enumerate(rlist):
            timestamp = rm[0]
            reminder = rm[1]
            ftime = format_rm_time(ctx.channel, datetime.fromtimestamp(float(timestamp)), reminder, tz, user_show_tz)
            if len(rm) > 2 and rm[2] != -1:
                ftime += f" (every {rm[2]} seconds)"
            if len(rm) > 3 and rm[3] != 0:
                ftime += f" (in #{self.bot.get_channel(rm[3])})"
            o.append(str(c + 1) + ": " + ftime)
        await ctx.send(box('\n'.join(o)))

    @remindme.command(name="remove", aliases=["rm", "delete", "del"])
    async def remindme_remove(self, ctx, no: int):
        """Remove a specific pending reminder"""
        rlist = sorted(await self.config.user(ctx.author).reminders(), key=lambda x: x[0])
        if len(rlist) < no:
            await ctx.send(inline("There is no reminder #{}".format(no)))
            return
        async with self.config.user(ctx.author).reminders() as rms:
            rms.remove(rlist[no - 1])
        await ctx.tick()

    @remindme.command()
    async def purge(self, ctx):
        """Delete all pending reminders."""
        await self.config.user(ctx.author).reminders.set([])
        await ctx.tick()

    @remindme.command()
    async def toggletzprivate(self, ctx, private: bool = True):
        """Hide/show your time zone in reminders"""
        await self.config.user(ctx.author).show_tz.set(not private)
        if private:
            await ctx.send("Ok, your time zone is now set to **private**."
                           " I will **hide** your time zone when I confirm"
                           " or list your reminders in a server.")
        else:
            await ctx.send("Ok, your time zone is now set to **public**."
                           " I will **show** your time zone when I confirm"
                           " or list your reminders in a server.")

    @commands.group(invoke_without_command=True)
    @checks.mod_or_permissions(administrator=True)
    async def schedule(self, ctx, name, *, text):
        """Sets up a schedule to fire at the specified interval

        [p]schedule name 1d Do something!
        [p]schedule name 5 hours Do something!
        """
        match = re.search(time_in_regeces[0], text, re.IGNORECASE)
        if match:
            tinstart = "now"
            tinstrs, reminder = match.groups()
        else:
            match = re.search(time_in_regeces[1], text, re.IGNORECASE)
            if not match:
                if name.isdigit() or re.search(time_in_regeces[0], name + " .", re.IGNORECASE):
                    await ctx.send("Invalid interval.  Remember to put 'name' as the first argument.")
                else:
                    await ctx.send_help()
                return
            tinstart, tinstrs, reminder = match.groups()
        start = (datetime.utcnow() + tin2tdelta(tinstart)).timestamp()

        async with self.config.guild(ctx.guild).schedules() as schedules:
            if name in schedules:
                await ctx.send("There is already a schedule with this name.")
                return
            schedules[name] = {
                "start": start,
                "time": start,
                "end": 2e11,
                "interval": tin2tdelta(tinstrs).seconds,
                "enabled": True,
                "channels": [ctx.channel.id],
                "message": reminder,
            }
        m = await ctx.send("Schedule created.")
        await asyncio.sleep(5.)
        await m.delete()

    @schedule.command(aliases=["start"])
    async def begin(self, ctx, name, *, start_time):
        """Sets the start time for a schedule."""
        start_time = await self.exact_tartintodt(ctx, start_time)
        if start_time is None:
            return
        async with self.config.guild(ctx.guild).schedules() as schedules:
            if name not in schedules:
                await ctx.send("There is no schedule with this name.")
                return
            schedules[name]['start'] = start_time.timestamp()
            schedules[name]['time'] = start_time.timestamp()
        await ctx.tick()

    @schedule.command()
    async def end(self, ctx, name, *, end_time):
        """Sets the end time for a schedule."""
        end_time = await self.exact_tartintodt(ctx, end_time)
        if end_time is None:
            return
        async with self.config.guild(ctx.guild).schedules() as schedules:
            if name not in schedules:
                await ctx.send("There is no schedule with this name.")
                return
            schedules[name]['end'] = end_time.timestamp()
        await ctx.tick()

    @schedule.command()
    async def interval(self, ctx, name, *, interval_time):
        """Sets the interval for a schedule."""
        if not re.match(exact_tins[0], interval_time):
            await ctx.send("Invalid interval.")
            return
        interval = tin2tdelta(interval_time)
        if interval is None:
            return
        async with self.config.guild(ctx.guild).schedules() as schedules:
            if name not in schedules:
                await ctx.send("There is no schedule with this name.")
                return
            schedules[name]['interval'] = interval.seconds
        await ctx.tick()

    @schedule.command()
    async def message(self, ctx, name, *, message):
        """Sets the message for a schedule."""
        async with self.config.guild(ctx.guild).schedules() as schedules:
            if name not in schedules:
                await ctx.send("There is no schedule with this name.")
                return
            schedules[name]['message'] = message
        await ctx.tick()

    @schedule.group()
    async def channel(self, ctx):
        """Set or remove channels for a schedule."""

    @channel.command()
    async def add(self, ctx, name, channel: discord.TextChannel):
        """Add a channel."""
        async with self.config.guild(ctx.guild).schedules() as schedules:
            if name not in schedules:
                await ctx.send("There is no schedule with this name.")
                return
            if channel.id in schedules[name]['channels']:
                await ctx.send("This channel is already registered.")
                return
            schedules[name]['channels'].append(channel.id)
        await ctx.tick()

    @channel.command(name="remove")
    async def channel_remove(self, ctx, name, channel: discord.TextChannel):
        """Remove a channel."""
        async with self.config.guild(ctx.guild).schedules() as schedules:
            if name not in schedules:
                await ctx.send("There is no schedule with this name.")
                return
            if channel.id not in schedules[name]['channels']:
                await ctx.send("This channel is not registered.")
                return
            schedules[name]['channels'].remove(channel.id)
        await ctx.tick()

    @channel.command(name="list")
    async def channel_list(self, ctx, name):
        """List the registered channels."""
        async with self.config.guild(ctx.guild).schedules() as schedules:
            if name not in schedules:
                await ctx.send("There is no schedule with this name.")
                return
            if not schedules[name]['channels']:
                await ctx.send("This schedule has no channels.")
                return
            o = ""
            for c in schedules[name]['channels']:
                ch = self.bot.get_channel(c)
                if ch:
                    o += "{} ({})\n".format(ch.name, c)
                else:
                    o += "deleted-channel ({})\n".format(c)
        for p in pagify(o):
            await ctx.send(box(p))

    @schedule.command()
    async def enable(self, ctx, name):
        """Enable a schedule."""
        async with self.config.guild(ctx.guild).schedules() as schedules:
            if name not in schedules:
                await ctx.send("There is no schedule with this name.")
                return
            schedules[name]['enabled'] = True
        await ctx.tick()

    @schedule.command()
    async def disable(self, ctx, name):
        """Disable a schedule."""
        async with self.config.guild(ctx.guild).schedules() as schedules:
            if name not in schedules:
                await ctx.send("There is no schedule with this name.")
                return
            schedules[name]['enabled'] = False
        await ctx.tick()

    @schedule.command(name="remove")
    async def schedule_remove(self, ctx, name):
        """Remove a schedule."""
        async with self.config.guild(ctx.guild).schedules() as schedules:
            if name not in schedules:
                await ctx.send("There is no schedule with this name.")
                return
            del schedules[name]
        await ctx.send(inline("Deleted schedule {}.".format(name)))

    @schedule.command(name="list")
    async def schedule_list(self, ctx):
        """List the guild's schedules."""
        async with self.config.guild(ctx.guild).schedules() as schedules:
            o = ""
            for n, s in schedules.items():
                o += " - {}{}\n".format(n, " (disabled)" if not s['enabled'] else " (expired)" if s[
                                                                                                      'end'] < datetime.utcnow().timestamp() else "")
                o += "   - Start Time: {}\n".format(datetime.fromtimestamp(s['start']).strftime(SHORT_DT_FORMAT))
                o += "   - Next Time: {}\n".format(datetime.fromtimestamp(s['time']).strftime(SHORT_DT_FORMAT))
                o += "   - End Time: {}\n".format(datetime.fromtimestamp(s['end']).strftime(SHORT_DT_FORMAT))
                o += "   - Interval: {}\n".format(timedelta(seconds=s['interval']))
                o += "   - Message: {}\n".format(s['message'])
        if not o:
            await ctx.send(inline("There are no schedules for this guild."))
        for page in pagify(o):
            await ctx.send(box(page))

    async def reminderloop(self):
        try:
            await self.bot.wait_until_ready()
            async for _ in tsutils.repeating_timer(10, lambda: self == self.bot.get_cog('TimeCog')):
                urs = await self.config.all_users()
                gds = await self.config.all_guilds()
                now = datetime.utcnow()
                for u in urs:
                    for c, rm in enumerate(urs[u]['reminders']):
                        if datetime.fromtimestamp(float(rm[0])) < now:
                            async with self.config.user_from_id(u).reminders() as rms:
                                if len(rm) > 2 and rm[2] != -1:
                                    rms[c][0] += rms[c][2]
                                else:
                                    rms.remove(rm)
                            try:
                                if len(rm) > 3 and rm[3] != 0:
                                    await self.bot.get_channel(rm[3]).send(rm[1])
                                else:
                                    await self.bot.get_user(u).send(rm[1])
                            except (discord.Forbidden, AttributeError):
                                pass
                for g in gds:
                    for n, sc in gds[g]['schedules'].items():
                        if datetime.fromtimestamp(sc['end']) < now or not sc['enabled']:
                            continue
                        if datetime.fromtimestamp(float(sc['time'])) < now:
                            async with self.config.guild_from_id(g).schedules() as scs:
                                scs[n]['time'] += scs[n]['interval']
                            for ch in sc['channels']:
                                try:
                                    await self.bot.get_channel(ch).send(sc['message'])
                                except (AttributeError, discord.Forbidden):
                                    pass
        except asyncio.CancelledError:
            pass

    @commands.command()
    async def time(self, ctx, *, tz: str):
        """Displays the current time in the supplied timezone"""
        try:
            tz_obj = tzstr_to_tz(tz)
        except Exception as e:
            await ctx.send("Failed to parse tz: " + tz)
            return

        now = datetime.now(tz_obj)
        msg = "The time in " + now.strftime('%Z') + " is " + fmt_time_short(now).strip()
        await ctx.send(inline(msg))

    @commands.command()
    async def timeto(self, ctx, tz: str, *, timestr: str):
        """Compute the time remaining until the [timezone] [time].

        The order of arguments does not matter.
        Times should either contain am or pm or will be interpreted in 24-hour time.
        """
        tz_obj = time_obj = None

        try:
            tz_obj = tzstr_to_tz(tz)
        except Exception:
            try:
                tz_obj = tzstr_to_tz(timestr)
                timestr, tz = tz, timestr
            except Exception:
                await ctx.send("Failed to parse tz: " + tz)
                return

        try:
            time_obj = timestr_to_time(timestr)
        except Exception as e:
            await ctx.send("Failed to parse argument: " + timestr)
            return

        now = datetime.now(tz_obj)
        req_time = now.replace(hour=time_obj.tm_hour, minute=time_obj.tm_min)

        if req_time < now:
            req_time = req_time + timedelta(days=1)
        delta = req_time - now

        msg = ("There are " + fmt_hrs_mins(delta.seconds).strip() +
               " until " + req_time.strftime('%-I:%M%p').lower() + " in " + now.strftime('%Z'))
        await ctx.send(inline(msg))

    async def exact_tartintodt(self, ctx, timestr, allowtat=True):
        user_timezone, set_tz = await self.get_timezone(ctx.author)

        for ar in exact_tats:
            if not allowtat:
                continue
            match = re.match(ar, timestr, re.IGNORECASE)
            if not match:
                continue
            match = match.groupdict()

            if not set_tz:
                await ctx.send(
                    "Please configure your personal timezone with `{0.prefix}pref timezone` first.".format(ctx))
                return

            now = datetime.now(tz=user_timezone)
            defaults = {
                'year': now.year,
                'month': now.month,
                'day': now.day,
                'hour': now.hour,
                'minute': now.minute,
                'merid': 'NONE'
            }
            defaults.update({k: v for k, v in match.items() if v})
            for key in defaults:
                if key not in ['merid']:
                    defaults[key] = int(defaults[key])
            if defaults['merid'] == 'pm' and defaults['hour'] <= 12:
                defaults['hour'] += 12
            elif defaults['merid'] == 'NONE' and defaults['hour'] < now.hour:
                defaults['hour'] += 12
            if defaults['hour'] >= 24:
                defaults['day'] += int(defaults['hour'] // 24)
                defaults['hour'] = defaults['hour'] % 24
            del defaults['merid']
            try:
                rmtime = user_timezone.localize(datetime(**defaults))
            except ValueError as e:
                await ctx.send(inline(str(e).capitalize()))
                return
            if rmtime < now:
                rmtime += timedelta(days=1)
            rmtime = rmtime.astimezone(pytz.utc).replace(tzinfo=None)
            break
        else:
            ir = exact_tins[0]
            match = re.search(ir, timestr, re.IGNORECASE)
            if not match:  # Only use the first one
                raise commands.UserFeedbackCheckFailure("Invalid time string: " + timestr)
            tinstrs, = match.groups()
            rmtime = datetime.utcnow()
            try:
                rmtime += tin2tdelta(tinstrs)
            except OverflowError:
                raise commands.UserFeedbackCheckFailure(
                    inline("That's way too far in the future! Please keep it in your lifespan!"))

        return rmtime

    async def get_timezone(self, user: User) -> Tuple[Optional[Any], bool]:
        cog: Any = self.bot.get_cog("UserPreferences")
        if cog is None:
            logger.info("UserPreferences cog not loaded.")
            return pytz.UTC, True
        if (tz := await cog.get_user_timezone(user)) is None:
            return pytz.UTC, False
        return tz, True


def timestr_to_time(timestr):
    timestr = timestr.replace(" ", "")
    try:
        return time.strptime(timestr, "%H:%M")
    except ValueError:
        pass
    try:
        return time.strptime(timestr, "%I:%M%p")
    except ValueError:
        pass
    try:
        return time.strptime(timestr, "%I%p")
    except ValueError:
        pass
    raise commands.UserFeedbackCheckFailure("Invalid Time: " + timestr)


def fmt_hrs_mins(seconds):
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    return '{}hrs {}mins'.format(int(hours), int(minutes))


def fmt_time_short(dt):
    return dt.strftime("%I:%M %p")


def tzstr_to_tz(tzstr: str):
    tzstr = tzstr.upper().strip()
    if tzstr in ('EST', 'EDT', 'ET'):
        return pytz.timezone('America/New_York')
    if tzstr in ('MST', 'MDT', 'MT'):
        return pytz.timezone('America/North_Dakota/Center')
    if tzstr in ('PST', 'PDT', 'PT'):
        return pytz.timezone('America/Los_Angeles')
    if tzstr in ('CST', 'CDT', 'CT'):
        return pytz.timezone('America/Chicago')
    if tzstr in ('JP', 'JST', 'JT'):
        return pytz.timezone('Japan')
    if tzstr in ('NA', 'US'):
        return timezone(timedelta(hours=-8))
    if tzstr in tz_lookup:
        return tz_lookup[tzstr]
    if (match := re.match(r"^UTC([-+]\d+)$", tzstr)):
        return timezone(timedelta(hours=int(match.group(1))))
    for tz in pytz.all_timezones:
        if tzstr in tz.upper().split("/"):
            return pytz.timezone(tz)
    for tz in pytz.all_timezones:
        if tzstr in tz.upper():
            return pytz.timezone(tz)
    raise commands.UserFeedbackCheckFailure("Invalid timezone: " + tzstr)


def tin2tdelta(tinstr):
    if tinstr.lower().strip() == "now":
        return timedelta(0)
    tins = re.findall(r'(-?\d+) ?([a-z]+) ?', tinstr.lower())
    o = timedelta()
    for tin, unit in tins:
        try:
            tin = int(tin)
            if unit[:2] == 'mo':
                o += relativedelta(months=+tin)
            elif unit[0] == 'm':
                o += timedelta(minutes=tin)
            elif unit[0] == 'h':
                o += timedelta(hours=tin)
            elif unit[0] == 'd':
                o += timedelta(days=tin)
            elif unit[0] == 'w':
                o += timedelta(weeks=tin)
            elif unit[0] == 'y':
                o += relativedelta(years=+tin)
            elif unit[0] == 's':
                raise commands.UserFeedbackCheckFailure(
                    "We aren't exact enough to use seconds! If you need that precision, try this: https://www.timeanddate.com/timer/")
            else:
                raise commands.UserFeedbackCheckFailure(inline(
                    "Invalid unit: {}\nPlease use minutes, hours, days, weeks, months, or, if you're feeling especially zealous, years.".format(
                        unit)))
        except OverflowError:
            raise commands.UserFeedbackCheckFailure(inline("Come on... Be reasonable :/"))
    return o


def ydhm(seconds):
    y, seconds = divmod(seconds, 60 * 60 * 24 * 365)
    d, seconds = divmod(seconds, 60 * 60 * 24)
    h, seconds = divmod(seconds, 60 * 60)
    m, seconds = divmod(seconds, 60)
    y, d, h, m = [int(val) for val in (y, d, h, m)]
    ret = []
    if y:
        ret.append("{} yr".format(y) + ("s" if y > 1 else ''))
    if d:
        ret.append("{} day".format(d) + ("s" if d > 1 else ''))
    if h:
        ret.append("{} hr".format(h) + ("s" if h > 1 else ''))
    if m:
        ret.append("{} min".format(m) + ("s" if m > 1 else ''))
    return " ".join(ret) or "<1 minute"


def format_rm_time(ctx_channel, rmtime, text, D_TZ, show_tz):
    if not isinstance(ctx_channel, discord.DMChannel) and not show_tz:
        return "'{}' ({} from now)".format(
            text,
            ydhm((rmtime - datetime.utcnow()).total_seconds() + 2)
        )
    return "'{}' on {} {} ({} from now)".format(
        text,
        D_TZ.fromutc(rmtime).strftime(DT_FORMAT),
        get_tz_name(D_TZ, rmtime),
        ydhm((rmtime - datetime.utcnow()).total_seconds() + 2)
    )


def get_tz_name(tz, dt=None):
    if dt is None:
        dt = datetime.utcnow()
    else:
        dt = dt.replace(tzinfo=None)
    tzname = tz.tzname(datetime(year=dt.year, month=1, day=1))
    tznowname = tz.tzname(dt)
    if tzname != tznowname and tznowname:
        return "{} ({})".format(tzname, tznowname)
    return tzname
