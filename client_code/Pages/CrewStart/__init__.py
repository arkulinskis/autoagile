from anvil import *
import re

from ._anvil_designer import CrewStartTemplate
from ... import aa, router, state


class CrewStart(CrewStartTemplate):
    """#crew/new and #crew/join: start a crew (name, card prefix, mission, starting level) or join one with a code."""

    def __init__(self, args=(), **properties):
        super().__init__(**properties)
        self.join = bool(args) and args[0] == "join"
        self.title.text = "Join a crew" if self.join else "Start a crew"
        state.heading(self.title, 1)
        self.sub.text = ("Ask a crew member for the 6-character code on their Crew page." if self.join else
                         "A crew is one team with one board, humans and AI agents together.")
        self.switch_text.text = "Start a crew instead" if self.join else "I have a code"
        state.set_attr(self.switch_link, "href", "#crew/new" if self.join else "#crew/join")
        self.join_win.visible = self.join
        self.new_win.visible = not self.join
        self.key_touched = False
        for box, label in ((self.code_box, "Crew code"), (self.name_box, "Crew name"), (self.key_box, "Card prefix"), (self.mission_box, "Mission")):
            state.set_control_attr(box, "aria-label", label)
        state.set_control_attr(self.code_box, "autocomplete", "off")

    @handle("name_box", "change")
    def name_box_change(self, **event_args):
        if not self.key_touched:
            self.key_box.text = re.sub(r"[^A-Z]", "", (self.name_box.text or "").upper())[:4]

    @handle("key_box", "change")
    def key_box_change(self, **event_args):
        self.key_touched = True

    def _done(self, r):
        aa.load_crews(True)
        aa.set_crew(r["crew"]["id"])
        aa.rave("WELCOME IN" if self.join else "CREW ONLINE", "%s // %s" % (r["crew"]["key"], r["crew"]["name"]))
        router.go("deck" if self.join else "backlog")

    @handle("code_box", "pressed_enter")
    def code_box_pressed_enter(self, **event_args):
        self.join_button_click()

    @handle("join_button", "click")
    def join_button_click(self, **event_args):
        r = state.call("join_crew", (self.code_box.text or "").strip().upper())
        if r:
            self._done(r)

    @handle("create_button", "click")
    def create_button_click(self, **event_args):
        lvl = 2 if self.lvl2.selected else 1
        r = state.call("create_crew", self.name_box.text or "", self.key_box.text or "", self.mission_box.text or "", lvl)
        if r:
            self._done(r)
