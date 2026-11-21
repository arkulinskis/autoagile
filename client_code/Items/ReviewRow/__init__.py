from anvil import *

from ._anvil_designer import ReviewRowTemplate
from ... import aa, router, state

LEVEL = ["good", "", "warn", "bad"]


class ReviewRow(ReviewRowTemplate):
    """A review packet in the review lane: key, wait, who handed it in and its note, acceptance x/y, the scope/risk/verify
    gate answers, links (PR), the last send-back reason, and Approve / Send back / Open.
    item = packet from Cards.packet + host (the Review page) + i + on (selected by the keyboard)."""

    def __init__(self, **properties):
        super().__init__(**properties)
        p = self.item
        c = p["card"]
        self.classes["on"] = bool(p.get("on"))
        self.key.text = c["key"]
        state.set_attr(self.key_link, "href", router.href("card", c["key"]))
        self.type_tag.text = c["type"]
        self.pts.text = ("%s PT" % c["points"]) if c["points"] is not None else "?"
        h = p.get("wait") or 0
        self.wait.text = "waiting " + aa.hours_text(h)
        self.wait.role = ["rv-wait", "bad" if h >= 24 else "warn" if h >= 4 else "ok"]
        self.pick.text = c["title"]
        state.set_control_attr(self.pick, "aria-pressed", "true" if p.get("on") else "false")
        by = p.get("by")
        self.who.person = by
        self.by.text = "%s handed it in %s" % (by["name"] if by else "Someone", state.ago(p.get("submitted")))
        n = p.get("sent_back") or 0
        self.backs.visible = bool(n)
        self.backs.text = "sent back %s" % ("once" if n == 1 else "%d times" % n)
        self.summary.content = p.get("summary") or ""
        self.summary_box.visible = bool(p.get("summary"))
        self.no_summary.visible = not p.get("summary")
        if c["acc_total"]:
            self.acc.text = "criteria %d/%d" % (c["acc_done"], c["acc_total"])
            self.acc.role = ["rv-fact", "good" if c["acc_done"] == c["acc_total"] else "warn"]
        else:
            self.acc.text = "no criteria"
            self.acc.role = ["rv-fact", "warn"]
        self.facts_panel.items = [{"text": "%s: %s" % (f["name"], f["text"]), "cls": LEVEL[f["level"]]} for f in p.get("facts") or []]
        links = c.get("links") or []
        self.links_panel.items = [dict(x, i=i) for i, x in enumerate(links)]
        self.links_panel.visible = bool(links)
        fb = p.get("last_feedback")
        self.fb_box.visible = bool(fb)
        if fb:
            self.fb_head.text = "Last sent back by %s" % fb["who"]
            self.fb_text.text = fb["reason"]
        state.set_control_attr(self.approve, "aria-label", "Approve %s" % c["key"])
        state.set_control_attr(self.send_back, "aria-label", "Send %s back" % c["key"])

    @handle("pick", "click")
    def pick_click(self, **event_args):
        self.item["host"].pick(self.item["i"])

    @handle("approve", "click")
    def approve_click(self, **event_args):
        self.item["host"].approve(self.item["i"])

    @handle("send_back", "click")
    def send_back_click(self, **event_args):
        self.item["host"].send_back(self.item["i"])

    @handle("open", "click")
    def open_click(self, **event_args):
        self.item["host"].open(self.item["i"])
