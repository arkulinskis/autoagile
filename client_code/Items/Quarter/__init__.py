from anvil import *

from ._anvil_designer import QuarterTemplate


class Quarter(QuarterTemplate):
    """A quarter of the year roadmap: capacity against booked epics. item = quarter + qi + host."""

    def __init__(self, **properties):
        super().__init__(**properties)
        q = self.item
        self.classes["over"] = bool(q.get("over"))
        self.qlabel.text = q["label"] + (" · NOW" if q["qi"] == 0 else "")
        self.cap.text = "%s / %s pts%s" % (q["load"], q["capacity"][1], " OVERBOOKED" if q.get("over") else "")
        pct = min(100, 100.0 * q["load"] / q["capacity"][1]) if q["capacity"][1] else 0
        self.load.style["width"] = "%d%%" % pct
        self.load.classes["over"] = bool(q.get("over"))
        self.epics_panel.items = [dict(e, host=q["host"]) for e in q["epics"]]
        self.free.visible = not q["epics"]
