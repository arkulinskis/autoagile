from anvil import *

from ._anvil_designer import LandingTemplate
from ... import state

# The app's video on the Addanapp YouTube channel (APP_MAKER/youtube/manifest.json), shown in the Watch section.
YT_VIDEO = "iJ6mNTshQPg"


class Landing(LandingTemplate):
    """#landing (Persuade): the promise, the live-demo hero (an agent's card moving across a board beside its API log,
    CSS only), the Watch section, the four levels, a live complexity-gates widget (Components/Gates with the built-in
    copy of Gates.py's config: visitors can't call the server), the agent API, features, FAQ. Static copy lives in the
    template."""

    def __init__(self, args=(), **properties):
        super().__init__(**properties)
        me = state.me()
        self.guest_cta.visible = not me
        self.member_cta.visible = bool(me)
        self.band_guest.visible = not me
        self.band_member.visible = bool(me)
        self.gates.answers = {"scope": 1, "clarity": 0, "novelty": 1, "deps": 0, "risk": 1}
        self.dom_nodes["yt_cover"].addEventListener("click", self._play)

    def _play(self, event):
        """Swap the video's cover for YouTube's player (privacy-enhanced); nothing loads from YouTube before this click."""
        self.dom_nodes["yt_frame"].innerHTML = (
            '<iframe src="https://www.youtube-nocookie.com/embed/' + YT_VIDEO + '?autoplay=1&rel=0&playsinline=1" '
            'title="AutoAgile video" allow="autoplay; encrypted-media; picture-in-picture; fullscreen" allowfullscreen '
            'referrerpolicy="strict-origin-when-cross-origin"></iframe>')
