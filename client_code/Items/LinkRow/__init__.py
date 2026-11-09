from anvil import *

from ._anvil_designer import LinkRowTemplate


class LinkRow(LinkRowTemplate):
    """A link on a card (opens in a new tab). item = {label, url, i}."""

    def __init__(self, **properties):
        super().__init__(**properties)
        self.link.text = self.item.get("label") or self.item["url"]
        self.link.url = self.item["url"]

    @handle("remove", "click")
    def remove_click(self, **event_args):
        self.parent.raise_event("x-remove", i=self.item["i"])
