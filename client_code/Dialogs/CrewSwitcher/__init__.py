from anvil import *

from ._anvil_designer import CrewSwitcherTemplate
from ... import aa, router


class CrewSwitcher(CrewSwitcherTemplate):
    """Pick the crew to look at (the header chip). Closes with the crew id, or None."""

    def __init__(self, **properties):
        super().__init__(**properties)
        cur = aa.current()
        self.crews_panel.items = [dict(c, on=bool(cur and cur["id"] == c["id"])) for c in aa.crews()]
        self.crews_panel.add_event_handler("x-pick", self._pick)

    def _pick(self, crew_id, **event_args):
        self.raise_event("x-close-alert", value=crew_id)

    @handle("new_button", "click")
    def new_button_click(self, **event_args):
        self.raise_event("x-close-alert", value=None)
        router.go("crew", "new")

    @handle("join_button", "click")
    def join_button_click(self, **event_args):
        self.raise_event("x-close-alert", value=None)
        router.go("crew", "join")

    @handle("close_button", "click")
    def close_button_click(self, **event_args):
        self.raise_event("x-close-alert", value=None)
