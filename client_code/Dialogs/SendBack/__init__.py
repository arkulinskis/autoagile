from anvil import *

from ._anvil_designer import SendBackTemplate
from ... import state

QUICK = {"q_tests": "Tests are missing for the new behaviour.",
         "q_scope": "Some of the changes are outside this card's scope. Keep the PR to what the card asks.",
         "q_criteria": "Not all acceptance criteria are met yet.",
         "q_split": "Too big to review in one go. Split it into smaller PRs."}


class SendBack(SendBackTemplate):
    """Send a card in Review back to Doing with a reason (10+ characters). The reason is logged on the card and shows in
    the agent's brief under "Review feedback". Quick buttons add common reasons. Closes with the server reply, or None."""

    def __init__(self, card_id=None, key="", title="", **properties):
        super().__init__(**properties)
        self.card_id = card_id
        self.title.text = "Send %s back" % key
        state.heading(self.title, 2)
        self.text.text = "\"%s\" goes back to Doing with your notes. If an agent built it, the notes are in its brief the next time it reads the card." % title
        state.set_control_attr(self.reason, "aria-label", "What to fix")
        for name in QUICK:
            getattr(self, name).set_event_handler("click", self._quick)

    def _quick(self, sender=None, **event_args):
        for name, line in QUICK.items():
            if getattr(self, name) is sender:
                cur = (self.reason.text or "").strip()
                if line not in cur:
                    self.reason.text = (cur + "\n" + line).strip()
                sender.enabled = False
        state.focus(self.reason)

    @handle("cancel_button", "click")
    def cancel_button_click(self, **event_args):
        self.raise_event("x-close-alert", value=None)

    @handle("ok_button", "click")
    def ok_button_click(self, **event_args):
        txt = (self.reason.text or "").strip()
        if len(txt) < 10:
            state.toast("Say what to fix (a sentence or so).", "error")
            return
        r = state.call("review_card", self.card_id, "send_back", txt)
        if r:
            self.raise_event("x-close-alert", value=r)
