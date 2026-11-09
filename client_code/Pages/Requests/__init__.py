from anvil import *
from anvil.js import window

from ._anvil_designer import RequestsTemplate
from ... import aa, router, state


def kpis(s, promise):
    return [{"value": s["open"], "label": "open"},
            {"value": s["overdue"], "label": "past the %d-day promise" % promise, "cls": "red" if s["overdue"] else "cyan"},
            {"value": "--" if s["median_days"] is None else s["median_days"], "unit": "" if s["median_days"] is None else "d",
             "label": "median time to answer", "cls": "pink"},
            {"value": "--" if s["on_time"] is None else s["on_time"], "unit": "" if s["on_time"] is None else "%",
             "label": "answered on time", "cls": "amber"},
            {"value": s["shipped"], "label": "shipped"}]


class Requests(RequestsTemplate):
    """#requests: the crew's request desk: the ask link, the answer promise (7/14/30 days), open requests by votes with
    their clock, and the answers (Accept makes a backlog card; Later and Decline need a reason). #ask/<code> is Pages/Ask."""

    def __init__(self, args=(), **properties):
        super().__init__(**properties)
        self.crew = aa.need_crew(self)
        if not self.crew:
            return
        state.set_control_attr(self.title_box, "aria-label", "Title")
        state.set_control_attr(self.body_box, "aria-label", "Details")
        self._load()

    def _load(self):
        d = state.call("get_requests", self.crew["id"])
        if not d:
            return
        self.d = d
        self.sub.text = "%s // Every request gets an answer within %d days: yes, later or no, with a reason." % (d["crew"]["key"], d["promise_days"])
        state.set_attr(self.ask_link, "href", router.href("ask", d["ask_code"]))
        self.demo_note.visible = d["crew"]["demo"]
        self.kpi_panel.items = kpis(d["stats"], d["promise_days"])
        reqs = d["requests"]
        opened = [r for r in reqs if r["status"] == "open"]
        done = [r for r in reqs if r["status"] != "open"]
        self.open_panel.items = [dict(r, crew=True, can_vote=True, host=self) for r in opened]
        self.open_empty.visible = not opened
        self.open_extra.text = "%d open" % len(opened)
        self.open_win.classes["warn"] = any(r.get("overdue") for r in opened)
        self.done_panel.items = [dict(r, crew=True, can_vote=True, host=self) for r in done]
        self.done_empty.visible = not done
        self.done_extra.text = str(len(done))
        loc = window.location
        self.link.text = loc.origin + loc.pathname + "#ask/" + d["ask_code"]
        self.new_link.visible = d["can_admin"]
        for p, b in ((7, self.p7), (14, self.p14), (30, self.p30)):
            b.visible = p in d["promises"]
            b.role = ["seg", "on"] if p == d["promise_days"] else ["seg"]

    def reload(self):
        self._load()

    def vote(self, rid, on):
        if state.call("vote_request", rid, on) is not None:
            self._load()

    def answer(self, rid, status):
        if status == "open":
            if state.call("answer_request", rid, "open", "") is not None:
                self._load()
            return
        from ...Dialogs.AnswerDialog import AnswerDialog
        r = alert(AnswerDialog(request_id=rid, status=status), buttons=[], role="app-dialog")
        if r:
            state.toast(("Accepted: %s is in the backlog" % r["request"]["card"]["key"]) if status == "accepted" and r["request"].get("card") else "Answered", "ok")
            self._load()

    def _promise(self, days):
        if state.call("update_crew", self.crew["id"], {"promise_days": days}) is not None:
            state.toast("Answer promise saved", "ok")
            self._load()

    @handle("p7", "click")
    def p7_click(self, **event_args):
        self._promise(7)

    @handle("p14", "click")
    def p14_click(self, **event_args):
        self._promise(14)

    @handle("p30", "click")
    def p30_click(self, **event_args):
        self._promise(30)

    @handle("copy_link", "click")
    def copy_link_click(self, **event_args):
        aa.copy(self.link.text)

    @handle("new_link", "click")
    def new_link_click(self, **event_args):
        if confirm("The old link stops working. Share the new one.", title="Make a new ask link?",
                   buttons=[("Cancel", False), ("New link", True)], role="app-dialog"):
            if state.call("new_ask_code", self.crew["id"]) is not None:
                self._load()

    @handle("add_button", "click")
    def add_button_click(self, **event_args):
        if state.call("submit_request", self.title_box.text or "", self.body_box.text or "", self.crew["id"]) is not None:
            state.toast("Request added", "ok")
            self.title_box.text = self.body_box.text = ""
            self._load()
