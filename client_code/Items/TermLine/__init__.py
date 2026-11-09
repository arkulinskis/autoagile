from anvil import *

from ._anvil_designer import TermLineTemplate


class TermLine(TermLineTemplate):
    """A console line. item = {cls: in|ok|err|'' , text}."""

    def __init__(self, **properties):
        super().__init__(**properties)
        if self.item.get("cls"):
            self.classes.add(self.item["cls"])
