from anvil import *

from ._anvil_designer import MemberRowTemplate
from ... import state


class MemberRow(MemberRowTemplate):
    """A person or agent in the crew. item = member (kind user, can = may manage) or agent (kind agent)."""

    def __init__(self, **properties):
        super().__init__(**properties)
        m = self.item
        agent = m["kind"] == "agent"
        self.who.person = {"kind": "agent", "name": m["name"], "color": m.get("color")} if agent else {"kind": "user", "name": m["name"]}
        self.mname.text = m["name"] + (" (you)" if m.get("me") else "")
        self.ai.visible = agent
        if agent:
            self.meta.text = "%s · WIP %s" % (m.get("kind_name") or "", m["max_wip"])
        else:
            self.meta.text = m["role"] + ((" · joined " + state.long_date(m["joined"])) if m.get("joined") else "")
        can = bool(m.get("can"))
        self.owner.visible = self.remove.visible = can and not agent
        self.manage.visible = agent

    @handle("owner", "click")
    def owner_click(self, **event_args):
        self.parent.raise_event("x-member", action="owner", user_id=self.item["id"])

    @handle("remove", "click")
    def remove_click(self, **event_args):
        self.parent.raise_event("x-member", action="remove", user_id=self.item["id"])
