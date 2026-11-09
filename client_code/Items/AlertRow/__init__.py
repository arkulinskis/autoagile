from anvil import *

from ._anvil_designer import AlertRowTemplate
from ... import router, state

LED = {"bad": ["bad", "blink"], "warn": ["warn"], "good": ["on"], "info": ["pink"]}


class AlertRow(AlertRowTemplate):
    """A deck alert; it links to the page that fixes it. item = {level, text, go: 'page/arg'}."""

    def __init__(self, **properties):
        super().__init__(**properties)
        state.set_attr(self, "href", router.href(*self.item["go"].split("/")))
        for c in LED.get(self.item["level"], []):
            self.led.classes.add(c)
