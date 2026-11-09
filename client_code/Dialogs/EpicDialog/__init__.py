from anvil import *

from ._anvil_designer import EpicDialogTemplate
from ... import state


class EpicDialog(EpicDialogTemplate):
    """New or edit an epic (name, what and why, size, quarter, status, colour). Closes with True after a save/delete."""

    def __init__(self, **properties):
        epic, crew_id, plan = properties.pop("epic"), properties.pop("crew_id"), properties.pop("plan")
        super().__init__(**properties)
        d = plan
        self.crew_id = crew_id
        self.epic_id = epic["id"] if epic else None
        e = epic or {"title": "", "body": "", "size": "M", "quarter": d["quarters"][0], "status": "planned",
                     "color": d["colors"][len(d["epics"]) % len(d["colors"])]}
        self.title.text = "Edit epic" if epic else "New epic"
        state.heading(self.title, 2)
        self.name_box.text = e["title"]
        self.body_box.text = e.get("body") or ""
        self.size_box.items = [("%s · about %s pts" % (k, v), k) for k, v in d["sizes"].items()]
        self.size_box.selected_value = e.get("size") or "M"
        qs = list(d["quarters"]) + ([e["quarter"]] if e.get("quarter") and e["quarter"] not in d["quarters"] else [])
        self.quarter_box.items = [("Unscheduled", "")] + [(q, q) for q in qs]
        self.quarter_box.selected_value = e.get("quarter") or ""
        self.status_box.items = ["idea", "planned", "active", "done"]
        self.status_box.selected_value = e.get("status") or "planned"
        self.color = e["color"]
        self.colors = d["colors"]
        self.colors_panel.add_event_handler("x-color", self._pick)
        self._colors()
        self.delete_button.visible = bool(epic)

    def _colors(self):
        self.colors_panel.items = [{"c": c, "on": c == self.color} for c in self.colors]

    def _pick(self, color, **event_args):
        self.color = color
        self._colors()
        state.refocus(self.colors_panel, color)

    @handle("cancel_button", "click")
    def cancel_button_click(self, **event_args):
        self.raise_event("x-close-alert", value=None)

    @handle("save_button", "click")
    def save_button_click(self, **event_args):
        fields = {"title": self.name_box.text or "", "body": self.body_box.text or "", "size": self.size_box.selected_value,
                  "quarter": self.quarter_box.selected_value or "", "status": self.status_box.selected_value, "color": self.color}
        if state.call("save_epic", self.crew_id, self.epic_id, fields) is not None:
            state.toast("Epic saved", "ok")
            self.raise_event("x-close-alert", value=True)

    @handle("delete_button", "click")
    def delete_button_click(self, **event_args):
        if confirm("Its cards stay; they just lose the epic.", title="Delete this epic?",
                   buttons=[("Cancel", False), ("Delete", True)], role="app-dialog"):
            if state.call("delete_epic", self.epic_id) is not None:
                self.raise_event("x-close-alert", value=True)
