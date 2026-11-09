from anvil import *
import anvil.js

from ._anvil_designer import ChartTemplate
from ... import aa


class Chart(ChartTemplate):
    """A chart drawn by the engine. draw(kind, opts, cols=None, rows=None): kind is bars|grouped|lines|stack|scatter,
    opts the engine's options (colours as var(--ch-1) ...); cols + rows add the 'Show as a table' view.
    It redraws itself when the window width changes (charts measure their box)."""

    def __init__(self, **properties):
        self._spec = None
        self._shown = False
        super().__init__(**properties)
        self._redraw_js = anvil.js.report_exceptions(self._redraw)
        aa.AA.onResize(self._redraw_js)

    def draw(self, kind, opts, cols=None, rows=None):
        self._spec = (kind, opts)
        if cols:
            self.dom_nodes["tbl"].innerHTML = aa.AA.table(aa.js(cols), aa.js(rows or []))
        self._paint()

    def _paint(self):
        if self._spec:
            kind, opts = self._spec
            aa.AA.chart[kind](self.dom_nodes["el"], aa.js(opts))

    def _redraw(self, *args):
        if not self._shown:
            return False  # gone: the engine forgets this redraw
        self._paint()
        return True

    @handle("", "show")
    def form_show(self, **event_args):
        self._shown = True
        self._paint()  # first draw once the box has a width

    @handle("", "hide")
    def form_hide(self, **event_args):
        self._shown = False
        aa.AA.hideTip()
