from anvil import *

from ._anvil_designer import AlertHistRowTemplate
from ... import state


class AlertHistRow(AlertHistRowTemplate):
    """A past alert and where it went. item = alert dict + kind_label."""

    def __init__(self, **properties):
        super().__init__(**properties)
        h = self.item
        self.when.text = state.ago(h["created"])
        sent = h.get("sent") or {}
        if sent.get("skipped"):
            st = "not sent: " + str(sent["skipped"])
        else:
            parts = []
            if sent.get("webhook"):
                parts.append("webhook %s" % sent["webhook"])
            if sent.get("email"):
                parts.append("%s email%s" % (sent["email"], "" if sent["email"] == 1 else "s"))
            st = " · ".join(parts) or "recorded"
        self.st.text = "%s · %s" % (h["kind_label"], st)
