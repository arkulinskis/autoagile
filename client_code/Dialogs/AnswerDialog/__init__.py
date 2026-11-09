from anvil import *

from ._anvil_designer import AnswerDialogTemplate
from ... import state

WORDS = {"accepted": ("Accept this request?", "It becomes a card in the backlog, and the requester sees it move to Shipped. A note is optional.", "Accept"),
         "later": ("Not now, maybe later", "Say why and when you might look again. A reason makes a \"not now\" fair.", "Answer: later"),
         "declined": ("Decline this request", "Say why in a sentence or two. People take a clear no better than silence.", "Decline")}


class AnswerDialog(AnswerDialogTemplate):
    """Answer a request: accept (note optional), later or decline (a reason of 10+ characters). Closes with the reply."""

    def __init__(self, request_id=None, status="accepted", **properties):
        super().__init__(**properties)
        self.rid, self.status = request_id, status
        w = WORDS[status]
        self.title.text = w[0]
        state.heading(self.title, 2)
        self.text.text = w[1]
        self.ans_label.text = "Answer (optional)" if status == "accepted" else "Answer"
        self.ok_button.text = w[2]
        self.ok_button.role = ["btn", "btn-danger", "btn-solid"] if status == "declined" else ["btn", "btn-primary"]
        state.set_control_attr(self.answer, "aria-label", "Answer")

    @handle("cancel_button", "click")
    def cancel_button_click(self, **event_args):
        self.raise_event("x-close-alert", value=None)

    @handle("ok_button", "click")
    def ok_button_click(self, **event_args):
        txt = (self.answer.text or "").strip()
        if self.status != "accepted" and len(txt) < 10:
            state.toast("Give a reason of a sentence or so.", "error")
            return
        r = state.call("answer_request", self.rid, self.status, txt)
        if r:
            self.raise_event("x-close-alert", value=r)
