from anvil import *

from ._anvil_designer import StandupPersonTemplate
from ... import state

SECTIONS = [("shipped", "SHIPPED", "good"), ("review", "IN REVIEW", "warn"), ("doing", "DOING", ""), ("blocked", "BLOCKED", "bad")]


class StandupPerson(StandupPersonTemplate):
    """One person or agent in the standup: their shipped / in review / doing / blocked cards and latest note.
    item = a person block from Standup.build, or {quiet_list: [names]} for the closing "Quiet" box."""

    def __init__(self, **properties):
        super().__init__(**properties)
        p = self.item
        if p.get("quiet_list") is not None:
            self.kind.text = "Quiet"
            self.count.text = str(len(p["quiet_list"]))
            self.head_box.visible = self.lines_panel.visible = self.note_box.visible = False
            self.quiet.text = "No moves: " + ", ".join(p["quiet_list"]) + ". Fine for a day; worth a word if it lasts."
            return
        self.quiet.visible = False
        w = p["who"]
        self.who.person = w
        self.pname.text = w["name"]
        self.kind.text = (w.get("agent_kind") or "AI agent") if w["kind"] == "agent" else "Human"
        self.count.text = "%d moves" % p["events"] if p["events"] != 1 else "1 move"
        lines = []
        for key, label, cls in SECTIONS:
            for x in p[key]:
                sub = label
                c = cls
                if key == "doing" and x.get("stuck"):
                    sub, c = "STUCK %dd" % int(x["age"] or 0), "stuck"
                elif key == "blocked" and x.get("blocked_reason"):
                    sub = "BLOCKED: " + x["blocked_reason"]
                lines.append({"key": x["key"], "text": x["title"], "sub": sub, "cls": c})
        self.lines_panel.items = lines
        self.lines_panel.visible = bool(lines)
        n = p.get("note")
        self.note_box.visible = bool(n)
        if n:
            self.note_head.text = "Latest note%s · %s" % ((" on " + n["key"]) if n.get("key") else "", state.ago(n["at"]))
            self.note.text = n["text"]
