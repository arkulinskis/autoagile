from anvil import *
import anvil.server

from ._anvil_designer import StatusTemplate
from ... import state


def _rows(items, with_age=False):
    out = []
    for x in items:
        sub = x.get("who") or ""
        if with_age and x.get("age") is not None:
            sub = (sub + " · " if sub else "") + ("%dd" % int(x["age"]) if x["age"] >= 1 else "today")
        out.append({"key": x["key"], "text": x["title"], "sub": sub})
    return out


class Status(StatusTemplate):
    """#status/<code>: a crew's public, read-only status page (no sign-in): shipped this week, in progress, in review,
    blocked count. Keys, titles and first names only. The crew switches it on in #standup."""

    def __init__(self, args=(), **properties):
        super().__init__(**properties)
        self.code = (args[0] if args else "").upper()
        state.heading(self.title, 1)
        self._load()

    def _load(self):
        d: dict = {}
        try:
            d = anvil.server.call("public_status", self.code)
        except Exception as e:
            d = {"ok": False, "error": str(e)}
        ok = bool(d and d.get("ok"))
        self.bad_box.visible = not ok
        self.page.visible = ok
        if not ok:
            self.bad_text.text = (d or {}).get("error") or "This status link doesn't work."
            return
        c, tt = d["crew"], d["totals"]
        self.title.text = c["name"] + ": status"
        self.sub.text = "%s // LVL %d %s%s%s" % (c["key"], c["level"]["n"], c["level"]["name"],
                                                (" · " + c["mission"]) if c.get("mission") else "",
                                                (" · %s AI agent%s on the crew" % (c["agents"], "" if c["agents"] == 1 else "s")) if c.get("agents") else "")
        self.updated.text = "LIVE · " + state.date_time(d["updated"])
        self.demo_note.visible = bool(c.get("demo"))
        self.kpi_panel.items = [
            {"value": tt["shipped"], "label": "Shipped in 7 days (%d pts)" % tt["points"]},
            {"value": tt["per_week"], "label": "Avg per week", "cls": "cyan"},
            {"value": tt["doing"], "label": "In progress", "cls": "pink"},
            {"value": tt["review"], "label": "Waiting for review", "cls": "amber"},
            {"value": d["blocked"], "label": "Blocked", "cls": "red" if d["blocked"] else ""}]
        for name, items, age in (("shipped", d["shipped"], False), ("doing", d["doing"], True), ("review", d["review"], True)):
            getattr(self, name + "_panel").items = _rows(items, age)
            getattr(self, name + "_empty").visible = not items
            getattr(self, name + "_extra").text = str(len(items))
