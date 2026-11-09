from anvil import *

from ._anvil_designer import CrewAdminRowTemplate


class CrewAdminRow(CrewAdminRowTemplate):
    """Admin → Crews: one crew with its size (no card contents). Demo crews are managed in Demo data."""

    def __init__(self, **properties):
        super().__init__(**properties)
        c = self.item
        self.cname.text = "%s %s" % (c["key"], c["name"])
        self.demo.visible = c["demo"]
        self.level.text = str(c["level"])
        self.size.text = "%s people · %s agents · %s cards" % (c["members"], c["agents"], c["cards"])
        self.delete.visible = not c["demo"]

    @handle("delete", "click")
    def delete_click(self, **event_args):
        self.parent.raise_event("x-delete", crew_id=self.item["id"])
