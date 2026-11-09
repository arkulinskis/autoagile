from anvil import *

from ._anvil_designer import GatesTemplate
from ... import aa


class Gates(GatesTemplate):
    """The complexity-gates widget (was AA.gateWidget): four answers per gate, the points ladder lights up, the verdict
    and agent fit underneath. Raises gates_change(answers, score) on every answer."""

    def __init__(self, **properties):
        self._answers, self._cfg, self._ready = {}, None, False
        super().__init__(**properties)
        self.rows_panel.add_event_handler("x-pick", self._pick)
        self._ready = True
        self._draw()

    @property
    def answers(self):
        return dict(self._answers)

    @answers.setter
    def answers(self, value):
        self._answers = dict(value or {})
        self._draw()

    @property
    def cfg(self):
        return self._cfg

    @cfg.setter
    def cfg(self, value):
        self._cfg = value or None
        self._draw()

    def config(self):
        return self._cfg or aa.GATES_CFG

    def score(self):
        return aa.gate_score(self._answers, self.config())

    def key(self, n):
        """Keys 1-4 answer the next unanswered gate. True if it took the key."""
        for g in self.config()["gates"]:
            if self._answers.get(g["id"]) is None and 1 <= n <= 4:
                self._set(g["id"], n - 1)
                return True
        return False

    def _pick(self, gid, value, **event_args):
        self._set(gid, value)

    def _set(self, gid, value):
        self._answers[gid] = value
        self._draw()
        self.raise_event("gates_change", answers=dict(self._answers), score=self.score())

    def _draw(self):
        if not self._ready:
            return
        cfg = self.config()
        s = self.score()
        nxt = None
        for g in cfg["gates"]:
            if nxt is None and self._answers.get(g["id"]) is None:
                nxt = g["id"]
        self.rows_panel.items = [{"g": g, "value": self._answers.get(g["id"]), "next": g["id"] == nxt} for g in cfg["gates"]]
        lit = s["points"] if s["complete"] else None
        self.ladder_panel.items = [{"points": r["points"], "name": r["name"], "lit": lit is not None and r["points"] <= lit,
                                    "top": r["points"] == lit} for r in reversed(cfg["ladder"])]
        if s["complete"]:
            self.big.text = "%d PTS // %s" % (s["points"], s["rung"])
            self.big.role = ["verdict-big"]
            self.fit_tag.visible = True
            self.fit_tag.text = ("⚡ " if s["fit"] == "solo" else "") + aa.FIT[s["fit"]]
            self.fit_tag.role = ["aa-fit", "fit-" + s["fit"]]
            self.hint.visible = False
            self.notes.visible = bool(s["notes"])
            self.notes.text = "\n".join(s["notes"])
            self.notes.role = ["verdict-note", "bad"] if s["verdict"] != "go" else ["verdict-note"]
        else:
            self.big.text = "%d/%d" % (s["answered"], len(cfg["gates"]))
            self.big.role = ["verdict-big", "faint"]
            self.fit_tag.visible = False
            self.hint.visible = True
            self.notes.visible = False
