"""Page addresses: #name/arg1/arg2 -> a page Form (open_form), with sign-in rules.

Links in templates are plain <a href="#board">; code calls router.go("card", "NOVA-12").

    PAGES[name] = (who may open it, browser-tab title)   who: None = anyone, "guest" = signed out only, "user", "admin"
    NAV = the main menu (header; the phone tab bar shows the first four): (page, label, icon)
New page: add it to PAGES, to _form() and (if it belongs in the menu) to NAV.
The addresses are the same as the JavaScript version's, so links people saved keep working.
A page whose __init__ sends people elsewhere (no crew yet -> #crew/new) sets self.redirected = True.
"""
import anvil
import anvil.js
from anvil.js import window

from . import state

PAGES = {
    "landing": (None, "Welcome"),
    "auth": ("guest", "Sign in"),
    "profile": ("user", "Your profile"),
    "admin": ("admin", "Admin"),
    "deck": ("user", "Deck"),
    "board": ("user", "Board"),
    "backlog": ("user", "Backlog"),
    "card": ("user", "Card"),
    "plan": ("user", "Plan"),
    "agents": ("user", "AI agents"),
    "insights": ("user", "Insights"),
    "reports": ("user", "Reports"),
    "requests": ("user", "Requests"),
    "ask": ("user", "Ask a crew"),
    "import": ("user", "Import and export"),
    "crew": ("user", "Crew"),
}
NAV = [("deck", "Deck", "deck"), ("board", "Board", "board"), ("backlog", "Backlog", "list"), ("plan", "Plan", "calendar"),
       ("agents", "Agents", "bot"), ("reports", "Reports", "chart")]
APP_NAME = "AutoAgile"
HOME = "deck"
_r: dict = {"after": "", "listening": False, "page": None, "name": ""}


def _form(name):
    """The page's Form class (imported when first needed, so start-up stays quick)."""
    if name == "landing":
        from .Pages.Landing import Landing
        return Landing
    if name == "auth":
        from .Pages.Auth import Auth
        return Auth
    if name == "profile":
        from .Pages.Profile import Profile
        return Profile
    if name == "deck":
        from .Pages.Deck import Deck
        return Deck
    if name == "board":
        from .Pages.Board import Board
        return Board
    if name == "backlog":
        from .Pages.Backlog import Backlog
        return Backlog
    if name == "party":
        from .Pages.Party import Party
        return Party
    if name == "card":
        from .Pages.Card import Card
        return Card
    if name == "plan":
        from .Pages.Plan import Plan
        return Plan
    if name == "agents":
        from .Pages.Agents import Agents
        return Agents
    if name == "insights":
        from .Pages.Insights import Insights
        return Insights
    if name == "reports":
        from .Pages.Reports import Reports
        return Reports
    if name == "requests":
        from .Pages.Requests import Requests
        return Requests
    if name == "ask":
        from .Pages.Ask import Ask
        return Ask
    if name == "import":
        from .Pages.Import import Import
        return Import
    if name == "crew":
        from .Pages.Crew import Crew
        return Crew
    if name == "crewstart":
        from .Pages.CrewStart import CrewStart
        return CrewStart
    from .Pages.Admin import Admin
    return Admin


def parse(hash_text):
    h = (hash_text or "").lstrip("#").lstrip("!").lstrip("/").split("?")[0]
    parts = [window.decodeURIComponent(p) for p in h.split("/") if p]
    return (parts[0] if parts else ""), parts[1:]


def href(name, *args):
    """'#name/arg1/arg2' with every part URL-encoded (row ids contain brackets and commas)."""
    return "#" + "/".join([name] + [window.encodeURIComponent(str(a)) for a in args if a not in (None, "")])


def home_page():
    return HOME if state.me() else "landing"


def current():
    """The name of the page on screen ("card", "deck" ...)."""
    return _r["name"]


def show():
    """Open the page for the current address."""
    name, args = parse(window.location.hash)
    if name not in PAGES:
        name, args = home_page(), []
    who = PAGES[name][0]
    if who == "guest" and state.me():
        name, args = HOME, []
    elif who in ("user", "admin") and not state.me():
        _r["after"] = window.location.hash
        name, args = "auth", []
    elif who == "admin" and not state.is_admin():
        state.toast("That page is for admins only.", "error")
        name, args = HOME, []
    title = args[0] if name == "card" and args else PAGES[name][1]
    window.document.title = title + " · " + APP_NAME
    window.UI_READY = False
    old = _r["page"]
    if old is not None and hasattr(old, "leave"):
        old.leave()  # pages with timers or listeners stop them here
    _r["name"] = name
    form = name
    if name == "backlog" and args and args[0] == "party":
        form = "party"
    elif name == "crew" and args and args[0] in ("new", "join"):
        form = "crewstart"
    page = _form(form)(args=args)
    if getattr(page, "redirected", False):
        return  # the page sent us somewhere else (no crew yet -> #crew/new); that address opens its own page
    _r["page"] = page
    anvil.open_form(page)
    shell = getattr(page, "layout", None)
    if shell is not None and hasattr(shell, "refresh"):
        shell.refresh(name)  # Anvil reuses the layout between pages: tell it who is signed in and which page is open
    window.scrollTo(0, 0)
    window.UI_READY = True  # tests and screenshots wait for this


def refresh_shell():
    """Redraw the header (the crew chip after switching crew)."""
    page = _r["page"]
    shell = getattr(page, "layout", None) if page is not None else None
    if shell is not None and hasattr(shell, "refresh"):
        shell.refresh(_r["name"])


def go(name, *args):
    """Go to a page. Same address again = reload the page."""
    target = href(name, *args)
    if window.location.hash == target:
        show()
    else:
        window.location.hash = target


def reload():
    show()


def replace(name, *args):
    """Change the address without opening anything (a page that switches its own view)."""
    window.history.replaceState(None, "", href(name, *args))


def after_sign_in():
    """Where to go once someone signs in: the page they were heading for, or home."""
    target = _r["after"]
    _r["after"] = ""
    if target and target != window.location.hash:
        window.location.hash = target
    else:
        go(HOME)


def remember_after(target):
    _r["after"] = target


def _on_hash(event):
    show()


def start():
    if not _r["listening"]:
        window.addEventListener("hashchange", anvil.js.report_exceptions(_on_hash))
        _r["listening"] = True
    show()
