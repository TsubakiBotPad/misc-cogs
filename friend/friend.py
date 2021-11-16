import logging
from io import BytesIO

import discord
from redbot.core import Config, commands
from redbot.core.utils.chat_formatting import box, pagify

logger = logging.getLogger('red.misc-cogs.friend')


class Friend(commands.Cog):
    """A friendly cog for friend related commands"""

    def __init__(self, bot, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot

        self.config = Config.get_conf(self, identifier=721370)
        self.config.register_user(friends=[])

    async def red_get_data_for_user(self, *, user_id):
        """Get a user's personal data."""
        udata = await self.config.user_from_id(user_id).friends()

        data = "You have {} friends stored with IDs: {}.\n".format(len(udata), ', '.join(map(str, udata)))

        if not udata:
            data = "No data is stored for user with ID {}.\n".format(user_id)

        return {"user_data.txt": BytesIO(data.encode())}

    async def red_delete_data_for_user(self, *, requester, user_id):
        """Delete a user's personal data."""
        await self.config.user_from_id(user_id).clear()

    @commands.group()
    async def menufriend(self, ctx):
        """Global Admin Commands"""

    @menufriend.command(name="add")
    async def mf_add(self, ctx, friend: discord.User):
        async with self.config.user(ctx.author).friends() as friends:
            if friend.id in friends:
                await ctx.send("This user is already added as a friend.")
                return
            friends.append(friend.id)
        await ctx.tick()

    @menufriend.command(name="remove", aliases=["rm", "delete"])
    async def mf_remove(self, ctx, friend: discord.User):
        async with self.config.user(ctx.author).friends() as friends:
            if friend.id not in friends:
                await ctx.send("This user is not added as a friend.")
                return
            friends.remove(friend.id)
        await ctx.tick()

    @menufriend.command(name="list")
    async def mf_list(self, ctx):
        friends = await self.config.user(ctx.author).friends()
        o = [u for u in (self.bot.get_user(uid) for uid in friends) if u]
        if not o:
            await ctx.send("You don't have any added friends.")
            return
        for page in pagify("\n".join(map(str, o))):
            await ctx.send(box(page))

    async def is_friend(self, author_id: int, user_id: int):
        # noinspection PyTypeChecker
        return user_id in await self.get_friends(author_id)

    async def get_friends(self, author_id: int):
        # noinspection PyTypeChecker
        return await self.config.user(discord.Object(author_id)).friends()
