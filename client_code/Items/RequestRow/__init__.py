from anvil import *

from ._anvil_designer import RequestRowTemplate
from ... import aa, router, state


class RequestRow(RequestRowTemplate):
    """A request with its votes, clock, answer and (for the crew) Accept / Later / Decline / Reopen.
    item = request dict + crew (bool) + can_vote + host (the page: vote(), answer())."""

    def __init__(self, **properties):
        super().__init__(**properties)
        r = self.item
        self.vote.text = "%d VOTES" % r["votes"]
        self.vote.role = ["rq-vote", "on"] if r["voted"] else ["rq-vote"]
        self.vote.enabled = bool(r.get("can_vote"))
        state.set_control_attr(self.vote, "aria-pressed", "true" if r["voted"] else "false")
        state.set_control_attr(self.vote, "aria-label", "%s (%d votes)" % ("Remove your vote" if r["voted"] else "Vote", r["votes"]))
        if r["status"] == "open":
            if r.get("overdue"):
                self.st.text, cls = "overdue by %dd" % max(1, -r.get("due_in", 0)), "late"
            else:
                self.st.text, cls = ("answer due today" if r.get("due_in") == 0 else "answer due in %sd" % r.get("due_in")), "open"
        elif r.get("shipped"):
            self.st.text, cls = "shipped", "shipped"
        else:
            self.st.text, cls = r["status"], r["status"]
        self.st.role = ["rq-st", cls]
        self.by.text = "by %s%s · %s" % (r["by"], " (you)" if r.get("mine") else "", state.ago(r["created"]))
        card = r.get("card")
        self.card_link.visible = bool(card)
        if card:
            self.card_text.text = "%s · %s" % (card["key"], aa.STATUS.get(card["status"], card["status"]))
            state.set_attr(self.card_link, "href", router.href("card", card["key"]))
        self.body.visible = bool(r.get("body"))
        answered = r["status"] != "open" and (r.get("answer") or r.get("answered_by"))
        self.answer_box.visible = bool(answered)
        if answered:
            self.ans_head.text = "%s answered%s" % (r.get("answered_by") or "The crew", (" in " + state.plural(r["took"], "day")) if r.get("took") is not None else "")
            self.ans_text.text = r.get("answer") or "Accepted."
        crew = bool(r.get("crew"))
        self.acts.visible = crew
        is_open = r["status"] == "open"
        self.accept.visible = self.later.visible = self.decline.visible = is_open
        self.reopen.visible = not is_open

    @handle("vote", "click")
    def vote_click(self, **event_args):
        self.item["host"].vote(self.item["id"], not self.item["voted"])

    @handle("accept", "click")
    def accept_click(self, **event_args):
        self.item["host"].answer(self.item["id"], "accepted")

    @handle("later", "click")
    def later_click(self, **event_args):
        self.item["host"].answer(self.item["id"], "later")

    @handle("decline", "click")
    def decline_click(self, **event_args):
        self.item["host"].answer(self.item["id"], "declined")

    @handle("reopen", "click")
    def reopen_click(self, **event_args):
        self.item["host"].answer(self.item["id"], "open")
