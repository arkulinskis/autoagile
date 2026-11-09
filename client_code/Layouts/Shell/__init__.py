import datetime

from anvil import *
import anvil.js
from anvil.js import window

from ._anvil_designer import ShellTemplate
from ... import aa, auth, router, state

THEMES = ["auto", "light", "dark"]
# Ctrl K palette entries and the g-chords: (address, label, icon, chord)
GO = [("deck", "Deck", "deck", "g d"), ("board", "Board", "board", "g b"), ("backlog", "Backlog", "list", "g l"),
      ("backlog/party", "Estimation Party", "gate", ""), ("plan", "Plan", "calendar", "g p"), ("reports", "Reports", "chart", "g r"),
      ("requests", "Requests", "flag", "g q"), ("agents", "AI agents", "bot", "g a"), ("insights", "Insights", "chart", "g i"),
      ("crew", "Crew settings", "users", "g s"), ("import", "Import and export", "layers", "g x")]


class Shell(ShellTemplate):
    """The frame around every page: the black console header (menu, the crew chip, Ctrl K, account menu), the footer
    and the phone tab bar. Anvil keeps ONE Shell while pages come and go, so everything that depends on who is signed
    in, the crew or the page is drawn in refresh(), which router.show() calls after every page change.
    Keyboard: Ctrl K or / opens the palette (Dialogs/Palette); g + a letter jumps to a page."""

    def __init__(self, **properties):
        super().__init__(**properties)
        self.copyright_label.text = "© %d AutoAgile" % datetime.date.today().year
        self._outside = anvil.js.report_exceptions(self._close_menu_outside)
        self._keys = anvil.js.report_exceptions(self._key)
        self._chord = 0
        self.refresh("")

    def refresh(self, page):
        me = state.me()
        self.classes.update({"signed-in": bool(me), "signed-out": not me})
        node = anvil.js.get_dom_node(self)
        if getattr(self, "_page_class", ""):
            node.classList.remove(self._page_class)
        self._page_class = ("page-" + page) if page else ""
        if page:
            node.classList.add(self._page_class)
        self.member_actions.visible = bool(me)
        self.guest_actions.visible = not me and page != "auth"
        self.tabbar.visible = bool(me)
        self.nav.visible = bool(me)
        self.menu.visible = False
        state.set_attr(self.brand, "href", "#deck" if me else "#landing")
        links = [{"page": p, "label": label, "icon": icon, "on": p == page} for p, label, icon in router.NAV] if me else []
        self.nav_panel.items = links
        self.tab_panel.items = links[:4]
        self.tab_profile.classes["on"] = page == "profile"
        crew = aa.current() if me else None
        self.crew_actions.visible = bool(crew)
        if crew:
            self.crew_button.text = "%s  L%d" % (crew["key"], crew["level"])
            self.crew_button.role = ["crewchip", "demo"] if crew["demo"] else ["crewchip"]
            state.set_control_attr(self.crew_button, "aria-label", "Crew %s, switch crew" % crew["name"])
        if me:
            self.avatar_button.text = state.initials(me.get("name"))
            self.menu_name.text = me.get("name") or ""
            self.menu_email.text = me.get("email") or ""
            self.admin_link.visible = bool(me.get("is_admin"))
        self._show_theme()

    # ---- crew chip + palette
    @handle("crew_button", "click")
    def crew_button_click(self, **event_args):
        open_switcher()

    @handle("palette_button", "click")
    def palette_button_click(self, **event_args):
        open_palette()

    # ---- account menu
    @handle("avatar_button", "click")
    def avatar_button_click(self, **event_args):
        self.menu.visible = not self.menu.visible

    def _close_menu_outside(self, event):
        if self.menu.visible and not event.target.closest(".anvil-role-avatar, .ui-menu .ui-seg"):
            self.menu.visible = False

    def _key(self, event):
        if event.key == "Escape":
            self.menu.visible = False
        if not state.me():
            return
        target = event.target
        tag = str(getattr(target, "tagName", "") or "")
        typing = tag in ("INPUT", "TEXTAREA", "SELECT") or bool(getattr(target, "isContentEditable", False))
        if (event.ctrlKey or event.metaKey) and str(event.key).lower() == "k":
            event.preventDefault()
            open_palette()
            return
        if typing or event.ctrlKey or event.metaKey or event.altKey or window.document.querySelector(".anvil-modal.in, .modal.in"):
            return
        if event.key == "/":
            event.preventDefault()
            open_palette()
            return
        now = window.Date.now()
        if self._chord and now - self._chord < 900:
            self._chord = 0
            for addr, label, icon, chord in GO:
                if chord == "g " + str(event.key).lower():
                    event.preventDefault()
                    router.go(*addr.split("/"))
            return
        if event.key == "g":
            self._chord = now

    @handle("", "show")
    def form_show(self, **event_args):
        window.document.addEventListener("click", self._outside, True)
        window.document.addEventListener("keydown", self._keys)

    @handle("", "hide")
    def form_hide(self, **event_args):
        window.document.removeEventListener("click", self._outside, True)
        window.document.removeEventListener("keydown", self._keys)

    def theme_click(self, event):
        state.set_theme(event.currentTarget.getAttribute("data-theme-set"))
        self._show_theme()

    def _show_theme(self):
        t = state.theme()
        for name, el in zip(THEMES, [self.theme_auto, self.theme_light, self.theme_dark]):
            el.classes["on"] = name == t

    def feedback_click(self, event):
        self.menu.visible = False
        state.feedback()

    def sign_out_click(self, event):
        auth.sign_out()
        aa.forget()
        state.toast("Signed out. See you soon!")
        router.go("landing")


def open_switcher():
    from ...Dialogs.CrewSwitcher import CrewSwitcher
    aa.load_crews(True)
    picked = alert(CrewSwitcher(), buttons=[], role="app-dialog", large=True)
    if picked:
        aa.set_crew(picked)
        if router.current() == "card":
            router.go("deck")
        else:
            router.reload()


_open = {"palette": False}


def open_palette():
    if _open["palette"] or not state.me():
        return
    from ...Dialogs.Palette import Palette
    _open["palette"] = True
    try:
        aa.load_crews()
        r = alert(Palette(go=GO), buttons=[], role="app-dialog", large=True)
    finally:
        _open["palette"] = False
    if not r:
        return
    kind, value = r
    if kind == "go":
        router.go(*value.split("/"))
    elif kind == "card":
        router.go("card", value)
    elif kind == "switch":
        open_switcher()
    elif kind == "add":
        crew = aa.current()
        res = state.call("quick_add", crew["id"], value)
        if res:
            state.toast(res["card"]["key"] + " added to the backlog", "ok")
            router.go("card", res["card"]["key"])
