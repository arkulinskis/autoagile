from anvil import *

from ._anvil_designer import AgentDialogTemplate
from ... import state


class AgentDialog(AgentDialogTemplate):
    """Add an AI developer (closes with the server reply incl. its token) or edit one (closes with True)."""

    def __init__(self, **properties):
        agent, kinds, crew_id = properties.pop("agent"), properties.pop("kinds"), properties.pop("crew_id", "")
        super().__init__(**properties)
        self.agent, self.crew_id = agent, crew_id
        self.title.text = ("Edit " + agent["name"]) if agent else "Add an AI developer"
        state.heading(self.title, 2)
        self.intro.visible = self.wip_hint.visible = not agent
        self.name_box.text = agent["name"] if agent else ""
        self.kind_box.items = list(kinds)
        if agent and agent["kind"] in kinds:
            self.kind_box.selected_value = agent["kind"]
        self.wip_box.items = [(str(n), n) for n in ([1, 2, 3, 4, 5] if agent else [1, 2, 3])]
        self.wip_box.selected_value = agent["max_wip"] if agent else 1
        self.remove_button.visible = bool(agent)
        self.save_button.text = "Save" if agent else "Add agent"
        self.save_button.role = ["btn", "btn-primary"] if agent else ["btn", "btn-primary", "ic-plus"]

    @handle("cancel_button", "click")
    def cancel_button_click(self, **event_args):
        self.raise_event("x-close-alert", value=None)

    @handle("save_button", "click")
    def save_button_click(self, **event_args):
        name = (self.name_box.text or "").strip()
        if not name:
            state.toast("Give the agent a name.", "error")
            return
        if self.agent:
            r = state.call("update_agent", self.agent["id"], {"name": name, "kind": self.kind_box.selected_value, "max_wip": int(self.wip_box.selected_value)})
            if r is not None:
                self.raise_event("x-close-alert", value=True)
        else:
            r = state.call("create_agent", self.crew_id, name, self.kind_box.selected_value, int(self.wip_box.selected_value))
            if r:
                self.raise_event("x-close-alert", value=r)

    @handle("remove_button", "click")
    def remove_button_click(self, **event_args):
        a = self.agent
        if confirm("Its cards in Doing go back to Ready. Its log stays on the cards.", title="Remove %s?" % a["name"],
                   buttons=[("Cancel", False), ("Remove", True)], role="app-dialog"):
            if state.call("delete_agent", a["id"]) is not None:
                self.raise_event("x-close-alert", value=True)
