import discord
from discordmenu.embed.components import EmbedMain, EmbedAuthor, EmbedFooter
from discordmenu.embed.view import EmbedView
from discordmenu.intra_message_state import IntraMessageState
from tsutils.menu.view.closable_embed import ClosableEmbedViewState


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
