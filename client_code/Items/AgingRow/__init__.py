from anvil import *

from ._anvil_designer import AgingRowTemplate
from ... import aa, router, state


class AgingRow(AgingRowTemplate):
    """A card in progress and how long it has sat there. item = {key, title, status, age, agent}."""

    def __init__(self, **properties):
        super().__init__(**properties)
        a = self.item
        self.title.text = ("🤖 " if a.get("agent") else "") + a["title"]
        state.set_attr(self.link, "href", router.href("card", a["key"]))
        self.age.text = aa.age_text(a["age"])
        cls = "bad" if a["age"] > 5 else "warn" if a["age"] > 2.5 else ""
        self.age.role = ["in-d", cls] if cls else ["in-d"]
