from anvil import *
import anvil.server

from ._anvil_designer import AskTemplate
from ... import aa, router, state


class Ask(AskTemplate):
    """#ask/<code>: what people with a crew's ask link see: add a request, vote, read every answer. Never the board."""

    def __init__(self, args=(), **properties):
        super().__init__(**properties)
        self.code = (args[0] if args else "").upper()
        state.set_control_attr(self.title_box, "aria-label", "What do you need?")
        state.set_control_attr(self.body_box, "aria-label", "Why it matters")
        self._load()

    def _load(self):
        d: dict = {}
        try:
            d = anvil.server.call("ask_page", self.code)
        except Exception as e:
            d = {"ok": False, "error": str(e)}
        ok = bool(d and d.get("ok"))
        self.bad_box.visible = not ok
        self.page.visible = ok
        if not ok:
            self.bad_text.text = (d or {}).get("error") or ""
            return
        self.d = d
        c = d["crew"]
        self.title.text = "Ask " + c["name"]
        state.heading(self.title, 1)
        self.sub.text = "%s // %s" % (c["key"], c.get("mission") or "Tell the crew what you need.")
        self.desk_button.visible = bool(c.get("id"))
        self.demo_note.visible = bool(c.get("demo"))
        self.reqs_panel.items = [dict(r, crew=False, can_vote=r["status"] == "open", host=self) for r in d["requests"]]
        self.reqs_empty.visible = not d["requests"]
        self.reqs_extra.text = "%d open" % d["stats"]["open"]
        self.promise.text = ("%s answers every request within %d days: yes (and you watch it ship), later, or no, always with a reason."
                             % (c["name"], d["promise_days"]))
        s = d["stats"]
        self.kpi_panel.items = [{"value": "--" if s["median_days"] is None else s["median_days"], "unit": "" if s["median_days"] is None else "d",
                                 "label": "median answer", "cls": "pink"}, {"value": s["shipped"], "label": "shipped", "cls": "cyan"}]

    def vote(self, rid, on):
        if state.call("vote_request", rid, on, self.code) is not None:
            self._load()

    def answer(self, rid, status):
        pass

    @handle("desk_button", "click")
    def desk_button_click(self, **event_args):
        aa.load_crews()
        aa.set_crew(self.d["crew"]["id"])
        router.go("requests")

    @handle("send_button", "click")
    def send_button_click(self, **event_args):
        if state.call("submit_request", self.title_box.text or "", self.body_box.text or "", None, self.code) is not None:
            aa.rave("REQUEST SENT", "%s answers within %d days" % (self.d["crew"]["key"], self.d["promise_days"]))
            self.title_box.text = self.body_box.text = ""
            self._load()
