from anvil import *

from ._anvil_designer import EventRowTemplate
from ... import router, state


class EventRow(EventRowTemplate):
    """A line of a timeline (the deck's live feed, a card's activity). item = an event dict; item["long"] = the card
    page's style (full date and kind, no card link)."""

    def __init__(self, **properties):
        super().__init__(**properties)
        e = self.item
        who = e["who"]
        self.who.person = None if who.get("kind") == "system" else who
        kind = e["kind"]
        self.classes.update({"agent": who.get("kind") == "agent", "submit": kind == "submit"})
        if kind == "comment":
            self.author.text = who["name"] + ": "
        elif kind in ("agent_log", "submit"):
            self.author.text = who["name"] + (" handed in: " if kind == "submit" else " logged: ")
        else:
            self.author.visible = False
        if e.get("long"):
            self.when.text = "%s · %s" % (state.date_time(e["created"]), kind.replace("_", " "))
            self.card_link.visible = False
        else:
            self.when.text = state.ago(e["created"]) + (" · " if e.get("card") else "")
            self.card_link.visible = bool(e.get("card"))
            if e.get("card"):
                self.card_key.text = e["card"]["key"]
                state.set_attr(self.card_link, "href", router.href("card", e["card"]["key"]))
