import logging
from abc import ABCMeta, abstractmethod
from typing import Optional, TYPE_CHECKING

from redbot.core.bot import Red

if TYPE_CHECKING:
    from . import MenuListener

logger = logging.getLogger('red.misc-cogs.menulistener')


class MenuABC(metaclass=ABCMeta):
    bot: Red

    async def register_menu(self):
        await self.bot.wait_until_ready()
        menucog: Optional[MenuListener] = self.bot.get_cog("MenuCog")
        if menucog is None:
            logger.warning("MenuCog is not loaded.")
            return
        await menucog.register(self)

    @property
    @abstractmethod
    def menu_map(self):
        ...

    @abstractmethod
    def get_menu_default_data(self, ims):
        ...
