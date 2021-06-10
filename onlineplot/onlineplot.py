import asyncio
import os
import re

import sys
from datetime import datetime, time
from io import BytesIO
import logging
from typing import Tuple, Sequence, List, Optional

import aioodbc
import discord
from aioodbc import Pool
from pytz.tzinfo import DstTzInfo
from redbot.core import commands, Config, data_manager
import matplotlib.pyplot as plt

logger = logging.getLogger('red.misc-cogs.onlineplot')

plt.interactive(False)

WEEKDAYS = {
    "monday": 1,
    "tuesday": 2,
    "wednesday": 3,
    "thursday": 4,
    "friday": 5,
    "saturday": 6,
    "sunday": 7,
}

CREATE_TABLE = '''
CREATE TABLE IF NOT EXISTS onlineplot(
  record_date DATETIME NOT NULL,
  record_time_index UNSIGNED TINYINT(3) NOT NULL,
  guild_id UNSIGNED BIGINT(18) NOT NULL,
  online UNSIGNED INT(11) NOT NULL,
  idle UNSIGNED INT(11) NOT NULL,
  dnd UNSIGNED INT(11) NOT NULL,
  offline UNSIGNED INT(11) NOT NULL,
  PRIMARY KEY (record_date, guild_id)
)
'''

CREATE_INDEX = '''
CREATE INDEX IF NOT EXISTS idx_record_time_index_guild_id
ON onlineplot(record_time_index, guild_id)
'''

GET_AVERAGES = '''
SELECT record_time_index, AVG(online), AVG(idle), AVG(dnd), AVG(offline)
FROM onlineplot
WHERE guild_id = ?
  AND strftime('%w', DATETIME(record_date || ?)) = ?
GROUP BY record_time_index
'''

DELETE_OLD = '''
DELETE FROM onlineplot WHERE DATE(record_date, "+57 days") < DATE('now')
'''

DELETE_GUILD = '''
DELETE FROM onlineplot WHERE guild_id = ?
'''

def _data_file(file_name: str) -> str:
    return os.path.join(str(data_manager.cog_data_path(raw_name='OnlinePlot')), file_name)


class OnlinePlot(commands.Cog):
    """Get online analytics"""

    def __init__(self, bot, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot

        self.db_path = _data_file('log.db')
        self.lock = asyncio.Event()
        self.pool: Optional[Pool] = None

        self.config = Config.get_conf(self, identifier=771739707)
        self.config.register_guild(opted_in=False)

        self._loop = bot.loop.create_task(self.do_loop())

    async def red_get_data_for_user(self, *, user_id):
        """Get a user's personal data."""
        data = "No data is stored for user with ID {}.\n".format(user_id)
        return {"user_data.txt": BytesIO(data.encode())}

    async def red_delete_data_for_user(self, *, requester, user_id):
        """Delete a user's personal data.

        No personal data is stored in this cog.
        """
        return

    def cog_unload(self):
        logger.info('OnlinePlot: unloading')
        self._loop.cancel()
        self.lock.clear()
        if self.pool:
            self.pool.close()
            self.bot.loop.create_task(self.pool.wait_closed())
            self.pool = None
        else:
            logger.error('unexpected error: pool was None')
        logger.info('OnlinePlot: unloading complete')

    async def init(self):
        logger.info('OnlinePlot: init')
        if os.name != 'nt' and sys.platform != 'win32':
            dsn = 'Driver=SQLite3;Database=' + self.db_path
        else:
            dsn = 'Driver=SQLite3 ODBC Driver;Database=' + self.db_path
        self.pool = await aioodbc.create_pool(dsn=dsn, autocommit=True)
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(CREATE_TABLE)
                await cur.execute(CREATE_INDEX)
        self.lock.set()

        logger.info('OnlinePlot: init complete')

    @commands.group()
    async def onlineplot(self, ctx):
        """Online plot"""

    @onlineplot.command()
    async def optin(self, ctx):
        """Opt in to onlineplot tracking"""
        await self.config.guild(ctx.guild).opted_in.set(True)
        await ctx.tick()

    @onlineplot.command()
    async def optout(self, ctx):
        """Opt out of onlineplot tracking"""
        m = await ctx.send("Are you sure you want to opt out of onlineplot and delete all"
                           " data associated with this guild?  Type 'Delete all my data'"
                           " to continue.")
        try:
            msg = await self.bot.wait_for('message', timeout=10.0,
                                          check=lambda m: m.channel == ctx.channel
                                                          and m.content == "Delete all my data")
        except asyncio.TimeoutError:
            await ctx.react_quietly("\N{CROSS MARK}")
            return
        await self.execute_query(DELETE_GUILD, (ctx.guild.id,))
        await self.config.guild(ctx.guild).opted_in.set(False)
        await ctx.tick()

    @onlineplot.command()
    async def plot(self, ctx, day_of_week: str = None):
        """Generate a graph of online presence in this server."""
        await self.lock.wait()

        if day_of_week is None:
            day = datetime.now().isoweekday()
        else:
            if day_of_week.lower() not in WEEKDAYS:
                await ctx.send("Invalid weekday.  Must be one of: " + ', '.join(WEEKDAYS))
                return
            day = WEEKDAYS[day_of_week.lower()]

        tz = await self.bot.get_cog("TimeCog").get_user_timezone(ctx.author)
        if tz is None:
            await ctx.send(f"Please set your timzeone with {ctx.prefix}settimezone")
            return

        data = await self.fetch_guild_data(ctx.guild, day, tz)

        times = [row[0] for row in data]
        online = [row[1] for row in data]
        idle = [row[2] for row in data]
        dnd = [row[3] for row in data]
        offline = [row[4] for row in data]

        await ctx.send(file=self.make_graph(times, online, idle, dnd, colors=('g', 'y', 'r')))

    def make_graph(self, x_vals: Sequence, *y_vals: Sequence, **kwargs) -> discord.File:
        fig = plt.figure(facecolor="#190432")
        sp = fig.add_subplot()
        sp.set_xlabel('Time')
        sp.set_ylabel('# of users')
        sp.set_facecolor("#190432")
        sp.xaxis.label.set_color('#DFCDF6')
        sp.yaxis.label.set_color('#DFCDF6')
        sp.tick_params(axis='x', colors='#DFCDF6')
        sp.tick_params(axis='y', colors='#DFCDF6')
        sp.spines['top'].set_color('#DFCDF6')
        sp.spines['left'].set_color('#DFCDF6')
        sp.spines['bottom'].set_color('#DFCDF6')
        sp.spines['right'].set_color('#DFCDF6')
        plt.stackplot(x_vals, *y_vals, **kwargs)
        plt.title("Users Online", color="#DFCDF6")
        fig.autofmt_xdate()

        buf = BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)

        return discord.File(buf, "image.png")

    async def fetch_guild_data(self, guild: discord.Guild, weekday: int, tz: DstTzInfo) \
            -> List[Tuple[datetime, int, int, int, int]]:
        # SQLite has a shitty TZ format
        now = datetime.now(tz)
        curtz = now.tzinfo  # noqa

        # Convert a tz object to an SQL tz string.  This is so awful.  I'm so sorry.
        # A SQL tz string matches /[-+]\d\d:\d\d/
        tzstr = re.sub(r'^([-+]\d\d)', r'\1:', "{:+05}".format(-int(datetime.now(tz).strftime("%z"))))

        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(GET_AVERAGES, (guild.id, tzstr, str(weekday)))
                rows = [[int(v) for v in row] for row in await cur.fetchall()]

        o = []
        for row in rows:
            mins = int((10 * row[0] + curtz._utcoffset.total_seconds() // 60) % (24 * 60))
            dt = datetime.combine(now.date(), time(mins // 60, mins % 60))
            o.append((dt, row[1], row[2], row[3], row[4]))
        return sorted(o, key=lambda x: x[0])

    async def insert_guild(self, guild: discord.Guild) -> None:
        stmt = '''INSERT INTO onlineplot(record_date, record_time_index, guild_id, online, idle, dnd, offline)
                  VALUES(DATETIME('now'), ?, ?, ?, ?, ?, ?)'''
        record_date = datetime.utcnow()
        record_time_index = (record_date.time().hour * 60 + record_date.time().minute) // 10
        guild_id = guild.id
        online, idle, dnd, offline = self.get_onilne_stats(guild)
        values = (record_time_index, guild_id, online, idle, dnd, offline)

        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(stmt, values)

    async def delete_old(self):
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(DELETE_OLD, ())

    @staticmethod
    def get_onilne_stats(guild: discord.Guild) -> Tuple[int, int, int, int]:
        online = idle = dnd = offline = 0

        for member in guild.members:
            if member.status is discord.Status.online:
                online += 1
            elif member.status is discord.Status.idle:
                idle += 1
            elif member.status is discord.Status.dnd:
                dnd += 1
            elif member.status is discord.Status.offline:
                offline += 1
            else:
                raise ValueError(f"Unknown status: {member.status}")

        return online, idle, dnd, offline

    async def restart_loop(self):
        while True:
            try:
                await asyncio.sleep(60 * 60)
                if self._loop.done():
                    logger.info("Refreshing OnlinePlot loop...")
                    e = self._loop.exception()
                    if e:
                        logger.error("Exception in OnlinePlot loop: {!r}".format(e))
                    self._loop = self.bot.loop.create_task(self.do_loop())
            except Exception:
                pass

    async def do_loop(self):
        try:
            await self.bot.wait_until_ready()
            await self.lock.wait()
            while True:
                for guild in self.bot.guilds:
                    if await self.config.guild(guild).opted_in():
                        await self.insert_guild(guild)
                await self.delete_old()
                await asyncio.sleep(10 * 60)
        except asyncio.CancelledError as e:
            logger.info("Task Cancelled.")
        except Exception as e:
            logger.exception("Task failed.")
