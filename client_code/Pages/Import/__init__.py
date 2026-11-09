from anvil import *
import json

import anvil.js

from ._anvil_designer import ImportTemplate
from ... import aa, state

SOURCES = ["jira", "trello", "csv", "autoagile"]
HELP = {"jira": "In Jira: Filters → your issues → Export → Export CSV (all fields). Dates, labels, comments, epics and story points come along.",
        "trello": "In Trello: board Menu → Print, export and share → Export as JSON. Lists become columns; comments and labels come along.",
        "csv": "Any spreadsheet saved as CSV: Asana, monday.com, Linear, GitHub Projects, Podio, Notion. You choose which column is what.",
        "autoagile": "A file from Export, from this or another AutoAgile crew."}
FROM = {"jira": "Jira", "trello": "Trello", "csv": "CSV", "autoagile": "AutoAgile"}


class Import(ImportTemplate):
    """#import: bring history in (Jira CSV, Trello JSON, any CSV, AutoAgile export), map fields and statuses, preview,
    import in batches of 200; export the whole crew as JSON or a Jira-style CSV. The engine (AA.imp) reads the file in the
    browser and keeps it; this page keeps the mapping."""

    def __init__(self, args=(), **properties):
        super().__init__(**properties)
        self.crew = aa.need_crew(self)
        if not self.crew:
            return
        self.src = state.store_get("im.src", "jira")
        self.parsed: dict = {}
        self.map: dict = {}
        self.smap: dict = {}
        self.result: dict = {}
        r = state.call("get_crew", self.crew["id"])
        self.cols = r["crew"]["columns"] if r else []
        self.sub.text = "%s // Bring your history. Leave whenever you like." % self.crew["key"]
        self.demo_note.visible = bool(self.crew.get("demo"))
        self.map_panel.add_event_handler("x-map", self._set_map)
        self.status_panel.add_event_handler("x-smap", self._set_smap)
        state.set_control_attr(self.paste_box, "aria-label", "Paste CSV or JSON")
        state.set_control_attr(self.link_box, "aria-label", "Link back to Jira")
        aa.AA.imp.clear()
        aa.AA.imp.dropzone(self.dom_nodes["zone"], self.dom_nodes["file"], anvil.js.report_exceptions(self._read))
        self._draw()

    # ---- reading
    def _read(self, text, name):
        try:
            p = json.loads(aa.AA.imp.read(text, self.src))
        except Exception as e:
            msg = str(e)
            state.toast(msg.split(": ", 1)[-1] if msg else "Could not read that file.", "error")
            return
        if p["kind"] != self.src:
            self.src = p["kind"]
            state.store_set("im.src", self.src)
        self.parsed = p
        self.map = dict(p["map"] or {})
        self.smap = {}
        self.result = {}
        self._guess()
        self._draw()
        state.toast("Read %s: %d cards" % (name or "the text", len(self._items())), "ok")

    def _guess(self):
        self.smap = json.loads(aa.AA.imp.guess(json.dumps(self.map), self.link_box.text or "", json.dumps(self.smap), json.dumps(self.cols)))

    def _items(self):
        if not self.parsed:
            return []
        return json.loads(aa.AA.imp.items(json.dumps(self.map), self.link_box.text or "", json.dumps(self.smap)))

    # ---- drawing
    def _draw(self):
        for s, b in zip(SOURCES, [self.s_jira, self.s_trello, self.s_csv, self.s_autoagile]):
            b.role = ["seg", "on"] if s == self.src else ["seg"]
            state.set_control_attr(b, "aria-pressed", "true" if s == self.src else "false")
        self.src_help.text = HELP[self.src]
        p = self.parsed
        self.map_win.visible = self.preview_win.visible = bool(p)
        if not p:
            return
        its = self._items()
        self.map_extra.text = "%d cards" % len(its)
        self.parsed_note.text = p["note"] or ("%d cards found%s." % (len(its), " (epics become AutoAgile epics)" if p["kind"] == "jira" else ""))
        heads = p.get("headers")
        self.map_panel.visible = bool(heads)
        if heads:
            self.map_panel.items = [{"id": f[0], "label": f[1], "headers": heads, "value": self.map.get(f[0]) or ""} for f in aa.py(aa.AA.imp.FIELDS)]
        srcs = json.loads(aa.AA.imp.sources(json.dumps(self.map), self.link_box.text or ""))
        targets = [("Backlog", "backlog")] + [(c["name"] + ((" (%s)" % aa.STATUS[c["stage"]]) if c["name"].lower() != c["stage"] else ""), c["id"]) for c in self.cols]
        self.status_panel.items = [{"src": s[0], "n": s[1], "targets": targets, "value": self.smap.get(s[0]) or "backlog"} for s in srcs]
        self.link_field.visible = p["kind"] == "jira"
        names = {c["id"]: c["name"] for c in self.cols}
        self.preview_panel.items = [dict(it, col=("Backlog" if it["status"] == "backlog" else names.get(it["status"], it["status"]))) for it in its[:6]]
        has_title = bool(self.map.get("title") or p.get("has_items"))
        self.need_title.visible = not has_title
        self.import_button.text = "Import %d cards into %s" % (len(its), self.crew["key"])
        self.import_button.enabled = has_title and not self.crew.get("demo") and bool(its)
        self.bar.visible = False
        r = self.result
        self.result_box.visible = bool(r)
        if r:
            self.result_panel.items = [{"value": r["created"], "label": "cards imported"}, {"value": r["duplicates"], "label": "already there, skipped", "cls": "cyan"},
                                       {"value": r["epics_created"], "label": "new epics", "cls": "pink"}, {"value": r["comments"], "label": "comments", "cls": "amber"}]
            self.unmatched.visible = bool(r["unmatched"])
            self.unmatched.text = "Not in this crew, so left unassigned (their name is in the card): %s. Invite them, then assign." % ", ".join(r["unmatched"])
            self.invalid.visible = bool(r["invalid"])
            self.invalid.text = "%d rows had no title and were skipped." % r["invalid"]

    # ---- controls
    def _source(self, s):
        self.src = s
        state.store_set("im.src", s)
        self.parsed, self.result = {}, {}
        aa.AA.imp.clear()
        self._draw()

    @handle("s_jira", "click")
    def s_jira_click(self, **event_args):
        self._source("jira")

    @handle("s_trello", "click")
    def s_trello_click(self, **event_args):
        self._source("trello")

    @handle("s_csv", "click")
    def s_csv_click(self, **event_args):
        self._source("csv")

    @handle("s_autoagile", "click")
    def s_autoagile_click(self, **event_args):
        self._source("autoagile")

    @handle("read_paste", "click")
    def read_paste_click(self, **event_args):
        self._read(self.paste_box.text or "", "the pasted text")

    def _set_map(self, field, value, **event_args):
        self.map[field] = value
        if field == "status":
            self._guess()
        self._draw()

    def _set_smap(self, src, value, **event_args):
        self.smap[src] = value
        self._draw()

    @handle("link_box", "lost_focus")
    def link_box_lost_focus(self, **event_args):
        self._draw()

    @handle("import_button", "click")
    def import_button_click(self, **event_args):
        items = self._items()
        total = {"created": 0, "duplicates": 0, "invalid": 0, "epics_created": 0, "comments": 0, "unmatched": []}
        opts = {"history": self.opt_history.checked, "epics": self.opt_epics.checked, "from": FROM[self.parsed["kind"]]}
        self.bar.visible = True
        self.import_button.enabled = False
        done = 0
        for i in range(0, len(items), 200):
            batch = items[i:i + 200]
            r = state.call("import_cards", self.crew["id"], batch, opts)
            if not r:
                break
            for k in ("created", "duplicates", "invalid", "epics_created", "comments"):
                total[k] += r[k]
            for u in r["unmatched"]:
                if u not in total["unmatched"]:
                    total["unmatched"].append(u)
            done += len(batch)
            self.bar_fill.style["width"] = "%d%%" % round(100.0 * done / max(1, len(items)))
        self.result = total
        self._draw()
        if total["created"]:
            aa.rave("IMPORTED", "%d cards into %s" % (total["created"], self.crew["key"]))

    def _export(self, kind):
        r = state.call("export_crew", self.crew["id"])
        if not r:
            return
        x = r["export"]
        day = x["exported"][:10]
        text = json.dumps(x)
        if kind == "json":
            aa.AA.imp.exportJSON(text, "%s-autoagile-%s.json" % (self.crew["key"], day))
        else:
            aa.AA.imp.exportCSV(text, "%s-cards-%s.csv" % (self.crew["key"], day))

    @handle("export_json", "click")
    def export_json_click(self, **event_args):
        self._export("json")

    @handle("export_csv", "click")
    def export_csv_click(self, **event_args):
        self._export("csv")
