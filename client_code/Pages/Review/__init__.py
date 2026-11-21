from anvil import *
import anvil.js
from anvil.js import window

from ._anvil_designer import ReviewTemplate
from ... import aa, router, state


hours_text = aa.hours_text


class Review(ReviewTemplate):
    """#review, the review lane: every card in Review as a packet (hand-in note, links, acceptance, risk/verify gates,
    wait), oldest first. Approve, or send back with a reason the agent reads in its brief. Keys: j/k, a, s, o."""

    def __init__(self, args=(), **properties):
        super().__init__(**properties)
        self.sel = 0
        self.packets = []
        self._keys = anvil.js.report_exceptions(self._key)
        self.crew = aa.need_crew(self)
        if not self.crew:
            return
        window.document.addEventListener("keydown", self._keys)
        self._load()

    def leave(self):
        window.document.removeEventListener("keydown", self._keys)

    def _load(self):
        d = state.call("get_review", self.crew["id"])
        if not d:
            return
        s = d["stats"]
        self.packets = d["packets"]
        self.sel = min(self.sel, max(0, len(self.packets) - 1))
        self.sub.text = "%s // Approve or send back with a reason. Agents read your notes before they try again." % d["crew"]["key"]
        self.demo_note.visible = bool(d["crew"]["demo"])
        oldest = s.get("oldest")
        self.kpi_panel.items = [
            {"value": s["in_review"], "label": "Waiting now", "cls": "amber" if s["in_review"] else ""},
            {"value": hours_text(oldest), "label": "Oldest wait", "cls": "red" if (oldest or 0) >= 24 else "pink"},
            {"value": hours_text(s.get("wait")), "label": "Median review wait (%dd)" % s["days"], "cls": "cyan"},
            {"value": "--" if s.get("first_pass") is None else s["first_pass"], "unit": "" if s.get("first_pass") is None else "%",
             "label": "Approved first time", "cls": ""},
            {"value": s["sent_back"], "label": "Sent back (%dd)" % s["days"], "cls": "pink"}]
        self.lane_extra.text = state.plural(len(self.packets), "card")
        self.lane_win.classes["warn"] = (oldest or 0) >= 24
        self._draw()

    def _draw(self):
        self.lane_panel.items = [dict(p, host=self, i=i, on=(i == self.sel)) for i, p in enumerate(self.packets)]
        self.lane_empty.visible = not self.packets

    def pick(self, i):
        self.sel = i
        self._draw()

    def approve(self, i):
        p = self.packets[i]
        r = state.call("review_card", p["card"]["id"], "approve", "")
        if r:
            state.toast(r.get("message") or "Approved", "ok")
            if len(self.packets) == 1:
                aa.rave("REVIEW ZERO", "nothing waiting for a human")
            self._load()

    def send_back(self, i):
        p = self.packets[i]
        from ...Dialogs.SendBack import SendBack
        r = alert(SendBack(card_id=p["card"]["id"], key=p["card"]["key"], title=p["card"]["title"]), buttons=[], role="app-dialog")
        if r:
            state.toast(r.get("message") or "Sent back", "ok")
            self._load()

    def open(self, i):
        router.go("card", self.packets[i]["card"]["key"])

    def _key(self, e):
        if not self.packets:
            return
        tag = str(getattr(e.target, "tagName", "") or "")
        if tag in ("INPUT", "TEXTAREA", "SELECT") or window.document.querySelector(".anvil-modal.in, .modal.in"):
            return
        if getattr(e, "ctrlKey", False) or getattr(e, "metaKey", False) or getattr(e, "altKey", False):
            return
        k = str(getattr(e, "key", "") or "").lower()
        now = window.Date.now()
        if k == "g":
            self._g = now  # the header's g-chords (g s = Crew settings) win over the lane's keys
            return
        if getattr(e, "defaultPrevented", False) or now - getattr(self, "_g", 0) < 900:
            return
        if k == "j":
            self.pick(min(len(self.packets) - 1, self.sel + 1))
        elif k == "k":
            self.pick(max(0, self.sel - 1))
        elif k == "a":
            self.approve(self.sel)
        elif k == "s":
            self.send_back(self.sel)
        elif k == "o":
            self.open(self.sel)
        else:
            return
        e.preventDefault()
