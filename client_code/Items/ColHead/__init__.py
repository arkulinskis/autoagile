from anvil import *

from ._anvil_designer import ColHeadTemplate
from ... import aa


class ColHead(ColHeadTemplate):
    """A board column's head: name (and its stage when the stage is split), count / WIP limit, a red glow when over."""

    def __init__(self, **properties):
        super().__init__(**properties)
        c = self.item
        n = len(c["cards"])
        over = bool(c.get("limit") and n > c["limit"])
        self.classes.update({"over": over, "show": bool(c.get("show"))})
        for k in (["bad", "blink"] if over else ["on"] if n else []):
            self.led.classes.add(k)
        self.stage_box.visible = bool(c.get("split"))
        self.stage.text = aa.STATUS.get(c["stage"], c["stage"]) + " ›"
        self.n.text = "%d%s" % (n, ("/%d" % c["limit"]) if c.get("limit") else "")
