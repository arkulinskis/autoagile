from anvil import *

from ._anvil_designer import TextDialogTemplate
from ... import state


class TextDialog(TextDialogTemplate):
    """Ask for one line of text (the sprint goal). Closes with the text, or None."""

    def __init__(self, title="", value="", **properties):
        super().__init__(**properties)
        self.title.text = title
        state.heading(self.title, 2)
        self.box.text = value
        state.set_control_attr(self.box, "aria-label", title)

    @handle("box", "pressed_enter")
    def box_pressed_enter(self, **event_args):
        self.save_button_click()

    @handle("cancel_button", "click")
    def cancel_button_click(self, **event_args):
        self.raise_event("x-close-alert", value=None)

    @handle("save_button", "click")
    def save_button_click(self, **event_args):
        self.raise_event("x-close-alert", value=self.box.text or "")
