from anvil import *

from ._anvil_designer import BacklogRowTemplate
from ... import aa, router, state


class BacklogRow(BacklogRowTemplate):
    """A ranked backlog row. item = {c: card, i: position, planned: the first planned sprint or None}."""

    def __init__(self, **properties):
        super().__init__(**properties)
        c, planned = self.item["c"], self.item["planned"]
        self.rk.text = str(self.item["i"] + 1)
        self.ky.text = c["key"]
        self.title.text = ("⛔ " if c["blocked"] else "") + c["title"]
        state.set_attr(self.title_link, "href", router.href("card", c["key"]))
        self.type_tag.text = c["type"]
        self.type_tag.role = ["aa-type", "t-" + c["type"]]
        self.prio.visible = c["priority"] != 2
        self.prio.text = "P%s" % c["priority"]
        self.prio.role = ["aa-prio", "p%s" % c["priority"]]
        ep = c.get("epic")
        self.epic_dot.visible = self.epic.visible = bool(ep)
        if ep:
            self.epic_dot.style["background"] = ep["color"]
            self.epic.text = ep["title"]
        self.labels.visible = bool(c.get("labels"))
        self.labels.text = "  ".join(c.get("labels") or [])
        self.ready_badge.visible = c["status"] == "ready"
        self.pts.text = "?" if c["points"] is None else str(c["points"])
        self.pts.role = ["aa-pts", "none"] if c["points"] is None else ["aa-pts"]
        self.fit.visible = bool(c.get("fit"))
        if c.get("fit"):
            self.fit.text = ("⚡ " if c["fit"] == "solo" else "") + aa.FIT[c["fit"]]
            self.fit.role = ["aa-fit", "fit-" + c["fit"]]
        self.gate_button.visible = not c.get("fit") and c["points"] is None
        self.by_hand.visible = not c.get("fit") and c["points"] is not None
        self.ready.text = "%s/%s" % (c["ready"], c["ready_total"])
        self.who.person = c.get("assignee")
        self.to_sprint.visible = bool(planned)
        if planned:
            self.to_sprint.text = "Add to " + planned["name"]

    def _send(self, name, **kw):
        if self.parent is not None:
            self.parent.raise_event(name, card_id=self.item["c"]["id"], **kw)

    @handle("gate_button", "click")
    def gate_button_click(self, **event_args):
        self._send("x-gate")

    @handle("to_sprint", "click")
    def to_sprint_click(self, **event_args):
        self._send("x-tosprint", sprint_id=self.item["planned"]["id"])

    @handle("top_button", "click")
    def top_button_click(self, **event_args):
        self._send("x-rank", how="top")

    @handle("up_button", "click")
    def up_button_click(self, **event_args):
        self._send("x-rank", how="up")

    @handle("down_button", "click")
    def down_button_click(self, **event_args):
        self._send("x-rank", how="down")
