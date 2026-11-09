from anvil import *

from ._anvil_designer import OpRowTemplate


class OpRow(OpRowTemplate):
    """An agent API operation in the reference. item = {op, method, doc}."""

    def __init__(self, **properties):
        super().__init__(**properties)
