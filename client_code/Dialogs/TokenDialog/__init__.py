from anvil import *

from ._anvil_designer import TokenDialogTemplate
from ... import aa, state


class TokenDialog(TokenDialogTemplate):
    """An agent's new token, shown once, with the CLAUDE.md snippet."""

    def __init__(self, **properties):
        token, agent, snippet = properties.pop("token"), properties.pop("agent"), properties.pop("snippet")
        super().__init__(**properties)
        self.title.text = "Token for " + agent["name"]
        state.heading(self.title, 2)
        self.token.text = token
        self.snippet.text = snippet

    @handle("copy_token", "click")
    def copy_token_click(self, **event_args):
        aa.copy(self.token.text)

    @handle("copy_snippet", "click")
    def copy_snippet_click(self, **event_args):
        aa.copy(self.snippet.text)

    @handle("done_button", "click")
    def done_button_click(self, **event_args):
        self.raise_event("x-close-alert", value=True)
