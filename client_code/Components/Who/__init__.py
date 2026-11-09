from anvil import *

from ._anvil_designer import WhoTemplate
from ... import state


class Who(WhoTemplate):
    """Avatar for a card's assignee, an event's author or a crew member (was AA.who)."""

    def __init__(self, **properties):
        self._person, self._size, self._ready = None, "", False
        super().__init__(**properties)
        self._ready = True
        self._draw()

    def _draw(self):
        if not self._ready:
            return
        p = self._person
        agent = bool(p and p.get("kind") == "agent")
        self.box.classes.update({"none": not p, "agent": agent, "lg": self._size == "lg"})
        self.bot.visible = agent
        self.letters.visible = not agent
        self.letters.text = state.initials(p.get("name")) if p and not agent else ("" if p else "?")
        self.box.style["background"] = (p.get("color") or "#00e5ff") if agent else ""
        state.set_attr(self.box, "title", (p["name"] + (" (AI agent)" if agent else "")) if p else "Nobody yet")

    @property
    def person(self):
        return self._person

    @person.setter
    def person(self, value):
        self._person = value or None
        self._draw()

    @property
    def size(self):
        return self._size

    @size.setter
    def size(self, value):
        self._size = value or ""
        self._draw()
