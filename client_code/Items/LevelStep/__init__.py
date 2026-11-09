from anvil import *

from ._anvil_designer import LevelStepTemplate


class LevelStep(LevelStepTemplate):
    """One cell of the level meter. item = {on}."""

    def __init__(self, **properties):
        super().__init__(**properties)
        self.cell.classes["on"] = bool(self.item.get("on"))
