from anvil import *
import anvil.js
from anvil.js import window

from ._anvil_designer import PartyTemplate
from ... import aa, router, state


class Party(PartyTemplate):
    """#backlog/party, the Estimation Party: unestimated cards one by one through the gates. Keys 1-4 answer the next
    gate, Enter saves, S skips (a document key listener, removed in leave())."""

    def __init__(self, args=(), **properties):
        super().__init__(**properties)
        self.crew = aa.need_crew(self)
        if not self.crew:
            return
        d = state.call("get_backlog", self.crew["id"])
        if not d:
            return
        self.cfg = d.get("gates")
        cards = d["cards"] + [c for s in d["sprints"] for c in s["cards_list"]]
        self.queue = [c for c in cards if c["points"] is None and c["status"] != "done"]
        self.i, self.done = 0, 0
        self._keys = anvil.js.report_exceptions(self._key)
        window.document.addEventListener("keydown", self._keys)
        self.gates.cfg = self.cfg
        self._show()

    def leave(self):
        window.document.removeEventListener("keydown", self._keys)

    def _show(self):
        if self.i >= len(self.queue):
            self.stage_box.visible = False
            self.done_box.visible = True
            self.done_text.text = (state.plural(self.done, "card") + " estimated. " if self.done else "") + "Nothing left without points."
            if self.done:
                aa.rave("GROOMED!", state.plural(self.done, "card") + " through the gates")
            return
        self.stage_box.visible = True
        self.done_box.visible = False
        c = self.queue[self.i]
        self.count.text = "%d / %d" % (self.i + 1, len(self.queue))
        self.key.text = c["key"]
        self.type_tag.text = c["type"]
        self.type_tag.role = ["aa-type", "t-" + c["type"]]
        self.prio.visible = c["priority"] != 2
        self.prio.text = "P%s" % c["priority"]
        self.prio.role = ["aa-prio", "p%s" % c["priority"]]
        self.title.text = c["title"]
        state.heading(self.title, 2)
        self.epic.visible = bool(c.get("epic"))
        self.epic.text = ("● " + c["epic"]["title"]) if c.get("epic") else ""
        self.acc.text = state.plural(c["acc_total"], "acceptance criterion", "acceptance criteria") + "."
        state.set_attr(self.card_link, "href", router.href("card", c["key"]))
        self.gates.answers = c.get("gates") or {}
        self.save_button.enabled = self.gates.score()["complete"]

    @handle("gates", "gates_change")
    def gates_change(self, answers=None, score=None, **event_args):
        self.save_button.enabled = bool(score and score["complete"])

    def _save(self):
        if not self.gates.score()["complete"]:
            return
        c = self.queue[self.i]
        r = state.call("estimate_card", c["id"], self.gates.answers)
        if r:
            self.done += 1
            state.toast("%s: %s pts (%s)" % (c["key"], r["gate"]["points"], r["gate"]["rung"]), "ok")
            self.i += 1
            self._show()

    @handle("save_button", "click")
    def save_button_click(self, **event_args):
        self._save()

    @handle("skip_button", "click")
    def skip_button_click(self, **event_args):
        self.i += 1
        self._show()

    def _key(self, e):
        if self.i >= len(self.queue):
            return
        tag = str(getattr(e.target, "tagName", "") or "")
        if tag in ("INPUT", "TEXTAREA", "SELECT") or window.document.querySelector(".anvil-modal.in, .modal.in"):
            return
        if e.key in ("1", "2", "3", "4"):
            self.gates.key(int(e.key))
            e.preventDefault()
        elif e.key == "Enter" and tag != "BUTTON" and tag != "A":
            e.preventDefault()
            self._save()
        elif e.key in ("s", "S"):
            self.i += 1
            self._show()
