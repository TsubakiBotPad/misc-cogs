import asyncio
import os
import sys
from collections import deque
from datetime import datetime, time
from io import BytesIO
import logging
from typing import Tuple, Sequence, List, Optional

import aioodbc
import discord
from aioodbc import Pool
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
WHERE guild_id = ? AND DATENAME(wd, DATETIME(record_date || ?)) = DATENAME(wd, DATETIME(now || ?))
GROUP BY record_time_index
'''

DELETE_OLD = '''
DELETE FROM onlineplot WHERE DATEADD(day, 57, record_date) < getdate()
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
    async def optin(self, ctx, enable: bool = True):
        """Opt in to onlineplot tracking"""
        await self.config.guild(ctx.guild).opted_in.set(enable)
        await ctx.tick()

    @onlineplot.command()
    async def optout(self, ctx, disable: bool = True):
        """Opt out of onlineplot tracking"""
        await self.config.guild(ctx.guild).opted_in.set(not disable)
        await ctx.tick()

    @onlineplot.command()
    async def plot(self, ctx, day_of_week: str = None):
        """Generate a graph of online presence in this server."""
        if day_of_week is None:
            day = datetime.now().isoweekday()
        else:
            if day_of_week.lower() not in WEEKDAYS:
                await ctx.send("Invalid weekday.  Must be one of: " + ', '.join(WEEKDAYS))
                return
            day = WEEKDAYS[day_of_week.lower()]

        await ctx.send(file=self.make_graph([1, 2], [2, 4], [3, 5], colors=['r', 'w']))

    def make_graph(self, x_vals: Sequence, *y_vals: Sequence, **kwargs) -> discord.File:
        fig = plt.figure(facecolor="#190432")
        sp = fig.add_subplot()
        sp.set_xlabel('X-axis ')
        sp.set_ylabel('Y-axis ')
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
        fig.autofmt_xdate()
        plt.title("Online plot (Averaged over 8 weeks)", color="#DFCDF6")

        buf = BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)

        return discord.File(buf, "image.png")

    async def fetch_guild_data(self, guild: discord.Guild) -> List[Tuple[time, int, int, int, int]]:
        pass

    async def insert_guild(self, guild: discord.Guild) -> None:
        stmt = '''INSERT INTO onlineplot(record_date, record_time_index, guild_id, online, idle, dnd, offline)
                  VALUES(?, ?, ?, ?, ?, ?, ?)'''
        record_date = datetime.utcnow()
        record_time_index = (record_date.time().hour * 60 + record_date.time().minute) // 10
        guild_id = guild.id
        online, idle, dnd, offline = self.get_onilne_stats(guild)
        values = (record_date, record_time_index, guild_id, online, idle, dnd, offline)

        print(values)
        print(0)
        async with self.pool.acquire() as conn:
            print(.2)
            async with conn.cursor() as cur:
                print(.5)
                await cur.execute(stmt, values)
                print(1)
                rows = await cur.fetchall()
                print(2)
                print(rows)
                print(3)

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
                await asyncio.sleep(10 * 60)
        except asyncio.CancelledError:
            logger.info("Task Cancelled.")
            pass
