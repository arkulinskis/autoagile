from anvil import *

from ._anvil_designer import PastSprintRowTemplate
from ... import state


class PastSprintRow(PastSprintRowTemplate):
    """A closed sprint: dates, points done of committed, its retro. item = sprint + host (the Plan page)."""

    def __init__(self, **properties):
        super().__init__(**properties)
        s = self.item
        self.dates.text = "%s – %s" % (state.short_date(s["start"]), state.short_date(s["end"]))
        done = s.get("done_final") or 0
        pct = round(100.0 * done / s["committed"]) if s.get("committed") else None
        self.pts.text = "%s/%s%s" % (done, s.get("committed") or 0, (" · %d%%" % pct) if pct is not None else "")
        r = s.get("retro") or {}
        n = len(r.get("louder") or []) + len(r.get("mute") or []) + len(r.get("remix") or [])
        self.retro.text = "Retro" + (" (%d)" % n if n else "")

    @handle("retro", "click")
    def retro_click(self, **event_args):
        self.item["host"].open_retro(self.item["id"])
