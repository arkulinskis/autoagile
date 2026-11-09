from anvil import *

from ._anvil_designer import GateRowTemplate
from ... import state


class GateRow(GateRowTemplate):
    """One complexity gate: the question and its four answers (green to red). item = {g, value, next}."""

    def __init__(self, **properties):
        super().__init__(**properties)
        g = self.item["g"]
        self.classes["next"] = bool(self.item.get("next"))
        self.keys.visible = bool(self.item.get("next"))
        state.set_attr(self.opts, "aria-label", g["name"])
        for i, b in enumerate([self.o0, self.o1, self.o2, self.o3]):
            on = self.item.get("value") == i
            b.text = g["opts"][i]
            b.role = ["gate-opt", "lv%d" % i] + (["on"] if on else [])
            state.set_control_attr(b, "role", "radio")
            state.set_control_attr(b, "aria-checked", "true" if on else "false")
            state.set_control_attr(b, "data-key", "%s-%d" % (g["id"], i))

    def _pick(self, i):
        key = "%s-%d" % (self.item["g"]["id"], i)
        p = self.parent
        if p is not None:
            p.raise_event("x-pick", gid=self.item["g"]["id"], value=i)
            state.refocus(p, key)

    @handle("o0", "click")
    def o0_click(self, **event_args):
        self._pick(0)

    @handle("o1", "click")
    def o1_click(self, **event_args):
        self._pick(1)

    @handle("o2", "click")
    def o2_click(self, **event_args):
        self._pick(2)

    @handle("o3", "click")
    def o3_click(self, **event_args):
        self._pick(3)
