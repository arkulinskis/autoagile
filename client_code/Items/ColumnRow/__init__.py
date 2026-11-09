from anvil import *

from ._anvil_designer import ColumnRowTemplate
from ... import state

STAGES = [("Ready stage", "ready"), ("Doing stage", "doing"), ("Review stage", "review"), ("Done stage", "done")]


class ColumnRow(ColumnRowTemplate):
    """A board column in the editor: name, stage, its own WIP limit, move up, remove. item = {col, i, sub, can_up}.
    Raises x-col(action, i, value) on the panel; the Crew page keeps the list and saves it."""

    def __init__(self, **properties):
        super().__init__(**properties)
        x = self.item["col"]
        self.classes["sub"] = bool(self.item["sub"])
        self.cname.text = x["name"]
        self.stage.items = STAGES
        self.stage.selected_value = x["stage"]
        self.wip.text = x.get("wip") or ""
        self.up.enabled = bool(self.item["can_up"])
        self.remove.enabled = bool(self.item["sub"])
        state.set_control_attr(self.cname, "aria-label", "Column name")
        state.set_control_attr(self.stage, "aria-label", "Stage")
        state.set_control_attr(self.wip, "aria-label", "WIP limit for this column")

    def _send(self, action, value=None):
        self.parent.raise_event("x-col", action=action, i=self.item["i"], value=value)

    @handle("cname", "change")
    def cname_change(self, **event_args):
        self._send("set", ("name", self.cname.text or ""))

    @handle("stage", "change")
    def stage_change(self, **event_args):
        self._send("set", ("stage", self.stage.selected_value))

    @handle("wip", "change")
    def wip_change(self, **event_args):
        v = self.wip.text
        self._send("set", ("wip", int(v) if v not in (None, "") else None))

    @handle("up", "click")
    def up_click(self, **event_args):
        self._send("up")

    @handle("remove", "click")
    def remove_click(self, **event_args):
        self._send("del")
