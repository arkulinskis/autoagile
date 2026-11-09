from anvil import *

from ._anvil_designer import LevelInfoRowTemplate


class LevelInfoRow(LevelInfoRowTemplate):
    """What a level adds (lit when the crew has it). item = level + cur."""

    def __init__(self, **properties):
        super().__init__(**properties)
        self.lname.text = "%d. %s" % (self.item["n"], self.item["name"])
        if self.item["n"] <= self.item["cur"]:
            self.led.classes.add("on")
