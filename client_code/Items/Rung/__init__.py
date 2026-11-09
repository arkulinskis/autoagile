from anvil import *

from ._anvil_designer import RungTemplate


class Rung(RungTemplate):
    """A rung of the points ladder. item = {points, name, lit, top}."""

    def __init__(self, **properties):
        super().__init__(**properties)
        p = self.item["points"]
        lit = bool(self.item["lit"])
        self.pts.text = str(p)
        self.classes.update({"lit": lit, "hot": lit and p >= 8, "fire": lit and p >= 13, "top": bool(self.item["top"])})
