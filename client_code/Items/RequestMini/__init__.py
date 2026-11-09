from anvil import *

from ._anvil_designer import RequestMiniTemplate


class RequestMini(RequestMiniTemplate):
    """A top-voted open request on the deck. item = a request dict."""

    def __init__(self, **properties):
        super().__init__(**properties)
        r = self.item
        self.votes.text = str(r["votes"])
        self.due.text = "overdue" if r["overdue"] else "%sd left" % r["due_in"]
        self.due.role = ["dk-due", "late"] if r["overdue"] else ["dk-due"]
