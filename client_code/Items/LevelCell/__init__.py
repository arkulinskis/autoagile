from anvil import *

from ._anvil_designer import LevelCellTemplate


class LevelCell(LevelCellTemplate):
    """A rung of the level ladder (done, you are here, locked). item = level + cur."""

    def __init__(self, **properties):
        super().__init__(**properties)
        n, cur = self.item["n"], self.item["cur"]
        self.n.text = "LVL %d" % n + (" 🔒" if n > cur else "")
        self.classes.add("done" if n < cur else "cur" if n == cur else "locked")
