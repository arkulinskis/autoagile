"""Demo content, so the app never looks empty. Loaded automatically the first time anyone opens the app
(ensure_loaded), removed or reloaded from Admin -> Demo data. Removing it is remembered.

Two fictional crews, open to every signed-in person as a sandbox:
  NOVA (Nova FM, an internet radio app): a veteran crew at level 4 (YEAR) with 8 closed sprints, a running
       sprint, a planned one, 10 epics across the year, and three AI agents (Claude, Unit 303, 909).
  PIXL (Pixel Bakery, online ordering for a bakery): a young Kanban crew five weeks in, 4 of 6 checks
       towards level 2 (SCRUM).
Demo people have @example.com emails and can't sign in. Every demo row is flagged is_demo=True; removing
the demo also deletes anything real people added inside the demo crews.
"""
import datetime as dt
import random

from anvil.tables import app_tables

from . import common as C
from . import Gates
from . import Model as M

DEMO_USERS = [
    ("maya", "Maya Chen", "maya.demo@example.com"),
    ("theo", "Theo Martin", "theo.demo@example.com"),
    ("ines", "Ines Ozola", "ines.demo@example.com"),
    ("kofi", "Kofi Mensah", "kofi.demo@example.com"),
    ("lena", "Lena Park", "lena.demo@example.com"),
]
# Children before parents.
DEMO_TABLES = ["events", "cards", "sprints", "epics", "agents", "members", "teams"]

RANGES = {1: (0, 1), 2: (2, 3), 3: (4, 6), 5: (7, 9), 8: (10, 12), 13: (13, 15), 21: (16, 18)}
SAFE = ["scope", "novelty"]


def state():
    return C.get_setting("demo", "never")  # "never" | "loaded" | "removed"


def ensure_loaded():
    if state() == "never":
        load()


def gates_for(rng, points, solo=False, spike=False):
    """Gate answers that score exactly `points` (and agent-solo / spike if asked)."""
    for _ in range(400):
        lo, hi = RANGES[points]
        total = rng.randint(lo, hi)
        cap = 1 if points <= 2 else 2 if points == 3 else 3
        a = {g: 0 for g in Gates.GATE_IDS}
        if spike:
            a["clarity"] = 3
            total = max(total, 3)
        tries = 0
        while sum(a.values()) < total and tries < 200:
            tries += 1
            pool = SAFE if solo and rng.random() < 0.75 else Gates.GATE_IDS
            g = rng.choice(pool)
            lim = min(cap, 1) if (solo and g not in SAFE) else cap
            if a[g] < lim:
                a[g] += 1
        s = Gates.score(a)
        if s["points"] == points and (not solo or s["fit"] == "solo") and (not spike or s["verdict"] == "spike"):
            return a
    return {}


def load():
    remove(remember=False)
    rng = random.Random(303)
    now = C.now()
    today = now.date()
    U = {}
    for key, name, email in DEMO_USERS:
        u = app_tables.users.get(email=email) or app_tables.users.add_row(email=email, enabled=False)
        u.update(display_name=name, is_demo=True, signed_up=now - dt.timedelta(days=170))
        U[key] = u
    _nova(rng, U, now, today)
    _pixl(rng, U, now, today)
    C.set_setting("demo", "loaded")
    return counts()


def _at(day, hours=10.0):
    return dt.datetime(day.year, day.month, day.day, tzinfo=dt.timezone.utc) + dt.timedelta(hours=hours)


class Builder(object):
    """Collects card specs, then numbers them in creation order and writes them."""

    def __init__(self, team, rng, creator=None):
        self.team, self.rng, self.specs, self.creator = team, rng, [], creator

    def add(self, title, points=None, status="done", created=None, solo=False, spike=False, gated=True, **kw):
        g = gates_for(self.rng, points, solo=solo, spike=spike) if (points and gated) else {}
        spec = dict(title=title, status=status, points=points, gates=g, points_src=("gates" if g else ("manual" if points else None)),
                    created=created, type=kw.pop("type", "story"), priority=kw.pop("priority", 2), body=kw.pop("body", ""),
                    acceptance=kw.pop("acceptance", []), labels=kw.pop("labels", []), links=kw.pop("links", []),
                    blocked=kw.pop("blocked", False), blocked_reason=kw.pop("blocked_reason", ""))
        spec["by"] = kw.pop("by", self.creator)
        spec.update(kw)
        self.specs.append(spec)
        return spec

    def write(self):
        self.specs.sort(key=lambda s: s["created"])
        rank = 1000
        for i, s in enumerate(self.specs):
            row = {k: v for k, v in s.items() if k != "by"}
            row.update(team=self.team, number=i + 1, is_demo=True, created_by=s.get("by"),
                       updated=s.get("done_at") or s.get("moved_at") or s["created"])
            rank += 1000
            row["rank"] = rank
            row.setdefault("moved_at", s.get("done_at") or s.get("review_at") or s.get("started") or s["created"])
            s["row"] = app_tables.cards.add_row(**row)
        self.team["next_number"] = len(self.specs) + 1


def _history_cards(b, rng, sprint, start, end, target, humans, agents, epics_pick, titles, agent_share):
    total = 0
    while total < target:
        p = rng.choice([1, 2, 3, 3, 3, 5, 5, 8])
        if total + p > target + 2:
            p = max([x for x in (1, 2, 3, 5) if x <= max(1, target - total)] or [1])
        title, typ = titles.pop()
        solo = p <= 5 and rng.random() < 0.55
        use_agent = bool(solo and agents and rng.random() < agent_share)
        st = _at(start, 9) + dt.timedelta(days=rng.uniform(0, 11))
        cyc = 0.4 + p * 0.55 + rng.uniform(0, 1.6)
        if use_agent:
            cyc *= 0.55
        done = min(st + dt.timedelta(days=cyc), _at(end, 17))
        if done <= st:
            st = done - dt.timedelta(hours=6)
        review = done - dt.timedelta(hours=rng.uniform(3, 22) if use_agent else rng.uniform(1, 10))
        review = max(review, st + dt.timedelta(hours=1))
        who = rng.choice(agents) if use_agent else rng.choice(humans)
        kw = {"assignee_agent": who} if use_agent else {"assignee_user": who}
        b.add(title, p, status="done", type=typ, solo=solo, created=st - dt.timedelta(days=rng.uniform(1, 24)), started=st,
              review_at=review, done_at=done, sprint=sprint, epic=epics_pick(), priority=rng.choice([1, 2, 2, 2, 3]),
              body="Done in %s." % sprint["name"],
              acceptance=[{"text": "Works as described", "done": True}, {"text": "Tests pass", "done": True}], **kw)
        total += p
    return total


ACTIONS = [("Add", "story"), ("Fix", "bug"), ("Speed up", "story"), ("Test", "task"), ("Polish", "story"), ("Refactor", "chore"),
           ("Document", "chore")]
NOVA_SUBJECTS = ["stream reconnect", "sleep timer", "album art cache", "listener counter", "show schedule", "station search",
                 "favourites sync", "push settings", "podcast player", "playlist export", "volume normalising", "lock-screen controls",
                 "car mode queue", "sign-up flow", "password reset email", "station analytics", "embeddable player", "deep links",
                 "error reporting", "offline downloads", "download manager", "station logos", "now-playing banner", "genre filters"]


def _nova(rng, U, now, today):
    t = app_tables.teams.add_row(
        name="Nova FM", key="NOVA", mission="An internet radio app for independent stations: tune in anywhere, chat with the show.",
        level=4, join_code=None, owner=U["maya"], created=now - dt.timedelta(days=160), next_number=1, sprint_days=14,
        wip={"ready": 10, "doing": 5, "review": 3}, dod=list(M.DEFAULT_DOD) + ["Release note written"],
        agent_rules=M.DEFAULT_AGENT_RULES + " Use the station test fixtures, never real stations. Chat features need a moderation test.",
        level_log=[{"level": 1, "at": C.iso(now - dt.timedelta(days=160)), "by": "Maya Chen", "forced": False},
                   {"level": 2, "at": C.iso(now - dt.timedelta(days=118)), "by": "Maya Chen", "forced": False},
                   {"level": 3, "at": C.iso(now - dt.timedelta(days=48)), "by": "Theo Martin", "forced": False},
                   {"level": 4, "at": C.iso(now - dt.timedelta(days=8)), "by": "Maya Chen", "forced": False}],
        is_demo=True)
    for k, role in (("maya", "owner"), ("theo", "member"), ("ines", "member"), ("kofi", "member")):
        app_tables.members.add_row(team=t, user=U[k], role=role, joined=now - dt.timedelta(days=150), is_demo=True)

    def agent(name, kind, color, wip, active, days, by, seen):
        return app_tables.agents.add_row(team=t, name=name, kind=kind, color=color, max_wip=wip, token_hash=None, token_hint="",
                                         active=active, created=now - dt.timedelta(days=days), created_by=by, last_seen=now - seen,
                                         is_demo=True)
    claude = agent("Claude", "Claude Code", "#ff7a1a", 2, True, 100, U["maya"], dt.timedelta(minutes=12))
    u303 = agent("Unit 303", "Custom agent", "#b4ff1f", 1, True, 60, U["theo"], dt.timedelta(hours=1))
    a909 = agent("909", "Codex", "#00e5ff", 1, False, 20, U["kofi"], dt.timedelta(days=2))

    def epic(title, color, size, quarter, status, rank, body):
        return app_tables.epics.add_row(team=t, title=title, color=color, size=size, quarter=quarter, status=status, rank=rank,
                                        body=body, created=now - dt.timedelta(days=150), is_demo=True)
    qs = M.quarters_from(today, 4)
    prev_q = M.quarter_of(today - dt.timedelta(days=95))
    E = {
        "offline": epic("Offline listening", "#39ff88", "L", prev_q, "done", 1000, "Download shows and listen without a connection."),
        "chat": epic("Live chat for shows", "#ff2bd6", "L", qs[0], "active", 2000, "Listeners chat with the host during live shows, with moderation."),
        "dash": epic("Station dashboard", "#00e5ff", "M", qs[0], "active", 3000, "Station owners see listeners, peaks and chat activity live."),
        "web": epic("Web player redesign", "#ffd60a", "L", qs[0], "planned", 4000, "A faster web player that works on every screen."),
        "a11y": epic("Accessibility pass", "#8a5cff", "M", qs[1], "planned", 5000, "Screen readers, contrast and keyboard use across the apps."),
        "podcast": epic("Podcast import", "#ff7a1a", "L", qs[1], "planned", 6000, "Stations import their podcasts from RSS feeds."),
        "speaker": epic("Smart speaker app", "#b4ff1f", "L", qs[1], "planned", 7000, "Ask your speaker to play a Nova station."),
        "pay": epic("Payments for stations", "#ff3b5c", "XL", qs[2], "planned", 8000, "Listeners support stations; stations get paid out."),
        "reco": epic("Recommendations", "#00e5ff", "XL", qs[3], "idea", 9000, "Suggest stations and shows you'll like."),
        "auto": epic("Car dashboards", "#ffd60a", "M", qs[1], "planned", 10000, "Android Auto and CarPlay apps."),
        "market": epic("Station marketplace", "#39ff88", "XL", qs[2], "idea", 11000, "Stations sell merch and tickets to listeners."),
        "video": epic("Video for live shows", "#ff2bd6", "L", "", "idea", 12000, "Stream the studio camera next to the audio."),
    }
    humans = [U["maya"], U["theo"], U["ines"], U["kofi"]]
    b = Builder(t, rng, U["maya"])
    titles = [("%s %s" % (a, s), typ) for a, typ in ACTIONS for s in NOVA_SUBJECTS]
    rng.shuffle(titles)

    act_start = today - dt.timedelta(days=6)
    targets = [27, 31, 30, 33, 29, 32, 34, 32]
    goals = ["Offline downloads in beta", "Offline for everyone", "Faster start-up", "Station logos everywhere",
             "Chat foundations", "Dashboard first look", "Chat moderation basics", "Polish and bugs"]
    sprints = []
    for k in range(1, 9):
        start = act_start - dt.timedelta(days=14 * (9 - k))
        end = start + dt.timedelta(days=13)
        s = app_tables.sprints.add_row(team=t, number=k, name="Sprint %d" % k, goal=goals[k - 1], start=start, end=end, state="closed",
                                       committed=0, done_points=0, retro={}, closed_at=_at(end, 18), is_demo=True)
        ag = [claude] if k >= 3 else []
        if k >= 6:
            ag.append(u303)
        if k <= 4:
            pick = (lambda: E["offline"] if rng.random() < 0.6 else None)
        else:
            pick = (lambda: rng.choice([E["chat"], E["dash"], None, None]))
        done = _history_cards(b, rng, s, start, end, targets[k - 1], humans, ag, pick, titles, 0.3 + 0.07 * k)
        s.update(done_points=done, committed=done + rng.choice([0, 2, 3, 3, 5]))
        sprints.append(s)
    sprints[-1]["retro"] = {"louder": ["Claude took every small card, so we focused on the hard ones", "Demo to two stations went great"],
                            "mute": ["Starting new cards on Friday afternoon", "Reviews sitting overnight"],
                            "remix": ["Review agent work within 4 hours", "Split anything that gates at 8 or more"],
                            "actions": [{"text": "Set a daily review slot at 14:00", "done": True},
                                        {"text": "Theo writes the chat load-test plan", "done": False}]}
    sprints[-2]["retro"] = {"louder": ["Pairing on the chat protocol"], "mute": ["Unclear acceptance criteria"],
                            "remix": ["Write criteria before running the gates"], "actions": [{"text": "Add a criteria template to cards", "done": True}]}
    sprints[-3]["retro"] = {"louder": ["Unit 303 joined: lint and test chores vanished"], "mute": ["Big-bang merges"],
                            "remix": ["Smaller PRs, merged daily"], "actions": [{"text": "Max 400 lines per PR", "done": True}]}

    act = app_tables.sprints.add_row(team=t, number=9, name="Sprint 9", goal="Live chat in beta for five stations", start=act_start,
                                     end=act_start + dt.timedelta(days=13), state="active", committed=0, done_points=0, retro={},
                                     is_demo=True)
    nxt = app_tables.sprints.add_row(team=t, number=10, name="Sprint 10", goal="Chat for everyone, dashboard export",
                                     start=act_start + dt.timedelta(days=14), end=act_start + dt.timedelta(days=27),
                                     state="planned", committed=0, done_points=0, retro={}, is_demo=True)
    d0 = _at(act_start, 9)

    def H(h):
        return d0 + dt.timedelta(hours=h)
    cur = []
    cur.append(b.add("Chat message list with infinite scroll", 5, "done", created=d0 - dt.timedelta(days=9), started=H(2), review_at=H(50),
                     done_at=H(58), sprint=act, epic=E["chat"], assignee_user=U["theo"], priority=1,
                     body="Listeners see the latest 50 messages and load older ones as they scroll up.",
                     acceptance=[{"text": "Loads 50 at a time", "done": True}, {"text": "Keeps the scroll position", "done": True}]))
    cur.append(b.add("Rate-limit chat messages per listener", 3, "done", solo=True, created=d0 - dt.timedelta(days=8), started=H(26),
                     review_at=H(31), done_at=H(40), sprint=act, epic=E["chat"], assignee_agent=claude, priority=1,
                     body="At most 5 messages per 10 seconds per listener; extra messages get a friendly 'slow down' notice.",
                     acceptance=[{"text": "The 6th message in 10 s is refused", "done": True}, {"text": "Notice shown in the chat box", "done": True},
                                 {"text": "Unit tests for the limiter", "done": True}],
                     links=[{"label": "PR #412", "url": "https://example.com/nova/pull/412"}]))
    cur.append(b.add("Fix emoji picker covering the play button", 2, "done", type="bug", created=d0 - dt.timedelta(days=3), started=H(70),
                     review_at=H(90), done_at=H(96), sprint=act, epic=E["chat"], assignee_user=U["ines"],
                     body="On phones the emoji picker hides the play button. Move it above the keyboard.",
                     acceptance=[{"text": "Play button visible with the picker open", "done": True}]))
    mute = b.add("Moderator can mute a listener", 5, "review", solo=True, created=d0 - dt.timedelta(days=8), started=H(60),
                 review_at=now - dt.timedelta(hours=27), sprint=act, epic=E["chat"], assignee_agent=claude, priority=1,
                 body="Station moderators can mute a listener for 10 minutes, 1 hour or the rest of the show. Muted listeners can read but not post.",
                 acceptance=[{"text": "Mute menu on each message for moderators", "done": True},
                             {"text": "Muted listener sees why and for how long", "done": True},
                             {"text": "Moderation test covers all three durations", "done": True}],
                 links=[{"label": "PR #418", "url": "https://example.com/nova/pull/418"}], moved_at=now - dt.timedelta(hours=27))
    cur.append(mute)
    hist = b.add("Chat history API for stations", 3, "review", created=d0 - dt.timedelta(days=6), started=H(80),
                 review_at=now - dt.timedelta(hours=3), sprint=act, epic=E["dash"], assignee_user=U["kofi"],
                 body="GET /stations/{id}/chat?since= returns messages for archiving.",
                 acceptance=[{"text": "Paginated", "done": True}, {"text": "Only the station's owner can call it", "done": True}],
                 moved_at=now - dt.timedelta(hours=3))
    cur.append(hist)
    prof = b.add("Profanity filter for chat (English and French)", 3, "doing", solo=True, created=d0 - dt.timedelta(days=7),
                 started=now - dt.timedelta(hours=30), sprint=act, epic=E["chat"], assignee_agent=u303,
                 body="Mask listed words in chat messages before they are shown. Word lists per language, editable by the station.",
                 acceptance=[{"text": "Masks words from the EN and FR lists", "done": True}, {"text": "Station can add words", "done": False},
                             {"text": "No false positives on the test corpus", "done": False}], moved_at=now - dt.timedelta(hours=30))
    cur.append(prof)
    cur.append(b.add("Dashboard: live listener graph", 8, "doing", created=d0 - dt.timedelta(days=12), started=now - dt.timedelta(days=3, hours=2),
                     sprint=act, epic=E["dash"], assignee_user=U["maya"], priority=1,
                     body="A live line chart of listeners for the last hour, updating every 10 seconds.",
                     acceptance=[{"text": "Updates every 10 s", "done": True}, {"text": "Shows the peak", "done": False}],
                     moved_at=now - dt.timedelta(days=3, hours=2)))
    cur.append(b.add("Spike: websocket load at 10,000 listeners", 3, "doing", type="spike", created=d0 - dt.timedelta(days=5),
                     started=now - dt.timedelta(days=2), sprint=act, epic=E["chat"], assignee_user=U["theo"],
                     body="Time-boxed to 2 days. Can one chat server hold 10k listeners? Write up the numbers.",
                     acceptance=[{"text": "Load test script in the repo", "done": True}, {"text": "Findings written in the card", "done": False}],
                     moved_at=now - dt.timedelta(days=2)))
    cur.append(b.add("Pin a message to the top of chat", 2, "ready", solo=True, created=d0 - dt.timedelta(days=4), sprint=act, epic=E["chat"],
                     body="Hosts can pin one message (a link, a question) above the chat. Pinning a new one replaces the old one.",
                     acceptance=[{"text": "Host sees 'Pin' on any message", "done": False}, {"text": "Pinned message shows for everyone", "done": False},
                                 {"text": "Unpin button for the host", "done": False}]))
    cur.append(b.add("Chat in the embeddable player", 5, "ready", created=d0 - dt.timedelta(days=4), sprint=act, epic=E["chat"],
                     body="Stations embed the player on their own sites; add an optional chat tab there. Needs design for small sizes.",
                     acceptance=[{"text": "chat=1 option on the embed code", "done": False}, {"text": "Works at 300px wide", "done": False}]))
    push = b.add("Push notification when a show goes live", 3, "ready", created=d0 - dt.timedelta(days=4), sprint=act,
                 blocked=True, blocked_reason="Waiting for the Apple push certificate from the station owner.",
                 body="Listeners who follow a show get a push when it starts.", acceptance=[{"text": "Opt-in per show", "done": False}])
    cur.append(push)
    committed = sum(c["points"] or 0 for c in cur)
    act["committed"] = committed

    for title, p, typ, ep, solo in [("Report a chat message", 3, "story", "chat", True), ("Dashboard: export listeners as CSV", 2, "story", "dash", True),
                                    ("Screen reader labels on the player", 3, "story", "a11y", False),
                                    ("Stream stalls on the iPhone lock screen", 5, "bug", "web", False)]:
        b.add(title, p, "ready", type=typ, solo=solo, created=d0 - dt.timedelta(days=rng.uniform(1, 9)), sprint=nxt, epic=E[ep],
              body="Planned for Sprint 10 with the station panel.",
              acceptance=[{"text": "Behaves as described", "done": False}, {"text": "Covered by a test", "done": False}])
    backlog = [
        ("Import podcasts from an RSS feed", 8, "story", "podcast", {}, "Stations paste an RSS URL; we import episodes and keep them in sync daily."),
        ("Spike: smart speaker SDKs", 5, "spike", "speaker", {"spike": True}, "Which speaker platforms can play a live stream by voice? Nobody here has built one."),
        ("Station payouts", 13, "story", "pay", {}, "Pay stations their share of listener support each month."),
        ("Keyboard shortcuts for the web player", 2, "story", "web", {"solo": True}, "Space plays and pauses, arrows change the volume, M mutes. A ? key shows the help overlay."),
        ("Remember the last volume per station", 1, "story", "web", {"solo": True}, "Store the volume per station in local storage and restore it on play."),
        ("Wrong time zone on the show schedule", 3, "bug", None, {}, "Schedules show UTC times for listeners in other zones."),
        ("Upgrade the audio player library to v5", 5, "chore", "web", {}, "v4 is out of support. The upgrade changes the buffering API."),
        ("Dark mode for the station dashboard", 3, "story", "dash", {"solo": True}, "Follow the system setting; same tokens as the listener app."),
        ("Weekly email digest for station owners", 5, "story", "dash", {}, "Monday email: listeners, peak, top shows, chat stats."),
    ]
    for i, (title, p, typ, ep, opts, body) in enumerate(backlog):
        acc = [] if opts.get("spike") else [{"text": "Criteria agreed with the crew", "done": False}]
        if opts.get("solo"):
            acc = [{"text": "Behaves as described", "done": False}, {"text": "Covered by a test", "done": False}]
        b.add(title, p, "backlog", type=typ, created=now - dt.timedelta(days=30 - i), epic=E[ep] if ep else None, body=body,
              acceptance=acc, priority=1 if i < 2 else 2, solo=opts.get("solo", False), spike=opts.get("spike", False))
    for i, title in enumerate(["Show song lyrics when the station provides them", "Listener profiles with favourite stations",
                               "High-contrast theme"]):
        b.add(title, None, "backlog", created=now - dt.timedelta(days=12 - i), epic=E["a11y"] if i == 2 else None, priority=3)
    prop1 = b.add("Add retry with backoff to the stream health checker", None, "backlog", type="task", labels=["agent-proposed"],
                  created=now - dt.timedelta(hours=26),
                  body="While working on the chat rate limit I saw the health checker retries instantly and floods a station "
                       "while it is down. Suggest exponential backoff (1 s, 2 s, 4 s ... up to 60 s).",
                  acceptance=[{"text": "Backoff doubles up to 60 s", "done": False}, {"text": "Resets after a success", "done": False}])
    prop2 = b.add("Remove unused analytics events from the web player", None, "backlog", type="chore", labels=["agent-proposed"],
                  created=now - dt.timedelta(days=2, hours=4),
                  body="14 events are sent but no dashboard reads them. Removing them saves 9 KB and some listener data.")
    prop1["by"] = prop2["by"] = None
    b.write()

    ev = []

    def E_(when, kind, text, card=None, user=None, agent=None):
        ev.append((when, kind, text, card, user, agent))
    E_(d0, "sprint", "Maya Chen started Sprint 9: %d cards, %d points. Goal: Live chat in beta for five stations." % (len(cur), committed), user=U["maya"])
    for spec in cur:
        r = spec["row"]
        who_u, who_a = r["assignee_user"], r["assignee_agent"]
        if r["started"]:
            if who_a is not None:
                E_(r["started"], "move", "%s claimed %s: Ready -> Doing" % (who_a["name"], M.card_key(r)), r, agent=who_a)
            else:
                E_(r["started"], "move", "%s moved %s: Ready -> Doing" % (C.name_of(who_u), M.card_key(r)), r, user=who_u)
        if r["review_at"] and r["status"] in ("review", "done") and spec is not mute:
            if who_a is not None:
                E_(r["review_at"], "submit", "All criteria ticked, tests green. See the PR.", r, agent=who_a)
            else:
                E_(r["review_at"], "move", "%s moved %s: Doing -> Review" % (C.name_of(who_u), M.card_key(r)), r, user=who_u)
        if r["done_at"]:
            E_(r["done_at"], "move", "Maya Chen approved %s: Review -> Done" % M.card_key(r), r, user=U["maya"])
    mr, pr = mute["row"], prof["row"]
    E_(mr["started"] + dt.timedelta(hours=1), "agent_log", "Read the moderation module. Mutes will live in the chat session store with an expiry.", mr, agent=claude)
    E_(mr["started"] + dt.timedelta(hours=5), "agent_log", "Mute menu done for moderators. Unsure: should a mute survive a page reload? Assuming yes.", mr, agent=claude)
    E_(mr["started"] + dt.timedelta(hours=6), "comment", "Yes, it should survive reloads. Good call.", mr, user=U["theo"])
    E_(mr["review_at"], "submit", "Moderators can mute for 10 min, 1 h or the whole show. Muted listeners see a banner with the time left. "
                                 "Tests: moderation suite, 12 new cases, all green. PR #418.", mr, agent=claude)
    E_(pr["started"] + dt.timedelta(hours=2), "agent_log", "Masking works for the EN list. The FR list has words that are fine in English: adding a language check.", pr, agent=u303)
    E_(pr["started"] + dt.timedelta(hours=20), "agent_log", "Corpus test: 3 false positives in 2,000 messages. Working on word boundaries.", pr, agent=u303)
    E_(now - dt.timedelta(hours=26), "create", "Claude added %s" % M.card_key(prop1["row"]), prop1["row"], agent=claude)
    E_(now - dt.timedelta(days=2, hours=4), "create", "909 added %s" % M.card_key(prop2["row"]), prop2["row"], agent=a909)
    E_(now - dt.timedelta(days=2), "agent", "Kofi Mensah paused 909.", user=U["kofi"])
    E_(now - dt.timedelta(hours=40), "comment", "Blocked until the station sends the certificate. Pinged them again.", push["row"], user=U["ines"])
    E_(now - dt.timedelta(hours=2), "comment", "Looks good. One question on the paging before I approve.", hist["row"], user=U["maya"])
    E_(now - dt.timedelta(minutes=12), "agent_log", "Waiting for review feedback on %s." % M.card_key(mr), mr, agent=claude)
    for when, kind, text, card, user, agent in ev:
        M.log(t, kind, text, card=card, user=user, agent=agent, when=when, demo=True)
    return t


PIXL_TITLES = [
    ("Menu page with today's breads", "story"), ("Add to basket", "story"), ("Pick-up time slots", "story"), ("Order confirmation email", "story"),
    ("Fix basket total rounding", "bug"), ("Allergen badges on products", "story"), ("Sold-out switch for the bakers", "story"),
    ("Photo upload for products", "story"), ("Fix slot picker on Safari", "bug"), ("Opening hours footer", "task"),
    ("Pre-order cakes 48 h ahead", "story"), ("Gift message on cake orders", "story"), ("Daily orders print sheet", "story"),
    ("Speed up the menu page", "story"), ("Cookie banner", "chore"), ("Fix double orders on slow networks", "bug"),
    ("Croissant of the week banner", "story"), ("Order history for regulars", "story"), ("Write a README for the bakers", "chore"),
    ("Set up error reporting", "chore"),
]


def _pixl(rng, U, now, today):
    t = app_tables.teams.add_row(
        name="Pixel Bakery", key="PIXL", mission="Online ordering for a neighbourhood bakery: pick a slot, pick up warm bread.",
        level=1, join_code=None, owner=U["lena"], created=now - dt.timedelta(days=38), next_number=1, sprint_days=14,
        wip={"ready": 6, "doing": 3, "review": 2}, dod=["Works on a phone", "The bakers tried it", "Merged to main"],
        agent_rules=M.DEFAULT_AGENT_RULES, level_log=[{"level": 1, "at": C.iso(now - dt.timedelta(days=38)), "by": "Lena Park", "forced": False}],
        is_demo=True)
    for k, role in (("lena", "owner"), ("kofi", "member")):
        app_tables.members.add_row(team=t, user=U[k], role=role, joined=now - dt.timedelta(days=38), is_demo=True)
    claude = app_tables.agents.add_row(team=t, name="Claude", kind="Claude Code", color="#ff7a1a", max_wip=1, token_hash=None, token_hint="",
                                       active=True, created=now - dt.timedelta(days=20), created_by=U["lena"],
                                       last_seen=now - dt.timedelta(hours=5), is_demo=True)
    b = Builder(t, rng, U["lena"])
    humans = [U["lena"], U["kofi"]]
    for i, (title, typ) in enumerate(PIXL_TITLES):
        done = now - dt.timedelta(days=33 - i * 1.65 + rng.uniform(-0.4, 0.4))
        p = rng.choice([1, 2, 2, 3, 3, 5])
        solo = p <= 3 and rng.random() < 0.5
        ag = solo and i >= 10 and rng.random() < 0.6
        st = done - dt.timedelta(days=0.5 + p * 0.6 + rng.uniform(0, 1.5))
        kw = {"assignee_agent": claude} if ag else {"assignee_user": rng.choice(humans)}
        gated = i >= 4 or rng.random() < 0.3
        b.add(title, p if gated else None, "done", type=typ, solo=solo, gated=gated, created=st - dt.timedelta(days=rng.uniform(1, 6)),
              started=st, review_at=done - dt.timedelta(hours=rng.uniform(1, 8)), done_at=done, body="Shipped.",
              acceptance=[{"text": "The bakers are happy", "done": True}], **kw)
    current = [
        ("Loyalty stamp card", 5, "doing", {"assignee_user": U["lena"]}, False, "Every 10th loaf is free. Stamps live on the account.", now - dt.timedelta(days=2)),
        ("Fix basket emptying after login", 2, "doing", {"assignee_agent": claude, "type": "bug"}, True,
         "Logging in mid-order loses the basket. Merge the guest basket into the account.", now - dt.timedelta(hours=7)),
        ("Bakers' order dashboard", 5, "review", {"assignee_user": U["kofi"]}, False, "Today's orders by pick-up slot, for the kitchen tablet.", now - dt.timedelta(hours=30)),
        ("Show prices with tax included", 1, "ready", {}, True, "Customers want to see the real total before checkout, tax included.", None),
        ("Gluten-free filter on the menu", 2, "ready", {}, True, "A toggle that hides every product with gluten in it.", None),
        ("SMS when the order is ready", 3, "ready", {}, False, "Text the customer when the bakers mark an order ready.", None),
        ("Seasonal menu switcher", None, "ready", {}, False, "Bakers swap the whole menu for the holidays.", None),
    ]
    for title, p, st, kw, solo, body, started in current:
        acc = [{"text": "Behaves as described", "done": st == "review"}, {"text": "Works on a phone", "done": st == "review"}]
        b.add(title, p, st, solo=solo, created=now - dt.timedelta(days=rng.uniform(3, 10)), started=started,
              review_at=now - dt.timedelta(hours=9) if st == "review" else None,
              moved_at=(now - dt.timedelta(hours=9)) if st == "review" else (started or now - dt.timedelta(days=2)),
              body=body, acceptance=acc, by=U["lena"], **kw)
    for i, title in enumerate(["Gift cards", "Wholesale orders for cafés", "Instagram feed on the home page", "Delivery by bike",
                               "Recipe blog", "Customer reviews", "Bread subscription", "Print labels for boxes"]):
        b.add(title, rng.choice([None, None, 3, 5, 8]), "backlog", created=now - dt.timedelta(days=20 - i), priority=rng.choice([2, 3]),
              by=U["lena"])
    b.write()
    M.log(t, "crew", "Lena Park started the crew at level 1 (KANBAN).", user=U["lena"], when=now - dt.timedelta(days=38), demo=True)
    for spec in b.specs:
        r = spec["row"]
        if r["status"] in ("doing", "review") and r["assignee_agent"] is not None:
            M.log(t, "move", "Claude claimed %s: Ready -> Doing" % M.card_key(r), card=r, agent=claude, when=r["started"], demo=True)
            M.log(t, "agent_log", "Found it: the basket lives in the session and signing in starts a new one. Merging them now.", card=r,
                  agent=claude, when=r["started"] + dt.timedelta(hours=3), demo=True)
        elif r["status"] == "done" and r["assignee_agent"] is not None:
            M.log(t, "submit", "Done and tested on a phone.", card=r, agent=claude, when=r["review_at"], demo=True)
    return t


def remove(remember=True):
    for t in app_tables.teams.search(is_demo=True):
        M.delete_team_rows(t)
    for name in DEMO_TABLES:
        for r in getattr(app_tables, name).search(is_demo=True):
            r.delete()
    for u in app_tables.users.search(is_demo=True):
        u.delete()
    if remember:
        C.set_setting("demo", "removed")
    return counts()


def counts():
    out = {"users": len(app_tables.users.search(is_demo=True))}
    for name in ("teams", "cards", "agents", "sprints", "epics"):
        out[name] = len(getattr(app_tables, name).search(is_demo=True))
    return out
