from anvil import *

from ._anvil_designer import ReadyRowTemplate


class ReadyRow(ReadyRowTemplate):
    """One Definition of Ready check (green or red). item = {label, ok}."""

    def __init__(self, **properties):
        super().__init__(**properties)
        self.led.classes.add("on" if self.item["ok"] else "bad")
