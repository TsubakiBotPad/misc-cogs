import logging
from copy import deepcopy
from io import BytesIO
from typing import Any, Mapping, Tuple, Union, TYPE_CHECKING

import discord

from menulistener.errors import CogNotLoaded, MissingImsMenuType, InvalidImsMenuType
from menulistener.menuabc import MenuABC
from discordmenu.embed.emoji import EmbedMenuEmojiConfig
from discordmenu.intra_message_state import IntraMessageState
from discordmenu.reaction_filter import ValidEmojiReactionFilter, BotAuthoredMessageReactionFilter, \
    MessageOwnerReactionFilter, FriendReactionFilter, NotPosterEmojiReactionFilter
from redbot.core import Config, commands, checks
from redbot.core.utils.chat_formatting import box, pagify

logger = logging.getLogger('red.misc-cogs.menulistener')

if TYPE_CHECKING:
    from padinfo.menu.common import MenuPanes


class MenuListener(commands.Cog):
    """A cog to listen for menus across cogs"""

    def __init__(self, bot, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot

        self.config = Config.get_conf(self, identifier=7377709)
        self.config.register_global(cogs=[])

        self.menu_map = {}  # type: Mapping[str, Tuple[str, Any, MenuPanes]]
        self.completed = False

    async def red_get_data_for_user(self, *, user_id):
        """Get a user's personal data."""
        data = "No data is stored for user with ID {}.\n".format(user_id)
        return {"user_data.txt": BytesIO(data.encode())}

    async def red_delete_data_for_user(self, *, requester, user_id):
        """Delete a user's personal data."""
        await self.config.user_from_id(user_id).clear()

    @commands.group()
    async def menulistener(self, ctx):
        """Global Admin Commands"""

    @menulistener.command(name="list")
    async def mc_list(self, ctx):
        """List all cogs that listen to menus"""
        cogs = await self.config.cogs()
        if not cogs:
            await ctx.send("There are no registered cogs.")
            return
        for page in pagify(", ".join(map(str, cogs))):
            await ctx.send(box(page))

    @checks.is_owner()
    @menulistener.command()
    async def unregister(self, ctx, cog_name):
        """Unregister a cog from the menu listener"""
        async with self.config.cogs() as cogs:
            if cog_name not in cogs:
                await ctx.send("Cog not registered.")
            cogs.remove(cog_name)
        await ctx.tick()

    @commands.Cog.listener('on_reaction_add')
    async def test_reaction_add(self, reaction, member):
        emoji_clicked = self.get_emoji_clicked(reaction)
        if emoji_clicked is None:
            return

        message = reaction.message
        ims = message.embeds and IntraMessageState.extract_data(message.embeds[0])
        if not ims:
            return
        cog_name, menu, panes = self.get_menu_attributes(ims)
        if not (await menu.should_respond(message, reaction, await self.get_reaction_filters(ims), member)):
            return

        try:
            data = await self.get_menu_default_data(ims)
        except CogNotLoaded:
            return

        data.update({
            'reaction': emoji_clicked
        })

        await menu.transition(message, deepcopy(ims), emoji_clicked, member, **data)
        await self.listener_respond_with_child(deepcopy(ims), message, emoji_clicked, member)

    def get_emoji_clicked(self, reaction):
        emoji_obj = reaction.emoji
        if isinstance(emoji_obj, str):
            emoji_clicked = emoji_obj
        else:
            emoji_clicked = emoji_obj.name

        # determine if this is potentially a valid reaction prior to doing any network call:
        # this is true if it's a default emoji or in any of our global panes emoji lists
        if emoji_clicked in EmbedMenuEmojiConfig().to_list():
            return emoji_clicked
        for menu_type, classes in self.menu_map.items():
            if emoji_clicked in classes[2].emoji_names():
                return emoji_clicked
        return None

    async def listener_respond_with_child(self, menu_1_ims, message_1, emoji_clicked, member):
        failsafe = 0
        pdicog = self.bot.get_cog("PadInfo")  # TODO: Oh god don't do this please support multiple menus eventually
        if pdicog is None:
            return

        while menu_1_ims.get('child_message_id'):
            # before this loop can actually work as a loop, the type of menu_2 can't be hard-coded as IdMenu anymore,
            # and we have to update menu_1_class to be menu_2_class during the loop.
            if failsafe == 10:
                break
            failsafe += 1
            menu_2 = pdicog.id_menu.menu()
            panes_class = self.menu_map[menu_1_ims['menu_type']][2]
            child_data_func = panes_class.get_child_data_func(emoji_clicked)
            try:
                data = await self.get_menu_default_data(menu_1_ims)
            except CogNotLoaded:
                return
            emoji_simulated_clicked_2, extra_ims = None, {}
            if child_data_func is not None:
                emoji_simulated_clicked_2, extra_ims = child_data_func(menu_1_ims, emoji_clicked, **data)
            if emoji_simulated_clicked_2 is not None:
                fctx = await self.bot.get_context(message_1)
                try:
                    message_2 = await fctx.fetch_message(int(menu_1_ims['child_message_id']))
                    menu_2_ims = message_2.embeds and IntraMessageState.extract_data(message_2.embeds[0])
                    menu_2_ims.update(extra_ims)
                    await menu_2.transition(message_2, menu_2_ims, emoji_simulated_clicked_2, member, **data)
                except discord.errors.NotFound:
                    break
                menu_1_ims = menu_2_ims
                message_1 = message_2

    async def get_reaction_filters(self, ims):
        original_author_id = ims['original_author_id']
        friend_cog = self.bot.get_cog("Friend")
        friend_ids = (await friend_cog.get_friends(original_author_id)) if friend_cog else []
        reaction_filters = [
            ValidEmojiReactionFilter(self.get_menu_attributes(ims)[2].emoji_names()),
            NotPosterEmojiReactionFilter(),
            BotAuthoredMessageReactionFilter(self.bot.user.id),
            MessageOwnerReactionFilter(original_author_id, FriendReactionFilter(original_author_id, friend_ids))
        ]
        return reaction_filters

    async def get_menu_default_data(self, ims):
        cog_name, menu, panes = self.get_menu_attributes(ims)
        cog = self.bot.get_cog(cog_name)
        if cog is None:
            raise CogNotLoaded(f"Cog {cog_name} is unloaded.")
        if hasattr(cog, "get_menu_default_data"):
            return await cog.get_menu_default_data(ims)
        return {}

    async def register(self, cog: Union[commands.Cog, MenuABC]):
        async with self.config.cogs() as cogs:
            if cog.__class__.__name__ not in cogs:
                cogs.append(cog.__class__.__name__)
            self.completed = False
        await self.reload()

    async def reload(self):
        if self.completed:
            return

        await self.bot.wait_until_ready()

        self.menu_map = {}
        self.completed = True
        for cog_name in await self.config.cogs():
            cog = self.bot.get_cog(cog_name)
            if not cog:
                self.completed = False
                continue
            self.menu_map.update({k: (cog_name,) + v for k, v in cog.menu_map.items()})

    def get_menu_attributes(self, ims):
        menu_type = ims.get('menu_type')
        if menu_type is None:
            raise MissingImsMenuType("Missing IMS menu type")
        if menu_type not in self.menu_map:
            raise InvalidImsMenuType(f"Invalid IMS menu type: {menu_type}")
        cog_name, menu, panes = self.menu_map[menu_type]
        return cog_name, menu.menu(), panes
