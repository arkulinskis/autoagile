from anvil import *

from ._anvil_designer import LcdTemplate


class Lcd(LcdTemplate):
    """An LCD read-out. item = {value, unit, label, cls} (cls: '', pink, cyan, amber, red). A value written the engine's
    way, "12<small>d</small>", is split into value + unit."""

    def __init__(self, **properties):
        super().__init__(**properties)
        v = str(self.item.get("value", ""))
        unit = self.item.get("unit") or ""
        if "<small>" in v:
            v, rest = v.split("<small>", 1)
            unit = rest.replace("</small>", "")
        self.value.text = v
        self.unit.text = unit
        self.unit_box.visible = bool(unit)
        cls = self.item.get("cls") or ""
        if cls:
            self.classes.add(cls)
