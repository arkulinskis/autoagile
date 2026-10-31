"""Requests: the crew's front door for everyone who isn't on the board (customers, managers, other teams).

Why: in big trackers, requests sit for years with thousands of votes and no answer. Here every request gets an
answer within the crew's promise (14 days unless changed): Accepted (it becomes a backlog card, and the requester
sees it move to Shipped), Later (with a reason) or Declined (with a reason). Open requests show their clock;
overdue ones raise an alert (Alerts.sweep) and show on the Deck.

Who sees what:
  - crew members (and demo sandbox guests): everything, plus the answer buttons (get_requests, answer_request)
  - anyone signed in who has the crew's ask link (#ask/<code>): the crew's name and mission and its requests
    (title, description, requester's name, votes, answer). They can add requests and vote. They never see the board.
"""
import random
import re

import anvil.server
from anvil.tables import app_tables

from . import common as C
from . import Model as M
from . import Cards

STATUSES = ["open", "accepted", "later", "declined"]
CODE_CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
PROMISES = (7, 14, 30)


def new_code():
    return "".join(random.choice(CODE_CHARS) for _ in range(8))


def ensure_code(t):
    if not t["ask_code"]:
        t["ask_code"] = new_code()
    return t["ask_code"]


def team_by_code(code):
    code = re.sub(r"[^A-Z0-9]", "", C.text(code, 20).upper())
    if len(code) != 8:
        return None
    return app_tables.teams.get(ask_code=code)


def promise(t):
    return t["promise_days"] or 14


def request_dict(r, me):
    t = r["team"]
    age = (C.now() - r["created"]).days if r["created"] else 0
    votes = r["votes"] or []
    card = r["card"]
    d = {"id": r.get_id(), "title": r["title"], "body": r["body"] or "", "by": C.name_of(r["by_user"]) if r["by_user"] else "Someone",
         "mine": r["by_user"] is not None and r["by_user"] == me, "votes": len(votes), "voted": me is not None and me.get_id() in votes,
         "status": r["status"] or "open", "answer": r["answer"] or "", "answered_at": C.iso(r["answered_at"]),
         "answered_by": C.name_of(r["answered_by"]) if r["answered_by"] else None, "created": C.iso(r["created"]), "age": age,
         "card": {"key": M.card_key(card), "status": card["status"]} if card is not None else None,
         "shipped": card is not None and card["status"] == "done"}
    if d["status"] == "open":
        d["due_in"] = promise(t) - age
        d["overdue"] = age > promise(t)
    else:
        d["took"] = (r["answered_at"] - r["created"]).days if (r["answered_at"] and r["created"]) else None
    return d


def sorted_requests(t, me):
    rows = [request_dict(r, me) for r in app_tables.requests.search(team=t)]
    open_ = sorted([d for d in rows if d["status"] == "open"], key=lambda d: (-d["votes"], d["created"] or ""))
    done = [d for d in rows if d["status"] != "open"]
    done.sort(key=lambda d: d["answered_at"] or "", reverse=True)
    return open_ + done


def stats(t, reqs):
    answered = [d for d in reqs if d["status"] != "open" and d.get("took") is not None]
    took = sorted(d["took"] for d in answered)
    on_time = len([x for x in took if x <= promise(t)])
    return {"open": len([d for d in reqs if d["status"] == "open"]), "overdue": len([d for d in reqs if d.get("overdue")]),
            "answered": len(answered), "median_days": took[len(took) // 2] if took else None,
            "on_time": round(100.0 * on_time / len(took)) if took else None,
            "shipped": len([d for d in reqs if d["shipped"]])}


def _access_request(request_id, code=None, crew_only=False):
    """(request row, team, me, crew role or None). Crew members always; code holders unless crew_only."""
    me = C.require_user()
    r = C.row_by_id(app_tables.requests, request_id)
    if r is None:
        raise anvil.server.PermissionDenied("That request doesn't exist any more.")
    t = r["team"]
    try:
        _, _, role = M.access(t.get_id())
        return r, t, me, role
    except anvil.server.PermissionDenied:
        if crew_only:
            raise
    if code and team_by_code(code) == t:
        return r, t, me, None
    raise anvil.server.PermissionDenied("Open the crew's ask link to do that.")


# ------------------------------------------------------------------------------------------- crew side
@anvil.server.callable(require_user=True)
def get_requests(team_id):
    t, me, role = M.access(team_id)
    reqs = sorted_requests(t, me)
    return {"crew": {"id": t.get_id(), "key": t["key"], "name": t["name"], "demo": bool(t["is_demo"])},
            "ask_code": ensure_code(t), "promise_days": promise(t), "promises": list(PROMISES),
            "can_admin": role == "owner" or (bool(t["is_demo"]) and C.is_admin(me)),
            "requests": reqs, "stats": stats(t, reqs)}


@anvil.server.callable(require_user=True)
def answer_request(request_id, status, answer=""):
    r, t, me, role = _access_request(request_id, crew_only=True)
    if status not in STATUSES:
        return C.fail("Answer with accepted, later or declined.")
    answer = C.text(answer, 1000, multiline=True)
    if status in ("later", "declined") and len(answer) < 10:
        return C.fail("Say why in a sentence (10 characters or more). A reason is what makes a 'no' fair.")
    upd = {"status": status, "answer": answer}
    if status == "open":
        upd.update(answered_at=None, answered_by=None)
    else:
        upd.update(answered_at=C.now(), answered_by=me)
    if status == "accepted" and r["card"] is None:
        body = "Requested by %s on %s.\n\n%s" % (C.name_of(r["by_user"]) if r["by_user"] else "someone",
                                                  C.iso(r["created"])[:10], r["body"] or "")
        if answer:
            body += "\n\nCrew note: %s" % answer
        upd["card"] = Cards.new_card(t, r["title"][:200], user=me, body=body.strip(), labels=["request"],
                                     source="request:%s" % r.get_id(), is_demo=bool(t["is_demo"]))
    r.update(**upd)
    M.log(t, "request", "%s answered a request (%s): %s" % (C.name_of(me), status, r["title"]), card=r["card"], user=me,
          demo=bool(t["is_demo"]))
    return C.ok(request=request_dict(r, me))


@anvil.server.callable(require_user=True)
def new_ask_code(team_id):
    t, me, role = M.access(team_id, owner=True)
    t["ask_code"] = new_code()
    return C.ok(code=t["ask_code"])


# ------------------------------------------------------------------------------------------- everyone with the link
@anvil.server.callable(require_user=True)
def ask_page(code):
    me = C.require_user()
    t = team_by_code(code)
    if t is None:
        return C.fail("That ask link doesn't work. Ask the crew for a fresh one.")
    reqs = sorted_requests(t, me)
    member = app_tables.members.get(team=t, user=me) is not None or bool(t["is_demo"])
    return C.ok(crew={"key": t["key"], "name": t["name"], "mission": t["mission"] or "", "demo": bool(t["is_demo"]),
                      "id": t.get_id() if member else None},
                promise_days=promise(t), requests=reqs, stats=stats(t, reqs))


@anvil.server.callable(require_user=True)
def submit_request(title, body="", team_id=None, code=None):
    me = C.require_user()
    if code:
        t = team_by_code(code)
        if t is None:
            return C.fail("That ask link doesn't work. Ask the crew for a fresh one.")
    else:
        t, me, role = M.access(team_id)
    title = C.text(title, 140)
    if len(title) < 5:
        return C.fail("Give the request a short title (5 characters or more).")
    if C.rate_limited("submit_request", 15, 3600):
        return C.fail("That's a lot of requests in one hour. Try again later.")
    same = [r for r in app_tables.requests.search(team=t, status="open") if (r["title"] or "").lower() == title.lower()]
    if same:
        return C.fail("There is already an open request with that title. Vote for it instead.")
    r = app_tables.requests.add_row(team=t, title=title, body=C.text(body, 3000, multiline=True), by_user=me, votes=[me.get_id()],
                                    status="open", answer="", created=C.now(), is_demo=bool(t["is_demo"]))
    M.log(t, "request", "%s asked for: %s" % (C.name_of(me), title), user=me, demo=bool(t["is_demo"]))
    return C.ok(request=request_dict(r, me))


@anvil.server.callable(require_user=True)
def vote_request(request_id, on=True, code=None):
    r, t, me, role = _access_request(request_id, code=code)
    votes = [v for v in (r["votes"] or []) if v != me.get_id()]
    if on:
        votes.append(me.get_id())
    r["votes"] = votes
    return C.ok(request=request_dict(r, me))
