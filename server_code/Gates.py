"""Complexity gates: estimate story points by answering six questions instead of guessing a number.

Each gate has four answers scored 0-3. The total picks a rung on the points ladder (Fibonacci), and
red answers act as floors (an answer at 2 means at least 3 points, an answer at 3 at least 5).
The same rules run in the browser (AA.gateScore in web/pages/_aa.html): keep the two in step.

Also here: agent fit (can an AI developer take this card alone?) and the Definition of Ready checks.
Pure functions, no tables: Cards, Agents and DemoData all use them.
"""

GATES = [
    {"id": "scope", "name": "Scope", "q": "How much of the system does it touch?",
     "opts": ["One file or setting", "One module", "Several modules", "Across services or teams"]},
    {"id": "clarity", "name": "Clarity", "q": "How clear is what done looks like?",
     "opts": ["Crystal: criteria written", "Mostly clear", "Fuzzy: open questions", "Unknown: needs research"]},
    {"id": "novelty", "name": "Novelty", "q": "Have we done this before?",
     "opts": ["Routine", "Like past work", "New to this crew", "Nobody has done it"]},
    {"id": "deps", "name": "Dependencies", "q": "What must we wait on?",
     "opts": ["Nothing", "One thing we control", "Another team or API", "Several outside parties"]},
    {"id": "risk", "name": "Risk", "q": "What breaks if it goes wrong?",
     "opts": ["Nothing much", "A small feature", "User data or money", "Production or security"]},
    {"id": "verify", "name": "Verify", "q": "How do we prove it works?",
     "opts": ["Quick automated test", "Tests plus a look", "Manual QA needed", "Hard to test"]},
]
GATE_IDS = [g["id"] for g in GATES]

# (lowest total score, points, rung name)
LADDER = [(0, 1, "TICK"), (2, 2, "PULSE"), (4, 3, "LOOP"), (7, 5, "GROOVE"), (10, 8, "BUILD"), (13, 13, "DROP"), (16, 21, "RAVE")]
FLOORS = {2: 3, 3: 5}          # any answer at this level -> at least this many points
POINTS = [p for _, p, _ in LADDER]
SPLIT_AT = 13                  # this many points or more: split the card
RUNG = {p: n for _, p, n in LADDER}

FIT = {
    "solo": "AGENT SOLO",      # an AI developer can take it end to end; a human reviews
    "pair": "AGENT + HUMAN",   # an agent can do most of it with a human close by
    "human": "HUMAN LED",      # needs judgement, research or access an agent shouldn't have
}


def config():
    """What the browser needs to draw the gates widget."""
    return {"gates": GATES, "ladder": [{"min": m, "points": p, "name": n} for m, p, n in LADDER],
            "floors": {str(k): v for k, v in FLOORS.items()}, "split_at": SPLIT_AT, "fit": FIT}


def clean(answers):
    """{gate id: 0..3} from whatever the browser sent; unknown keys and bad values dropped."""
    out = {}
    if not isinstance(answers, dict):
        return out
    for gid in GATE_IDS:
        v = answers.get(gid)
        if isinstance(v, bool):
            continue
        if isinstance(v, (int, float)) and int(v) == v and 0 <= v <= 3:
            out[gid] = int(v)
    return out


def score(answers):
    """The verdict for a set of answers: points, rung, verdict, agent fit and why."""
    a = clean(answers)
    if len(a) < len(GATE_IDS):
        return {"complete": False, "answered": len(a), "points": None}
    total = sum(a.values())
    points = 1
    for low, p, _ in LADDER:
        if total >= low:
            points = p
    floor = max([FLOORS.get(v, 1) for v in a.values()] + [1])
    floored = floor > points
    points = max(points, floor)
    notes = []
    if floored:
        notes.append("A red answer raised the floor to %d points." % floor)
    verdict = "go"
    if a["clarity"] == 3:
        verdict = "spike"
        notes.append("Clarity is unknown: run a time-boxed spike before building.")
    elif points >= SPLIT_AT:
        verdict = "split"
        notes.append("%d points will not fit one sprint comfortably: split it." % points)
    return {"complete": True, "total": total, "points": points, "rung": RUNG[points], "floored": floored,
            "verdict": verdict, "fit": agent_fit(a, points), "notes": notes}


def agent_fit(a, points):
    if not a or len(a) < len(GATE_IDS) or points is None:
        return None
    if a["clarity"] <= 1 and a["verify"] <= 1 and a["risk"] <= 1 and a["deps"] <= 1 and points <= 5:
        return "solo"
    if a["clarity"] <= 2 and a["risk"] <= 2 and points <= 8:
        return "pair"
    return "human"


def readiness(card):
    """Definition of Ready for an AI developer. card: dict with body, acceptance, gates, points, blocked."""
    a = clean(card.get("gates") or {})
    checks = [
        ("criteria", "Acceptance criteria written", len(card.get("acceptance") or []) >= 1),
        ("context", "Description of 40+ characters", len((card.get("body") or "").strip()) >= 40),
        ("gated", "Estimated with the gates", len(a) == len(GATE_IDS)),
        ("size", "Small: 5 points or less", card.get("points") is not None and card.get("points") <= 5),
        ("clear", "Clarity crystal or mostly clear", a.get("clarity") is not None and a.get("clarity") <= 1),
        ("unblocked", "Not blocked", not card.get("blocked")),
    ]
    passed = sum(1 for c in checks if c[2])
    return {"checks": [{"id": i, "label": l, "ok": bool(o)} for i, l, o in checks], "passed": passed,
            "total": len(checks), "ready": passed == len(checks)}
