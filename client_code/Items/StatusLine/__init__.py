from anvil import *

from ._anvil_designer import StatusLineTemplate


class StatusLine(StatusLineTemplate):
    """One short line: an optional card key, the text, an optional faint note on the right. Used for the review lane's
    gate answers, the standup and the public status page. item = {key, text, sub, cls} (cls: good, warn, bad, stuck)."""

    def __init__(self, **properties):
        super().__init__(**properties)
        it = self.item
        self.key.text = it.get("key") or ""
        self.key.visible = bool(it.get("key"))
        self.text.text = it.get("text") or ""
        self.sub.text = it.get("sub") or ""
        self.sub.visible = bool(it.get("sub"))
        if it.get("cls"):
            self.text.role = ["st-text", it["cls"]]
