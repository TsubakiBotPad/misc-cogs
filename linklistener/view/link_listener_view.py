from discordmenu.embed.base import Box
from discordmenu.embed.components import EmbedMain, EmbedField, EmbedAuthor, EmbedFooter
from discordmenu.embed.text import Text
from discordmenu.embed.view import EmbedView
from discordmenu.emoji.emoji_cache import emoji_cache
from discordmenu.intra_message_state import IntraMessageState
from tsutils.menu.components.footers import embed_footer_with_state
from tsutils.menu.view.closable_embed import ClosableEmbedViewState
import discord


class LinkListenerViewProps:
    def __init__(self, name: str, jump_url: str, avatar, content, requester: discord.User):
        self.requester = requester
        self.content = content
        self.avatar = avatar
        self.jump_url = jump_url
        self.name = name


class LinkListenerView:
    VIEW_TYPE = "LinkListener"

    @staticmethod
    def embed(state: ClosableEmbedViewState, props: LinkListenerViewProps):
        footer_url = IntraMessageState.serialize(
            props.requester.avatar.url, state.serialize())

        return EmbedView(
            embed_main=EmbedMain(description=props.content),
            embed_author=EmbedAuthor(props.name, props.jump_url,
                                     props.avatar),
            embed_footer=EmbedFooter(
                f"Quoted by {props.requester}", icon_url=footer_url),
        )
