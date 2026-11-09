from anvil import *

from ._anvil_designer import RetroDialogTemplate
from ... import state


def _lines(t):
    return [x.strip() for x in (t or "").split("\n") if x.strip()]


class RetroDialog(RetroDialogTemplate):
    """The retro: LOUDER / MUTE / REMIX + action items. Closes with True when saved."""

    def __init__(self, **properties):
        sprint = properties.pop("sprint")
        super().__init__(**properties)
        self.sprint = sprint
        r = sprint.get("retro") or {}
        self.title.text = "Retro: " + sprint["name"]
        state.heading(self.title, 2)
        self.louder.text = "\n".join(r.get("louder") or [])
        self.mute.text = "\n".join(r.get("mute") or [])
        self.remix.text = "\n".join(r.get("remix") or [])
        self.actions.text = "\n".join(("[x] " if a.get("done") else "") + a["text"] for a in (r.get("actions") or []))

    @handle("cancel_button", "click")
    def cancel_button_click(self, **event_args):
        self.raise_event("x-close-alert", value=None)

    @handle("save_button", "click")
    def save_button_click(self, **event_args):
        acts = []
        for a in _lines(self.actions.text):
            done = a.lower().startswith("[x]")
            acts.append({"text": a[3:].strip() if done else a, "done": done})
        out = {"louder": _lines(self.louder.text), "mute": _lines(self.mute.text), "remix": _lines(self.remix.text), "actions": acts}
        if state.call("save_retro", self.sprint["id"], out) is not None:
            self.raise_event("x-close-alert", value=True)
