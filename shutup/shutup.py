import logging
from io import BytesIO

from redbot.core import commands

logger = logging.getLogger('misc-cogs.shutup')


class ShutUpFilter(logging.Filter):
    def filter(self, record):
        return not record.getMessage().startswith('We are being rate limited.')


class ShutUp(commands.Cog):
    def __init__(self, bot, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot

        self.filter = ShutUpFilter()
        self.httplogger = logging.getLogger('discord.http')

        self.httplogger.addFilter(self.filter)

    def cog_unload(self):
        self.httplogger.removeFilter(self.filter)

    async def red_get_data_for_user(self, *, user_id):
        """Get a user's personal data."""
        data = "No data is stored for user with ID {}.\n".format(user_id)
        return {"user_data.txt": BytesIO(data.encode())}

    async def red_delete_data_for_user(self, *, requester, user_id):
        """Delete a user's personal data.

        No personal data is stored in this cog.
        """
        return
