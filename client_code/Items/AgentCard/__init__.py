from anvil import *

from ._anvil_designer import AgentCardTemplate
from ... import aa, state

LED = {"working": ["on", "blink"], "waiting": ["warn"], "idle": [], "paused": ["bad"]}


class AgentCard(AgentCardTemplate):
    """An agent on the Agents page: state, Doing / Review / Done, current cards, token hint, actions.
    item = an agent dict. Raises x-agent(action, agent_id) on the panel."""

    def __init__(self, **properties):
        super().__init__(**properties)
        a = self.item
        self.classes["warn"] = not a["active"]
        self.kind_title.text = a["kind"]
        self.state_extra.text = a["state"]
        self.who.person = {"kind": "agent", "name": a["name"], "color": a["color"]}
        for c in LED.get(a["state"], []):
            self.led.classes.add(c)
        self.seen.text = a["state"] + (" · seen " + state.ago(a["last_seen"]) if a.get("last_seen") else " · never connected")
        self.stats_panel.items = [{"value": a["wip"], "unit": "/%d" % a["max_wip"], "label": "Doing"},
                                  {"value": a["in_review"], "label": "Review", "cls": "amber"},
                                  {"value": a["done"], "label": "Done", "cls": "cyan"}]
        tr = a.get("trust") or {}
        fp = tr.get("first_pass")
        self.trust_panel.items = [
            {"value": "--" if fp is None else fp, "unit": "" if fp is None else "%", "label": "Approved first time",
             "cls": "" if fp is None or fp >= 80 else "amber" if fp >= 50 else "red"},
            {"value": tr.get("sent_back") or 0, "label": "Sent back", "cls": "pink"},
            {"value": aa.hours_text(tr.get("wait")), "label": "Review wait", "cls": "cyan"}]
        self.cur_panel.items = [{"card": {"key": c["key"]}, "text": "%s (%s)" % (c["title"], c["status"]), "plain": True} for c in a["current"]]
        self.no_card.visible = not a["current"]
        self.tok.text = ("Token …" + a["token_hint"]) if a["has_token"] else "No token yet (demo agents run from the console)"
        self.toggle.text = "Pause" if a["active"] else "Resume"
        self.toggle.role = ["btn", "btn-sm", "ic-pause" if a["active"] else "ic-play"]
        self.token.text = "New token" if a["has_token"] else "Get token"
        self.edit.text = "Edit " + a["name"]

    def _send(self, action):
        self.parent.raise_event("x-agent", action=action, agent_id=self.item["id"])

    @handle("toggle", "click")
    def toggle_click(self, **event_args):
        self._send("toggle")

    @handle("token", "click")
    def token_click(self, **event_args):
        self._send("token")

    @handle("use", "click")
    def use_click(self, **event_args):
        self._send("use")

    @handle("edit", "click")
    def edit_click(self, **event_args):
        self._send("edit")
