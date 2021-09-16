import logging
import pickle
from io import BytesIO

from redbot.core import Config, commands
from redbot.core.bot import Red
from redbot.core.commands import Context

from userpreferences.preferences.timezone import TimezonePreference
from userpreferences.preferences.tsutils import TSUtilsPreference

logger = logging.getLogger('red.misc-cogs.userpreferences')


class UserPreferences(TimezonePreference, TSUtilsPreference):
    """Stores user preferences for users."""

    def __init__(self, bot: Red, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot

        self.config = Config.get_conf(self, identifier=75321770)

        self.setup_mixins()

    async def red_get_data_for_user(self, *, user_id):
        """Get a user's personal data."""
        data = []

        if (tz := await self.config.user_by_id(user_id).timezone()) is not None:
            data.append(f"Timezone: `{pickle.loads(tz)}`")

        data = '\n'.join(await self.get_mixin_user_data(user_id))
        if not data:
            data = "No data is stored for user with ID {}.\n".format(user_id)
        return {"user_data.txt": BytesIO(data.encode())}

    async def red_delete_data_for_user(self, *, requester, user_id):
        """Delete a user's personal data."""
        await self.delete_mixin_user_data(requester, user_id)

    @commands.group(aliases=['preference', 'prefs', 'pref'])
    async def preferences(self, ctx: Context):
        """Set user preferences"""
