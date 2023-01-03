from tsutils.menu.closable_embed_base import ClosableEmbedMenuBase

from linklistener.view.link_listener_view import LinkListenerView


class ClosableEmbedMenu(ClosableEmbedMenuBase):
    view_types = {
        LinkListenerView.VIEW_TYPE: LinkListenerView
    }
