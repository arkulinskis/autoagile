"""The app starts here (anvil.yaml: startup module). One server call to learn who is signed in (Anvil's loading
spinner shows meanwhile), the Privacy & Terms kit, then the page for the address in the browser bar."""
import anvil.server
from anvil.js import window

from . import legal, router, state

LEGAL_THEME = {"accent": "#5a00e0"}  # colours for the Privacy & Terms page (match --c-brand in app.css)


def _go(name, arg=None):
    router.go(name, arg) if arg else router.go(name)


window.AA.toast = state.toast  # the engine (aa-engine.js) speaks through the app's toasts and router
window.AA.go = _go

legal.setup(LEGAL_THEME)
state.set_me(anvil.server.call("get_me"))
if state.me():
    legal.refresh_soon()
router.start()
