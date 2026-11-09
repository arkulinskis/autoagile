from anvil import *
import anvil.js
from anvil.js import window

from ._anvil_designer import PaletteTemplate
from ... import aa, state

STATUS = {"backlog": "Backlog", "ready": "Ready", "doing": "Doing", "review": "Review", "done": "Done"}


class Palette(PaletteTemplate):
    """Ctrl K: jump to a page or a card, add a card by typing its title, switch crew. Arrow keys pick, Enter goes.
    Closes with (kind, value): ("go", "board"), ("card", "NOVA-12"), ("add", "title"), ("switch", None), or None."""

    def __init__(self, go=(), **properties):
        super().__init__(**properties)
        self.go = list(go)
        self.sel = 0
        self.items_now = []
        self.seq = 0
        self.timer = None
        self.crew = aa.current()
        self.foot.text = "↑↓ pick · Enter go · Esc close · " + " · ".join("%s %s" % (g[3], g[1]) for g in self.go if g[3])
        self.list_panel.add_event_handler("x-run", self._run_index)
        state.set_control_attr(self.query, "aria-label", "Search")
        state.set_control_attr(self.query, "autocomplete", "off")
        anvil.js.get_dom_node(self.query).addEventListener("keydown", anvil.js.report_exceptions(self._keydown))
        self._build([])

    @handle("", "show")
    def form_show(self, **event_args):
        window.setTimeout(lambda: self.query.focus(), 60)

    def _build(self, cards):
        q = (self.query.text or "").strip()
        lq = q.lower()
        items: list = [{"label": g[1], "icon": g[2], "go": g[0], "hint": g[3]} for g in self.go if not lq or lq in g[1].lower()]
        for c in cards or []:
            items.append({"key": c["key"], "label": c["title"], "hint": STATUS.get(c["status"], ""), "card": c["key"]})
        if len(q) >= 3 and self.crew:
            items.append({"label": "New card: " + q, "icon": "plus", "add": q, "hint": self.crew["key"] + " backlog"})
        if "crew" in lq or "switch" in lq:
            items.append({"label": "Switch crew", "icon": "users", "sw": True, "hint": ""})
        self.sel = min(self.sel, max(0, len(items) - 1))
        self.items_now = items
        self._draw()

    def _draw(self):
        self.list_panel.items = [dict(it, i=i, on=i == self.sel) for i, it in enumerate(self.items_now)]
        self.nothing.visible = not self.items_now
        on = anvil.js.get_dom_node(self.list_panel).querySelector(".on")
        if on:
            on.scrollIntoView({"block": "nearest"})

    @handle("query", "change")
    def query_change(self, **event_args):
        self.sel = 0
        self._build([])
        q = (self.query.text or "").strip()
        self.seq += 1
        if self.timer:
            window.clearTimeout(self.timer)
        if q and self.crew:
            my = self.seq
            self.timer = window.setTimeout(lambda: self._search(q, my), 160)

    def _search(self, q, my):
        r = state.call_quiet("search_cards", self.crew["id"], q)
        if my == self.seq and r and r.get("ok") is not False:
            self._build(r.get("cards") or [])

    def _keydown(self, e):
        if getattr(e, "key", None) == "ArrowDown":
            e.preventDefault()
            self.sel = min(len(self.items_now) - 1, self.sel + 1)
            self._draw()
        elif getattr(e, "key", None) == "ArrowUp":
            e.preventDefault()
            self.sel = max(0, self.sel - 1)
            self._draw()
        elif getattr(e, "key", None) == "Enter":
            e.preventDefault()
            self._run_index(self.sel)

    def _run_index(self, i, **event_args):
        if i is None or i >= len(self.items_now):
            return
        it = self.items_now[i]
        if it.get("go"):
            r = ("go", it["go"])
        elif it.get("card"):
            r = ("card", it["card"])
        elif it.get("sw"):
            r = ("switch", None)
        else:
            r = ("add", it["add"])
        self.raise_event("x-close-alert", value=r)
