from anvil import *

from ._anvil_designer import PhoneTabTemplate


class PhoneTab(PhoneTabTemplate):
    """On a phone the board shows one column at a time: these tabs pick it. item = {id, name, n, on}."""

    def __init__(self, **properties):
        super().__init__(**properties)
        self.tab.text = "%s %d" % (self.item["name"], self.item["n"])
        self.tab.role = ["seg", "on"] if self.item["on"] else ["seg"]

    @handle("tab", "click")
    def tab_click(self, **event_args):
        self.parent.raise_event("x-pcol", col_id=self.item["id"])
