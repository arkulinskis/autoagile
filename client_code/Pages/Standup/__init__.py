from anvil import *
from anvil.js import window

from ._anvil_designer import StandupTemplate
from ... import aa, router, state


class Standup(StandupTemplate):
    """#standup: the standup that writes itself (Standup.get_standup): per person and agent what shipped, waits for
    review, is in progress (stuck after 3 days) or blocked, plus their latest note. Copy for Slack gives markdown.
    The public status link (#status/<code>, Pages/Status) is switched on and off here."""

    def __init__(self, args=(), **properties):
        super().__init__(**properties)
        self.days = 7 if (args and args[0] == "7") else 1
        self.d = None
        self.crew = aa.need_crew(self)
        if not self.crew:
            return
        self._load()

    def _load(self):
        d = state.call("get_standup", self.crew["id"], self.days)
        if not d:
            return
        self.d = d
        tt = d["totals"]
        self.sub.text = "%s // Written from the board %s. No meeting needed." % (
            d["crew"]["key"], "since the last workday" if d["days"] == 1 else "over the last 7 days")
        self.demo_note.visible = bool(d["crew"]["demo"])
        self.d1.role = ["seg", "on"] if d["days"] == 1 else ["seg"]
        self.d7.role = ["seg", "on"] if d["days"] == 7 else ["seg"]
        self.kpi_panel.items = [
            {"value": tt["shipped"], "label": "Shipped (%d pts)" % tt["points"]},
            {"value": tt["review"], "label": "Waiting for review", "cls": "amber"},
            {"value": tt["doing"], "label": "In progress", "cls": "cyan"},
            {"value": tt["stuck"], "label": "Stuck 3+ days", "cls": "red" if tt["stuck"] else "pink"},
            {"value": tt["blocked"], "label": "Blocked", "cls": "red" if tt["blocked"] else ""}]
        busy = [p for p in d["people"] if not p["quiet"]]
        quiet = [p for p in d["people"] if p["quiet"]]
        self.people_panel.items = busy + ([{"quiet_list": [p["who"]["name"] for p in quiet]}] if quiet else [])
        self.people_empty.visible = not busy
        self.orphan_win.visible = bool(d["unassigned"])
        self.orphan_panel.items = [{"key": x["key"], "text": x["title"], "sub": x["blocked_reason"], "cls": "bad"} for x in d["unassigned"]]
        self.preview.text = d["markdown"]
        self._link()

    def _link(self):
        code = self.d.get("status_code")
        self.link_on_box.visible = bool(code)
        self.on_link.visible = not code
        self.link_state.text = "on" if code else "off"
        demo = self.d["crew"]["demo"]
        self.new_link.visible = self.off_link.visible = not demo
        self.on_link.enabled = not demo
        if demo and not code:
            self.on_link.text = "Start your own crew to share a link"
        if code:
            loc = window.location
            self.link.text = loc.origin + loc.pathname + "#status/" + code
            state.set_attr(self.view_link, "href", router.href("status", code))

    def _set(self, on):
        r = state.call("status_link", self.crew["id"], on)
        if r is not None:
            self.d["status_code"] = r.get("code")
            self._link()
            state.toast("Status link is on. Share it with anyone." if r.get("code") else "Status link is off. The old link stops working.", "ok")

    @handle("d1", "click")
    def d1_click(self, **event_args):
        self.days = 1
        router.replace("standup")
        self._load()

    @handle("d7", "click")
    def d7_click(self, **event_args):
        self.days = 7
        router.replace("standup", "7")
        self._load()

    @handle("copy_button", "click")
    def copy_button_click(self, **event_args):
        if self.d:
            aa.copy(self.d["markdown"], "Standup copied. Paste it in your team chat.")

    @handle("copy_link", "click")
    def copy_link_click(self, **event_args):
        aa.copy(self.link.text)

    @handle("on_link", "click")
    def on_link_click(self, **event_args):
        self._set(True)

    @handle("new_link", "click")
    def new_link_click(self, **event_args):
        if confirm("The old link stops working. Share the new one.", title="Make a new status link?",
                   buttons=[("Cancel", False), ("New link", True)], role="app-dialog"):
            self._set(True)

    @handle("off_link", "click")
    def off_link_click(self, **event_args):
        if confirm("Anyone with the link loses access straight away.", title="Turn the status link off?",
                   buttons=[("Cancel", False), ("Turn off", True)], role="app-dialog"):
            self._set(False)
