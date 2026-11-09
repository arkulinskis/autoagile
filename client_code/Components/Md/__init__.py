from anvil import *

from ._anvil_designer import MdTemplate
from ... import aa


class Md(MdTemplate):
    """Mini markdown text (card descriptions). The HTML comes from the engine (AA.md), which escapes first."""

    def __init__(self, **properties):
        self._content, self._ready = "", False
        super().__init__(**properties)
        self._ready = True
        self._draw()

    def _draw(self):
        if self._ready:
            self.dom_nodes["out"].innerHTML = aa.AA.md(self._content or "")

    @property
    def content(self):
        return self._content

    @content.setter
    def content(self, value):
        self._content = value or ""
        self._draw()
