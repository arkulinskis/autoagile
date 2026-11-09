from anvil import *

from ._anvil_designer import CloseSprintTemplate
from ... import state


class CloseSprint(CloseSprintTemplate):
    """Close the running sprint: where unfinished cards go. Closes with 'next' / 'backlog', or None."""

    def __init__(self, **properties):
        sprint = properties.pop("sprint")
        super().__init__(**properties)
        self.title.text = "Close %s?" % sprint["name"]
        state.heading(self.title, 2)
        self.text.text = "%s of %s points are done. Unfinished cards go:" % (sprint["done_points"], sprint["points"])

    @handle("cancel_button", "click")
    def cancel_button_click(self, **event_args):
        self.raise_event("x-close-alert", value=None)

    @handle("close_button", "click")
    def close_button_click(self, **event_args):
        self.raise_event("x-close-alert", value="backlog" if self.to_backlog.selected else "next")
