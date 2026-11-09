from anvil import *
import anvil.server

from ._anvil_designer import CardTemplate
from ... import aa, router, state

PRIOS = [("P0 · drop everything", 0), ("P1 · high", 1), ("P2 · normal", 2), ("P3 · someday", 3)]
STAGES = ["backlog", "ready", "doing", "review", "done"]


class Card(CardTemplate):
    """#card/NOVA-12: one card. Title, description (mini markdown), acceptance criteria, the gates, the agent brief,
    activity + comments, status, details, agent readiness, links, delete. Opening a card switches to the crew its key
    belongs to. Every change saves straight away (update_card) and redraws from the server's reply."""

    def __init__(self, args=(), **properties):
        super().__init__(**properties)
        self.key_text = (args[0] if args else "").upper()
        self.brief_open = False
        crews = aa.load_crews()
        prefix = "-".join(self.key_text.split("-")[:-1])
        cur = aa.current()
        match = [c for c in crews if c["key"] == prefix]
        if match and (not cur or cur["key"] != prefix):
            state.store_set("crew", match[0]["id"])
            cur = match[0]
        if not cur:
            self.redirected = True
            router.go("crew", "new")
            return
        self.crew = cur
        self.acc_panel.add_event_handler("x-tick", self._tick)
        self.acc_panel.add_event_handler("x-remove", self._acc_remove)
        self.links_panel.add_event_handler("x-remove", self._link_remove)
        for b in (self.f_assignee, self.f_type, self.f_priority, self.f_epic, self.f_sprint, self.f_points):
            b.add_event_handler("change", self._field_change)
        state.set_control_attr(self.title_box, "aria-label", "Title")
        state.set_control_attr(self.acc_box, "aria-label", "New acceptance criterion")
        state.set_control_attr(self.comment_box, "aria-label", "Comment")
        state.set_control_attr(self.link_label, "aria-label", "Link label")
        state.set_control_attr(self.link_url, "aria-label", "Link address")
        state.set_control_attr(self.f_reason, "aria-label", "Blocked by what?")
        self.editing = False
        self._load()

    def _load(self):
        r = anvil.server.call("get_card", self.crew["id"], self.key_text)
        ok = bool(r and r.get("ok"))
        self.page.visible = ok
        self.missing.visible = not ok
        if not ok:
            self.missing_title.text = "No card " + self.key_text
            self.missing_text.text = (r or {}).get("error") or ""
            return
        self.st = r
        self._draw()

    # ---------------------------------------------------------------- drawing
    def _draw(self):
        c, d = self.st["card"], self.st
        self.key.text = c["key"]
        self.type_tag.text = c["type"]
        self.type_tag.role = ["aa-type", "t-" + c["type"]]
        self.prio.visible = c["priority"] != 2
        self.prio.text = "P%s" % c["priority"]
        self.prio.role = ["aa-prio", "p%s" % c["priority"]]
        self.fit.visible = bool(c.get("fit"))
        if c.get("fit"):
            self.fit.text = ("⚡ " if c["fit"] == "solo" else "") + aa.FIT[c["fit"]]
            self.fit.role = ["aa-fit", "fit-" + c["fit"]]
        self.blocked_badge.visible = c["blocked"]
        self.demo_badge.visible = c.get("demo", False)
        self.pts.text = "?" if c["points"] is None else str(c["points"])
        self.pts.role = ["aa-pts", "none"] if c["points"] is None else ["aa-pts"]
        self.title_box.text = c["title"]
        # description
        self.desc_extra.text = "%d chars" % len(c["body"])
        self.body_view.visible = not self.editing
        self.body_edit.visible = self.editing
        self.body_md.visible = bool(c["body"])
        self.body_md.content = c["body"]
        self.body_empty.visible = not c["body"]
        # acceptance
        self.acc_extra.text = "%s/%s" % (c["acc_done"], c["acc_total"])
        self.acc_panel.items = [dict(a, i=i) for i, a in enumerate(c["acceptance"])]
        # gates
        g = c.get("gate") or {}
        self.gates_extra.text = ("%s pts%s" % (c["points"], (" // " + g["rung"]) if g.get("rung") else "")) if c["points"] is not None else "unestimated"
        self.gates.cfg = d.get("gates")
        self.gates.answers = c.get("gates") or {}
        self.save_gates.enabled = self.gates.score()["complete"]
        self.points_src.text = {"manual": "Points were set by hand. Running the gates replaces them.",
                                "gates": "Estimated with the gates."}.get(c.get("points_src"), "Not estimated yet.")
        ready = c["readiness"]
        self.brief_extra.text = "⚡ agent-ready" if c["agent_ready"] else "%d/%d ready" % (ready["passed"], ready["total"])
        # activity
        self.act_extra.text = str(len(d["events"]))
        self.events_panel.items = [dict(e, long=True) for e in d["events"]]
        self.events_empty.visible = not d["events"]
        # status
        for s, b in zip(STAGES, [self.s_backlog, self.s_ready, self.s_doing, self.s_review, self.s_done]):
            b.role = ["cd-st", "on"] if c["status"] == s else ["cd-st"]
            state.set_control_attr(b, "aria-pressed", "true" if c["status"] == s else "false")
        self.review_box.visible = c["status"] == "review"
        facts = ["Created  %s by %s" % (state.long_date(c["created"]), c["created_by"])]
        if c.get("started"):
            facts.append("Started  " + state.date_time(c["started"]))
        if c.get("done_at"):
            facts.append("Done  " + state.date_time(c["done_at"]))
        if c.get("age") is not None and c["status"] != "done":
            facts.append("In column  " + ("%d hours" % round(c["age"] * 24) if c["age"] < 1 else "%s days" % c["age"]))
        self.facts.text = "\n".join(facts)
        # details
        a = c.get("assignee")
        self.f_assignee.items = [("Nobody", "")] + [(("🤖 " if p["kind"] == "agent" else "") + p["name"] +
                                                    (" (paused)" if p["kind"] == "agent" and p.get("active") is False else ""),
                                                    p["kind"] + ":" + p["id"]) for p in d["people"]]
        self.f_assignee.selected_value = (a["kind"] + ":" + a["id"]) if a else ""
        self.f_type.items = [(t[0].upper() + t[1:], t) for t in aa.TYPES]
        self.f_type.selected_value = c["type"]
        self.f_priority.items = PRIOS
        self.f_priority.selected_value = c["priority"]
        ep = c.get("epic")
        self.f_epic.items = [("None", "")] + [(e["title"], e["id"]) for e in d["epics"] if e.get("status") != "done" or (ep and ep["id"] == e["id"])]
        self.f_epic.selected_value = ep["id"] if ep else ""
        self.sprint_field.visible = d["level"] >= 2
        sp = c.get("sprint")
        opts = [("Not in a sprint", "")] + [(s["name"] + (" (running)" if s["state"] == "active" else ""), s["id"]) for s in d["sprints"]]
        if sp and sp["state"] == "closed":
            opts.append((sp["name"] + " (closed)", sp["id"]))
        self.f_sprint.items = opts
        self.f_sprint.selected_value = sp["id"] if sp else ""
        self.f_points.items = [("From the gates (%s)" % c["points"] if c.get("points_src") == "gates" else "Not set", "")] + \
            [("%d pts" % p, str(p)) for p in [1, 2, 3, 5, 8, 13, 21]]
        self.f_points.selected_value = str(c["points"]) if c.get("points_src") == "manual" and c["points"] is not None else ""
        self.f_labels.text = ", ".join(c["labels"])
        self.f_blocked.checked = c["blocked"]
        self.f_reason.visible = c["blocked"]
        self.f_reason.text = c.get("blocked_reason") or ""
        for box, label in ((self.f_assignee, "Assignee"), (self.f_type, "Type"), (self.f_priority, "Priority"),
                           (self.f_epic, "Epic"), (self.f_sprint, "Sprint"), (self.f_points, "Points by hand")):
            state.set_control_attr(box, "aria-label", label)
        # readiness + links
        self.ready_extra.text = "%d/%d" % (ready["passed"], ready["total"])
        self.ready_panel.items = ready["checks"]
        self.ready_note.text = ("⚡ An agent can pick this up with next." if c["agent_ready"] else
                                "Agents only pull cards that pass every check and gate as AGENT SOLO or AGENT + HUMAN.")
        self.links_panel.items = [dict(l, i=i) for i, l in enumerate(c["links"])]
        self.links_empty.visible = not c["links"]

    # ---------------------------------------------------------------- saving
    def _save(self, fields, reload_events=True):
        r = state.call("update_card", self.st["card"]["id"], fields)
        if r is None:
            self._draw()
            return False
        if reload_events:
            self._load()
        else:
            self.st["card"] = r["card"]
            self._draw()
        return True

    @handle("title_box", "pressed_enter")
    def title_box_pressed_enter(self, **event_args):
        self._save_title()

    @handle("title_box", "lost_focus")
    def title_box_lost_focus(self, **event_args):
        self._save_title()

    def _save_title(self):
        t = (self.title_box.text or "").strip()
        if t and t != self.st["card"]["title"]:
            if self._save({"title": t}):
                state.toast("Saved", "ok")

    @handle("edit_button", "click")
    def edit_button_click(self, **event_args):
        self.editing = True
        self.body_box.text = self.st["card"]["body"]
        self._draw()
        self.body_box.focus()

    @handle("cancel_edit", "click")
    def cancel_edit_click(self, **event_args):
        self.editing = False
        self._draw()

    @handle("save_body", "click")
    def save_body_click(self, **event_args):
        self.editing = False
        self._save({"body": self.body_box.text or ""})

    def _tick(self, i, done, **event_args):
        acc = [dict(a, done=done) if k == i else a for k, a in enumerate(self.st["card"]["acceptance"])]
        self._save({"acceptance": acc})

    def _acc_remove(self, i, **event_args):
        self._save({"acceptance": [a for k, a in enumerate(self.st["card"]["acceptance"]) if k != i]})

    @handle("acc_box", "pressed_enter")
    def acc_box_pressed_enter(self, **event_args):
        self.acc_add_click()

    @handle("acc_add", "click")
    def acc_add_click(self, **event_args):
        txt = (self.acc_box.text or "").strip()
        if not txt:
            return
        if self._save({"acceptance": self.st["card"]["acceptance"] + [{"text": txt, "done": False}]}):
            self.acc_box.text = ""
            self.acc_box.focus()

    @handle("gates", "gates_change")
    def gates_change(self, answers=None, score=None, **event_args):
        self.save_gates.enabled = bool(score and score["complete"])

    @handle("save_gates", "click")
    def save_gates_click(self, **event_args):
        r = state.call("estimate_card", self.st["card"]["id"], self.gates.answers)
        if r:
            state.toast("%s points // %s" % (r["gate"]["points"], r["gate"]["rung"]), "ok")
            self._load()

    def _brief(self):
        r = state.call("agent_brief", self.st["card"]["id"], aa.api_base())
        return r["markdown"] if r else None

    @handle("copy_brief", "click")
    def copy_brief_click(self, **event_args):
        md = self._brief()
        if md:
            aa.copy(md, "Brief copied: paste it into your AI tool")

    @handle("show_brief", "click")
    def show_brief_click(self, **event_args):
        self.brief_open = not self.brief_open
        self.show_brief.text = "Hide" if self.brief_open else "Preview"
        if self.brief_open:
            self.brief_text.text = self._brief() or ""
        self.brief_text.visible = self.brief_open

    @handle("comment_button", "click")
    def comment_button_click(self, **event_args):
        v = (self.comment_box.text or "").strip()
        if not v:
            return
        if state.call("add_comment", self.st["card"]["id"], v) is not None:
            self.comment_box.text = ""
            self._load()

    def _move(self, to):
        c = self.st["card"]
        if to == c["status"]:
            return
        r = state.call("move_card", c["id"], to, False)
        if r is not None:
            over = bool(r.get("over_wip"))
            state.toast("%s → %s%s" % (c["key"], aa.STATUS[to], " (over the WIP limit!)" if over else ""), "error" if over else "ok")
            self._load()

    @handle("s_backlog", "click")
    def s_backlog_click(self, **event_args):
        self._move("backlog")

    @handle("s_ready", "click")
    def s_ready_click(self, **event_args):
        self._move("ready")

    @handle("s_doing", "click")
    def s_doing_click(self, **event_args):
        self._move("doing")

    @handle("s_review", "click")
    def s_review_click(self, **event_args):
        self._move("review")

    @handle("s_done", "click")
    def s_done_click(self, **event_args):
        self._move("done")

    @handle("approve", "click")
    def approve_click(self, **event_args):
        self._move("done")

    @handle("send_back", "click")
    def send_back_click(self, **event_args):
        self._move("doing")

    def _field_change(self, **event_args):
        sender = event_args["sender"]
        v = sender.selected_value
        if sender is self.f_assignee:
            kind, _, pid = (v or "").partition(":")
            self._save({"assignee": {"kind": kind, "id": pid} if v else None})
        elif sender is self.f_priority:
            self._save({"priority": int(v)})
        elif sender is self.f_points:
            self._save({"points": int(v) if v else None})
        elif sender is self.f_type:
            self._save({"type": v})
        elif sender is self.f_epic:
            self._save({"epic_id": v or None})
        elif sender is self.f_sprint:
            self._save({"sprint_id": v or None})

    @handle("f_labels", "lost_focus")
    def f_labels_lost_focus(self, **event_args):
        labels = [x.strip() for x in (self.f_labels.text or "").split(",") if x.strip()]
        if labels != self.st["card"]["labels"]:
            self._save({"labels": labels})

    @handle("f_labels", "pressed_enter")
    def f_labels_pressed_enter(self, **event_args):
        self.f_labels_lost_focus()

    @handle("f_blocked", "change")
    def f_blocked_change(self, **event_args):
        self._save({"blocked": self.f_blocked.checked, "blocked_reason": ""})

    @handle("f_reason", "lost_focus")
    def f_reason_lost_focus(self, **event_args):
        if (self.f_reason.text or "") != (self.st["card"].get("blocked_reason") or ""):
            self._save({"blocked": True, "blocked_reason": self.f_reason.text or ""})

    def _link_remove(self, i, **event_args):
        self._save({"links": [l for k, l in enumerate(self.st["card"]["links"]) if k != i]})

    @handle("link_add", "click")
    def link_add_click(self, **event_args):
        url = (self.link_url.text or "").strip()
        if not (url.startswith("https://") or url.startswith("http://")):
            state.toast("Links start with https://", "error")
            return
        if self._save({"links": self.st["card"]["links"] + [{"label": self.link_label.text or "", "url": url}]}):
            self.link_label.text = self.link_url.text = ""

    @handle("delete_button", "click")
    def delete_button_click(self, **event_args):
        c = self.st["card"]
        if confirm("The card and its activity are deleted for the whole crew.", title="Delete %s?" % c["key"],
                   buttons=[("Cancel", False), ("Delete", True)], role="app-dialog"):
            if state.call("delete_card", c["id"]) is not None:
                state.toast("Deleted", "ok")
                router.go("backlog")
