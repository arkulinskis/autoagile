from anvil import *

from ._anvil_designer import PreviewRowTemplate


class PreviewRow(PreviewRowTemplate):
    """A preview line of the import. item = an import item + col (the column name)."""

    def __init__(self, **properties):
        super().__init__(**properties)
        it = self.item
        self.t.text = (it.get("title") or "")[:60]
        self.ty.text = it.get("type") or ""
        self.p.text = "" if it.get("points") in (None, "") else str(it["points"])
        self.who.text = it.get("assignee") or ""
        self.ep.text = it.get("epic") or ""
        self.cr.text = (it.get("created") or "")[:10]
