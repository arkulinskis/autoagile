from anvil import *

from ._anvil_designer import CrewTemplate
from ... import aa, router, state

STAGES = ["ready", "doing", "review", "done"]


class Crew(CrewTemplate):
    """#crew: the crew's settings: name + mission, join code, members (make owner, remove), WIP limits, sprint length,
    Definition of Done, board columns (split a stage), alerts (webhook + email digest), leave or delete.
    #crew/new and #crew/join are Pages/CrewStart."""

    def __init__(self, args=(), **properties):
        super().__init__(**properties)
        self.crew = aa.need_crew(self)
        if not self.crew:
            return
        self.cols: list = []
        self.members_panel.add_event_handler("x-member", self._member)
        self.cols_panel.add_event_handler("x-col", self._col)
        self.sprint_days.items = [("1 week", 7), ("2 weeks", 14), ("3 weeks", 21), ("4 weeks", 28)]
        for box, label in ((self.name_box, "Name"), (self.mission_box, "Mission"), (self.wip_ready, "Ready WIP limit"),
                           (self.wip_doing, "Doing WIP limit"), (self.wip_review, "Review WIP limit"), (self.dod_box, "Definition of Done"),
                           (self.webhook, "Webhook"), (self.review_hours, "Review waits over (hours)"), (self.confirm_box, "Type the card prefix")):
            state.set_control_attr(box, "aria-label", label)
        self._load()

    def _load(self):
        r = state.call("get_crew", self.crew["id"])
        if not r:
            return
        c = self.c = r["crew"]
        self.title.text = c["name"]
        state.heading(self.title, 1)
        self.sub.text = "%s // Level %d %s · you are %s" % (c["key"], c["level"], c["level_info"]["name"],
                                                         "a guest in this demo crew" if c["role"] == "sandbox" else "the " + c["role"])
        self.demo_note.visible = c["demo"]
        self.name_box.text, self.mission_box.text = c["name"], c["mission"]
        self.name_box.enabled = self.mission_box.enabled = c["can_admin"]
        self.prefix.text = "Card prefix: %s (fixed once cards exist)." % c["key"]
        self.basic_save.visible = c["can_admin"]
        self.owner_only.visible = not c["can_admin"]
        self.invite_win.visible = bool(c.get("join_code"))
        self.code.text = c.get("join_code") or ""
        self.new_code.visible = c["can_admin"]
        people = [dict(m, kind="user", can=c["can_admin"] and not m["me"] and not c["demo"]) for m in c["members"]] + \
                 [dict(a, kind="agent", kind_name=a["kind"]) for a in c["agents"]]
        self.members_panel.items = people
        self.people_extra.text = "%d total" % len(people)
        self.wip_ready.text, self.wip_doing.text, self.wip_review.text = c["wip"]["ready"], c["wip"]["doing"], c["wip"]["review"]
        self.sprint_days.selected_value = c["sprint_days"]
        self.dod_box.text = "\n".join(c["dod"])
        self.cols = [dict(x) for x in c["columns"]]
        self._draw_cols()
        self.demo_leave.visible = c["demo"]
        self.owner_delete.visible = not c["demo"] and c["role"] == "owner"
        self.leave_button.visible = not c["demo"] and c["role"] != "owner"
        self.delete_text.text = "Deleting removes every card, sprint, epic, agent and log of this crew. Type %s to confirm." % c["key"]
        self.confirm_box.placeholder = c["key"]
        self._alerts()

    # ---- basics + invite
    @handle("save_basic", "click")
    def save_basic_click(self, **event_args):
        if state.call("update_crew", self.c["id"], {"name": self.name_box.text or "", "mission": self.mission_box.text or ""}) is not None:
            state.toast("Saved", "ok")
            aa.load_crews(True)
            router.refresh_shell()

    @handle("copy_code", "click")
    def copy_code_click(self, **event_args):
        aa.copy(self.code.text)

    @handle("new_code", "click")
    def new_code_click(self, **event_args):
        if confirm("The old code stops working.", title="New join code?", buttons=[("Cancel", False), ("New code", True)], role="app-dialog"):
            if state.call("new_join_code", self.c["id"]) is not None:
                self._load()

    def _member(self, action, user_id, **event_args):
        if action == "remove":
            if confirm("Their cards become unassigned.", title="Remove this person?", buttons=[("Cancel", False), ("Remove", True)], role="app-dialog"):
                if state.call("remove_member", self.c["id"], user_id) is not None:
                    self._load()
        elif action == "owner":
            if confirm("They become the owner and you become a member.", title="Hand over the crew?",
                       buttons=[("Cancel", False), ("Hand over", True)], role="app-dialog"):
                if state.call("make_owner", self.c["id"], user_id) is not None:
                    aa.load_crews(True)
                    self._load()

    # ---- flow rules
    @handle("save_flow", "click")
    def save_flow_click(self, **event_args):
        fields = {"wip": {"ready": self.wip_ready.text, "doing": self.wip_doing.text, "review": self.wip_review.text},
                  "sprint_days": int(self.sprint_days.selected_value),
                  "dod": [x.strip() for x in (self.dod_box.text or "").split("\n") if x.strip()]}
        if state.call("update_crew", self.c["id"], fields) is not None:
            state.toast("Flow rules saved", "ok")

    # ---- board columns
    def _draw_cols(self):
        self.cols = [x for s in STAGES for x in self.cols if x["stage"] == s]
        rows = []
        for i, x in enumerate(self.cols):
            same = len([y for y in self.cols if y["stage"] == x["stage"]])
            rows.append({"col": x, "i": i, "sub": same > 1, "can_up": i > 0 and self.cols[i - 1]["stage"] == x["stage"]})
        self.cols_panel.items = rows
        self.cols_extra.text = "%d columns" % len(self.cols)

    def _col(self, action, i, value=("", None), **event_args):
        if action == "set":
            field, v = value
            self.cols[i][field] = v
            if field == "stage":
                self._draw_cols()
        elif action == "up" and i > 0:
            self.cols[i - 1], self.cols[i] = self.cols[i], self.cols[i - 1]
            self._draw_cols()
        elif action == "del":
            del self.cols[i]
            self._draw_cols()

    @handle("add_col", "click")
    def add_col_click(self, **event_args):
        self.cols.append({"id": "", "name": "Test", "stage": "doing", "wip": None})
        self._draw_cols()

    @handle("save_cols", "click")
    def save_cols_click(self, **event_args):
        r = state.call("save_columns", self.c["id"], self.cols)
        if r:
            self.cols = [dict(x) for x in r["columns"]]
            self._draw_cols()
            state.toast("Columns saved. The board follows.", "ok")

    # ---- alerts
    def _alerts(self):
        a = state.call("get_alerts", self.c["id"])
        if not a:
            return
        self.a = a
        s = a["settings"]
        edit = a["can_edit"] and not a["demo"]
        self.alert_form.visible = edit
        self.alert_info.visible = not edit
        self.alert_info.text = ("Demo crews keep an alert history but never send anything." if a["demo"] else
                                "The owner connects a webhook" + (" (one is connected)." if s["webhook"] else " (none yet)."))
        if edit:
            self.webhook.text = s["webhook"]
            self.format_box.items = [(f["label"], f["id"]) for f in a["formats"]]
            self.format_box.selected_value = s["format"]
            self.review_hours.text = s["review_hours"]
            self.kinds = dict(s["kinds"])
            self.kinds_panel.items = [{"id": k["id"], "label": k["label"], "on": bool(self.kinds.get(k["id"])), "host": self} for k in a["kinds"]]
        self.notify_box.visible = a["member"] and not a["demo"]
        self.notify_box.checked = a["notify"]
        labels = {k["id"]: k["label"] for k in a["kinds"]}
        labels["test"] = "test"
        self.hist_panel.items = [dict(h, kind_label=labels.get(h["kind"], h["kind"])) for h in a["history"][:8]]
        self.hist_empty.visible = not a["history"]

    def set_kind(self, kind, on):
        self.kinds[kind] = on

    @handle("save_alerts", "click")
    def save_alerts_click(self, **event_args):
        try:
            hours = int(self.review_hours.text or 24)
        except (TypeError, ValueError):
            hours = 24
        fields = {"webhook": self.webhook.text or "", "format": self.format_box.selected_value, "review_hours": hours, "kinds": self.kinds}
        if state.call("save_alerts", self.c["id"], fields) is not None:
            state.toast("Alert settings saved", "ok")
            self._alerts()

    @handle("test_alert", "click")
    def test_alert_click(self, **event_args):
        if state.call("test_alerts", self.c["id"]) is not None:
            state.toast("Test sent. Check your channel.", "ok")
            self._alerts()

    @handle("notify_box", "change")
    def notify_box_change(self, **event_args):
        r = state.call("set_notify", self.c["id"], self.notify_box.checked)
        if r:
            state.toast(("You will get alert emails for " + self.c["key"]) if r.get("notify") else "Alert emails off", "ok")

    # ---- leave / delete
    @handle("delete_button", "click")
    def delete_button_click(self, **event_args):
        c = self.c
        if confirm("This cannot be undone.", title="Delete %s for good?" % c["name"], buttons=[("Cancel", False), ("Delete", True)], role="app-dialog"):
            if state.call("delete_crew", c["id"], self.confirm_box.text or "") is not None:
                state.store_set("crew", None)
                aa.load_crews(True)
                state.toast("Crew deleted", "ok")
                router.go("deck")

    @handle("leave_button", "click")
    def leave_button_click(self, **event_args):
        if confirm("", title="Leave %s?" % self.c["name"], buttons=[("Cancel", False), ("Leave", True)], role="app-dialog"):
            if state.call("leave_crew", self.c["id"]) is not None:
                state.store_set("crew", None)
                aa.load_crews(True)
                router.go("deck")
