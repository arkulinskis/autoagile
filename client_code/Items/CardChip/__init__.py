from anvil import *

from ._anvil_designer import CardChipTemplate
from ... import aa, router, state


class CardChip(CardChipTemplate):
    """A card on the board, the backlog's sprint panels and the deck (was AA.card). It is a link to #card/KEY;
    on the board it is also draggable (item["drag"]). item = a card dict from the server."""

    def __init__(self, **properties):
        super().__init__(**properties)
        c = self.item
        agent = bool(c.get("assignee") and c["assignee"].get("kind") == "agent")
        state.set_attr(self, "href", router.href("card", c["key"]))
        state.set_attr(self, "data-id", c["id"])
        if c.get("drag"):
            state.set_attr(self, "draggable", "true")
        self.classes.update({"blocked": bool(c.get("blocked")), "agentcard": agent})
        style = ""
        if c.get("epic"):
            style += "--epic:%s;" % c["epic"]["color"]
        if agent:
            style += "--agent:%s;" % (c["assignee"].get("color") or "#00e5ff")
        state.set_attr(self, "style", style or None)
        self.type_tag.text = c["type"]
        self.type_tag.role = ["aa-type", "t-" + c["type"]]
        p = c.get("priority")
        self.prio.visible = p not in (2, None)
        self.prio.text = "P%s" % p
        self.prio.role = ["aa-prio", "p%s" % p]
        self.pts.text = "?" if c.get("points") is None else str(c["points"])
        self.pts.role = ["aa-pts", "none"] if c.get("points") is None else ["aa-pts"]
        self.title.text = ("⛔ " if c.get("blocked") else "") + c["title"]
        self.tagline.visible = bool(c.get("labels"))
        self.labels.text = "  ".join(c.get("labels") or [])
        self.who.person = c.get("assignee")
        self.acc.visible = bool(c.get("acc_total"))
        self.acc.text = "☑ %s/%s" % (c.get("acc_done"), c.get("acc_total"))
        self.rdy.visible = c.get("fit") == "solo" and bool(c.get("agent_ready")) and c["status"] != "done"
        if c["status"] in ("doing", "review") and c.get("age") is not None:
            self.age.text = aa.age_text(c["age"])
            cls = aa.age_class(c["age"])
            self.age.role = ["chip-age", cls] if cls else ["chip-age"]
        elif c["status"] == "done" and c.get("done_at"):
            self.age.text = state.ago(c["done_at"])
        else:
            self.age.visible = False
