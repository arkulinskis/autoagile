from anvil import *

from ._anvil_designer import CheckRowTemplate


class CheckRow(CheckRowTemplate):
    """One level check: what it measures, the crew's number and the target. item = a check from Metrics.maturity."""

    def __init__(self, **properties):
        super().__init__(**properties)
        c = self.item
        self.classes.add("ok" if c["ok"] else "no")
        self.led.classes.add("on" if c["ok"] else "bad")
        self.shown.text = str(c["shown"])
        self.need.text = "need 0" if c["id"] in ("wip", "stale") else "need %s" % c["target"]
