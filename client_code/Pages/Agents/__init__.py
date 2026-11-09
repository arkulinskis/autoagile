from anvil import *
import json

import anvil.js
from anvil.js import window

from ._anvil_designer import AgentsTemplate
from ... import aa, state


def snippet(base, key):
    return ("## AutoAgile (task board)\n\nThis repo's work is tracked on AutoAgile, crew " + key + ". Your token is in the env var AUTOAGILE_TOKEN.\n"
            "API: " + base + "/agent/<op>, header \"Authorization: Bearer $AUTOAGILE_TOKEN\", JSON in and out.\n\n"
            "1. GET  next     -> the best Ready card for you, with a markdown brief. Read the whole brief.\n"
            "2. POST claim    {\"key\": \"" + key + "-12\"} before you touch code.\n"
            "3. POST log      {\"key\", \"text\"} at each milestone and whenever you are unsure (humans answer on the card).\n"
            "4. POST check    {\"key\", \"index\", \"done\": true} as each acceptance criterion passes.\n"
            "5. POST submit   {\"key\", \"summary\", \"links\": [{\"label\": \"PR\", \"url\": \"...\"}]} when tests pass. Never claim a second card while one is in Doing.\n"
            "6. POST release  {\"key\", \"reason\"} if you get stuck or the card is wrong. POST propose {\"title\", \"body\", \"type\"} for follow-up work you notice.\n\n"
            "Example: curl -s -H \"Authorization: Bearer $AUTOAGILE_TOKEN\" " + base + "/agent/next\n")


class Agents(AgentsTemplate):
    """#agents: AI developers on the crew. Add one (its token shows once), pause/resume, new token, edit/remove, the
    review queue, a live console that runs the agent API as any agent, the house rules, the API reference and the
    CLAUDE.md snippet."""

    def __init__(self, args=(), **properties):
        super().__init__(**properties)
        self.crew = aa.need_crew(self)
        if not self.crew:
            return
        self.lines = []
        self.hist, self.hi = [], -1
        self.console_id = state.store_get("ag.console", None)
        self.agents_panel.add_event_handler("x-agent", self._agent_action)
        state.set_control_attr(self.console_agent, "aria-label", "Drive which agent")
        state.set_control_attr(self.cmd, "aria-label", "Console command")
        state.set_control_attr(self.cmd, "spellcheck", "false")
        state.set_control_attr(self.cmd, "autocomplete", "off")
        state.set_control_attr(self.rules_box, "aria-label", "House rules")
        anvil.js.get_dom_node(self.cmd).addEventListener("keydown", anvil.js.report_exceptions(self._cmd_key))
        self._load()

    def _load(self, quiet=False):
        d = state.call_quiet("get_agents", self.crew["id"]) if quiet else state.call("get_agents", self.crew["id"])
        if not d:
            return
        self.d = d
        key = d["crew"]["key"]
        base = aa.api_base()
        ag = d["agents"]
        self.sub.text = "%s // %s · %d Ready cards pass the agent checks · %d agent cards in review" % (
            key, state.plural(len(ag), "agent"), d["agent_ready"], len(d["review"]))
        self.demo_note.visible = bool(d["crew"]["demo"])
        self.review_win.visible = bool(d["review"])
        self.review_extra.text = str(len(d["review"]))
        self.review_panel.items = d["review"]
        self.agents_panel.items = ag
        self.agents_empty.visible = not ag
        cur = [a for a in ag if a["id"] == self.console_id] or [a for a in ag if a["active"]] or ag[:1]
        self.console_id = cur[0]["id"] if cur else None
        self.console_box.visible = bool(cur)
        self.console_empty.visible = not cur
        self.console_extra.text = "live"
        if cur:
            self.console_agent.items = [(a["name"], a["id"]) for a in ag]
            self.console_agent.selected_value = self.console_id
            self.prompt_label.text = "%s@%s $" % (cur[0]["name"].replace(" ", "").lower(), key.lower())
            self.cmd.placeholder = "next · claim %s-12 · log %s-12 text · submit %s-12 summary" % (key, key, key)
        self._draw_term()
        self.rules_box.text = d["rules"]
        self.base.text = base + "/agent/<op>"
        state.set_attr(self.manifest_link, "href", base + "/agent/manifest")
        self.ops_panel.items = d["ops"]
        self.curl.text = ('curl -s -H "Authorization: Bearer $AUTOAGILE_TOKEN" \\\n  ' + base + '/agent/next\n\n'
                          'curl -s -X POST -H "Authorization: Bearer $AUTOAGILE_TOKEN" \\\n  -d \'{"key":"' + key + '-12"}\' ' + base + '/agent/claim')
        self.snippet.text = snippet(base, key)
        self.feed_panel.items = d["feed"][:14]
        self.feed_empty.visible = not d["feed"]

    def _draw_term(self):
        self.term_panel.items = self.lines
        self.term_intro.visible = not self.lines
        aa.AA.scrollEnd(anvil.js.get_dom_node(self.term))

    # ---- console
    def _run(self, command):
        command = (command or "").strip()
        if not command or not self.console_id:
            return
        if command in ("__clear", "clear"):
            self.lines = []
            self._draw_term()
            return
        self.hist.insert(0, command)
        self.hi = -1
        self.lines.append({"cls": "in", "text": "$ " + command})
        r = state.call_quiet("agent_console", self.console_id, command, aa.api_base())
        if r is None:
            self.lines.append({"cls": "err", "text": "The console could not reach the server."})
        elif r.get("lines"):
            self.lines.append({"cls": "", "text": "\n".join(r["lines"])})
        elif r.get("ok") is False:
            self.lines.append({"cls": "err", "text": r.get("error") or "Error"})
        else:
            res = r["result"]
            brief = None
            if isinstance(res.get("card"), dict) and res["card"].get("brief"):
                brief = res["card"].pop("brief")
            txt = json.dumps(res, indent=1)
            if brief:
                txt += "\n--- brief ---\n" + brief
            self.lines.append({"cls": "ok" if res.get("ok") else "err", "text": txt})
        self.lines = self.lines[-60:]
        self._load(quiet=True)

    @handle("cmd", "pressed_enter")
    def cmd_pressed_enter(self, **event_args):
        v = self.cmd.text
        self.cmd.text = ""
        self._run(v)
        self.cmd.focus()

    def _cmd_key(self, e):
        if e.key == "ArrowUp" and self.hist:
            self.hi = min(len(self.hist) - 1, self.hi + 1)
            self.cmd.text = self.hist[self.hi]
            e.preventDefault()
        elif e.key == "ArrowDown":
            self.hi = max(-1, self.hi - 1)
            self.cmd.text = "" if self.hi < 0 else self.hist[self.hi]
            e.preventDefault()

    @handle("console_agent", "change")
    def console_agent_change(self, **event_args):
        self.console_id = self.console_agent.selected_value
        state.store_set("ag.console", self.console_id)
        self._load(quiet=True)

    @handle("c_help", "click")
    def c_help_click(self, **event_args):
        self._run("help")

    @handle("c_whoami", "click")
    def c_whoami_click(self, **event_args):
        self._run("whoami")

    @handle("c_next", "click")
    def c_next_click(self, **event_args):
        self._run("next")

    @handle("c_ready", "click")
    def c_ready_click(self, **event_args):
        self._run("cards ready")

    @handle("c_review", "click")
    def c_review_click(self, **event_args):
        self._run("cards review")

    @handle("c_clear", "click")
    def c_clear_click(self, **event_args):
        self._run("__clear")

    # ---- rules, snippet
    @handle("rules_button", "click")
    def rules_button_click(self, **event_args):
        if state.call("update_crew", self.crew["id"], {"agent_rules": self.rules_box.text or ""}) is not None:
            state.toast("House rules saved", "ok")

    @handle("copy_snippet", "click")
    def copy_snippet_click(self, **event_args):
        aa.copy(self.snippet.text)

    # ---- agents
    def _token(self, token, agent):
        from ...Dialogs.TokenDialog import TokenDialog
        alert(TokenDialog(token=token, agent=agent, snippet=snippet(aa.api_base(), self.d["crew"]["key"])), buttons=[], role="app-dialog", large=True)

    def _agent_action(self, action, agent_id, **event_args):
        a = [x for x in self.d["agents"] if x["id"] == agent_id][0]
        if action == "toggle":
            if state.call("update_agent", a["id"], {"active": not a["active"]}) is not None:
                state.toast(a["name"] + (" paused" if a["active"] else " resumed"), "ok")
                self._load()
        elif action == "use":
            self.console_id = a["id"]
            state.store_set("ag.console", a["id"])
            self._load(quiet=True)
            anvil.js.get_dom_node(self.cmd).scrollIntoView({"block": "center"})
            self.cmd.focus()
        elif action == "token":
            title = ("New token for " if a["has_token"] else "Token for ") + a["name"] + "?"
            text = "The old token stops working right away." if a["has_token"] else "The token is shown once."
            if confirm(text, title=title, buttons=[("Cancel", False), ("Issue token", True)], role="app-dialog"):
                r = state.call("rotate_token", a["id"])
                if r:
                    self._token(r["token"], a)
                    self._load()
        elif action == "edit":
            from ...Dialogs.AgentDialog import AgentDialog
            if alert(AgentDialog(agent=a, kinds=self.d["kinds"]), buttons=[], role="app-dialog"):
                self._load()

    @handle("new_button", "click")
    def new_button_click(self, **event_args):
        from ...Dialogs.AgentDialog import AgentDialog
        r = alert(AgentDialog(agent=None, kinds=self.d["kinds"], crew_id=self.crew["id"]), buttons=[], role="app-dialog")
        if r:
            self.console_id = r["agent"]["id"]
            state.store_set("ag.console", self.console_id)
            self._token(r["token"], r["agent"])
            self._load()
