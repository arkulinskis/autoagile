from anvil import *

from ._anvil_designer import AgentRowTemplate

LED = {"working": ["on", "blink"], "waiting": ["warn"], "idle": [], "paused": ["bad"]}


class AgentRow(AgentRowTemplate):
    """An agent on the deck: what it is doing now. item = an agent dict."""

    def __init__(self, **properties):
        super().__init__(**properties)
        a = self.item
        self.who.person = {"kind": "agent", "name": a["name"], "color": a["color"]}
        self.aname.text = "%s  · %s" % (a["name"], a["kind"])
        if a["current"]:
            self.cur.text = " · ".join("%s %s" % (c["key"], c["title"]) for c in a["current"])
        else:
            self.cur.text = "Paused by the crew" if a["state"] == "paused" else "Waiting for a Ready card"
        for c in LED.get(a["state"], []):
            self.led.classes.add(c)
