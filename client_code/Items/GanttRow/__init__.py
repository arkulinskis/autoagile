from anvil import *

from ._anvil_designer import GanttRowTemplate
from ... import state

CONF = {"safe": "SAFE", "likely": "LIKELY", "stretch": "STRETCH", "nofit": "WON'T FIT"}


class GanttRow(GanttRowTemplate):
    """An epic on the 3-month forecast: a bar to the likely sprint, whiskers from optimistic to pessimistic.
    item = forecast epic + n (number of sprint slots)."""

    def __init__(self, **properties):
        super().__init__(**properties)
        e, n = self.item, self.item["n"]

        def pct(v):
            return min(100.0, 100.0 * v / n)
        left = pct(e["start"])
        w = max(2.0, pct(min(e["finish_avg"], n + 0.5)) - left)
        self.dot.style["background"] = e["color"]
        self.meta.text = "%s pts left · %s%% done" % (e["remaining"], e["progress"])
        state.set_attr(self.track, "style", "--slot:%s%%" % (100.0 / n))
        state.set_attr(self.track, "title", "Optimistic sprint %s, likely %s, pessimistic %s" % (e["finish_opt"], e["finish_avg"], e["finish_pes"]))
        state.set_attr(self.whisk, "style", "left:%s%%;width:%s%%" % (pct(e["finish_opt"]), max(0.5, pct(min(e["finish_pes"], n)) - pct(e["finish_opt"]))))
        state.set_attr(self.barline, "style", "left:%s%%;width:%s%%;background:%s" % (left, w, e["color"]))
        self.conf.text = CONF.get(e["confidence"], e["confidence"])
        self.conf.role = ["pl-conf", e["confidence"]]
