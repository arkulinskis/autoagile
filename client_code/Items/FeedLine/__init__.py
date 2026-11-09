from anvil import *

from ._anvil_designer import FeedLineTemplate
from ... import router, state


class FeedLine(FeedLineTemplate):
    """One line of the agent feed (or an agent's current card when item["plain"]). item = event dict."""

    def __init__(self, **properties):
        super().__init__(**properties)
        e = self.item
        self.classes["plain"] = bool(e.get("plain"))
        self.who.visible = bool(e.get("who"))
        self.who.text = (e.get("who") or {}).get("name", "")
        self.card_link.visible = bool(e.get("card"))
        if e.get("card"):
            self.card_key.text = e["card"]["key"]
            state.set_attr(self.card_link, "href", router.href("card", e["card"]["key"]))
        self.when.visible = bool(e.get("created"))
        self.when.text = state.ago(e.get("created"))
