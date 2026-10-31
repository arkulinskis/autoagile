"""Alerts: tell the crew when something needs a human, without notification spam.

Kinds (each can be switched off per crew):
  submitted    an agent handed in work for review (sent straight away)
  review_wait  work has waited in Review longer than the crew's limit (24 hours unless changed)
  blocked      someone flagged a card blocked
  wip          Doing or Review went over its WIP limit
  sprint_end   the sprint ends tomorrow, or ended and isn't closed
  request      a request passed the crew's answer promise (Requests.py)
Channels: one webhook set by the owner (Slack, Microsoft Teams, Mattermost and Discord, or plain JSON for
anything else), and an email digest for members who switch it on for themselves.
Every alert is written once to the alerts table under a dedupe key, so a condition that stays true is announced
once, not every hour. sweep(t) checks the conditions; it runs when someone opens the Deck and when agents use the
API, at most every SWEEP_MINUTES per crew. Demo crews keep the history but never send anything.
"""
import json
import re

import anvil.email
import anvil.http
import anvil.server
from anvil.tables import app_tables

from . import common as C
from . import Model as M

KINDS = [("submitted", "An agent hands in work"), ("review_wait", "Work waits too long in Review"), ("blocked", "A card is blocked"),
         ("wip", "A column goes over its WIP limit"), ("sprint_end", "A sprint ends tomorrow or is overdue"),
         ("request", "A request passes the answer promise")]
FORMATS = {"slack": "Slack, Teams, Mattermost (text)", "discord": "Discord", "json": "JSON (anything else)"}
SWEEP_MINUTES = 10
BAD_HOST = re.compile(r"^(localhost|127\.|10\.|0\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.|169\.254\.|metadata\b)|\.(local|internal|localhost)$", re.I)


def settings(t):
    a = dict(t["alerts"] or {})
    kinds = dict({k: True for k, _ in KINDS}, **(a.get("kinds") or {}))
    try:
        hours = int(a.get("review_hours") or 24)
    except (TypeError, ValueError):
        hours = 24
    return {"webhook": a.get("webhook") or "", "format": a.get("format") if a.get("format") in FORMATS else "slack",
            "review_hours": hours, "kinds": kinds}


def clean_webhook(url):
    """'' or a safe https URL. Raises ValueError with a readable message."""
    url = C.text(url, 500)
    if not url:
        return ""
    m = re.match(r"^https://([A-Za-z0-9.-]+)(:\d{2,5})?(/[^\s]*)?$", url)
    if not m or BAD_HOST.search(m.group(1)) or re.match(r"^[\d.]+$", m.group(1)) or "." not in m.group(1):
        raise ValueError("Use an https:// webhook address from Slack, Teams, Discord or your own server.")
    return url


def _origin():
    try:
        return anvil.server.get_app_origin() or ""
    except Exception:
        return ""


def alert_dict(r):
    return {"id": r.get_id(), "kind": r["kind"], "text": r["text"], "created": C.iso(r["created"]), "sent": r["sent"] or {},
            "card": {"key": M.card_key(r["card"]), "title": r["card"]["title"]} if r["card"] is not None else None}


# ------------------------------------------------------------------------------------------- sending
def payload(fmt, t, rows, origin):
    head = "AutoAgile // %s (%s)" % (t["key"], t["name"])
    items = []
    for r in rows:
        link = "%s/#card/%s" % (origin, M.card_key(r["card"])) if (origin and r["card"] is not None) else ""
        items.append((r, link))
    if fmt == "discord":
        txt = "**%s**\n" % head + "\n".join("- %s%s" % (r["text"], " <%s>" % l if l else "") for r, l in items)
        return {"content": txt[:1900]}
    if fmt == "json":
        return {"app": "AutoAgile", "crew": {"key": t["key"], "name": t["name"]},
                "alerts": [{"kind": r["kind"], "text": r["text"], "card": M.card_key(r["card"]) if r["card"] is not None else None,
                            "url": l or None, "at": C.iso(r["created"])} for r, l in items]}
    txt = "*%s*\n" % head + "\n".join("- %s%s" % (r["text"], " <%s|open>" % l if l else "") for r, l in items)
    return {"text": txt[:3500]}


def post(url, body):
    """POST JSON. Returns "sent" or "failed: ..." (never raises: an alert must not break the page)."""
    try:
        anvil.http.request(url, method="POST", data=json.dumps(body), headers={"Content-Type": "application/json"}, timeout=8)
        return "sent"
    except Exception as e:
        return "failed: %s" % (str(getattr(e, "status", "") or e) or "no reply")[:90]


def deliver(t, rows):
    if not rows:
        return {}
    if t["is_demo"]:
        for r in rows:
            r["sent"] = {"skipped": "demo crew"}
        return {"skipped": "demo crew"}
    st, origin, result = settings(t), _origin(), {}
    if st["webhook"]:
        result["webhook"] = post(st["webhook"], payload(st["format"], t, rows, origin))
    emails = [m["user"]["email"] for m in app_tables.members.search(team=t, notify=True) if m["user"] is not None and m["user"]["email"]]
    if emails:
        lines = ["- %s%s" % (r["text"], "\n  %s/#card/%s" % (origin, M.card_key(r["card"])) if (origin and r["card"] is not None) else "")
                 for r in rows]
        subject = "AutoAgile // %s: %s" % (t["key"], rows[0]["text"][:70] if len(rows) == 1 else "%d alerts" % len(rows))
        body = ("Crew %s (%s)\n\n%s\n\nYou get these because you switched on email alerts for this crew in AutoAgile "
                "(Crew settings -> Alerts). Switch them off there.\n") % (t["name"], t["key"], "\n".join(lines))
        sent = 0
        for e in emails[:30]:
            try:
                anvil.email.send(to=e, from_name="AutoAgile", subject=subject, text=body)
                sent += 1
            except Exception:
                pass
        result["email"] = sent
    for r in rows:
        r["sent"] = result
    return result


def fire(t, kind, dedupe, text, card=None, now=True):
    """Record one alert (once per dedupe key) and, with now=True, send it. Returns the new row or None."""
    if not settings(t)["kinds"].get(kind, True):
        return None
    dedupe = C.text(dedupe, 200)
    if len(app_tables.alerts.search(team=t, dedupe=dedupe)):
        return None
    row = app_tables.alerts.add_row(team=t, kind=kind, dedupe=dedupe, card=card, text=C.text(text, 500), created=C.now(), sent={},
                                    is_demo=bool(t["is_demo"]))
    if now:
        deliver(t, [row])
    return row


def sweep(t, force=False):
    """Check the crew's standing conditions and send what is new, as one digest. Throttled per crew."""
    last = t["alerts_checked"]
    if not force and last is not None and (C.now() - last).total_seconds() < SWEEP_MINUTES * 60:
        return []
    t["alerts_checked"] = C.now()
    st, new = settings(t), []

    def add(kind, dedupe, text, card=None):
        r = fire(t, kind, dedupe, text, card, now=False)
        if r is not None:
            new.append(r)
    cards = list(app_tables.cards.search(team=t))
    for c in cards:
        if c["status"] == "review" and c["review_at"] is not None:
            waited = (C.now() - c["review_at"]).total_seconds() / 3600.0
            if waited > st["review_hours"]:
                who = c["assignee_agent"]["name"] if c["assignee_agent"] is not None else C.name_of(c["assignee_user"]) if c["assignee_user"] else "someone"
                add("review_wait", "review_wait:%s:%s" % (c.get_id(), C.iso(c["review_at"])),
                    "%s has waited %d hours for review: %s (work by %s)" % (M.card_key(c), round(waited), c["title"], who), c)
    wip = dict(M.DEFAULT_WIP, **(t["wip"] or {}))
    for col in ("doing", "review"):
        n = len([c for c in cards if c["status"] == col])
        if n > wip[col]:
            add("wip", "wip:%s:%s" % (col, C.now().date().isoformat()),
                "%s is over its WIP limit: %d cards, the limit is %d. Stop starting, start finishing." % (M.STATUS_LABEL[col], n, wip[col]))
    if (t["level"] or 1) >= 2:
        for s in app_tables.sprints.search(team=t, state="active"):
            left = (M.as_date(s["end"]) - M.team_today()).days
            if left == 1:
                add("sprint_end", "sprint_end:%s:soon" % s.get_id(), "%s ends tomorrow. Goal: %s" % (s["name"], s["goal"] or "none set"))
            elif left < 0:
                add("sprint_end", "sprint_end:%s:over" % s.get_id(), "%s ended %d day%s ago and is still open. Close it and run the retro." %
                    (s["name"], -left, "" if left == -1 else "s"))
    promise = t["promise_days"] or 14
    for r in app_tables.requests.search(team=t, status="open"):
        if r["created"] is not None and (C.now() - r["created"]).days > promise:
            add("request", "request:%s" % r.get_id(), "A request has waited %d days for an answer (the promise is %d): %s" %
                ((C.now() - r["created"]).days, promise, r["title"]))
    deliver(t, new)
    return new


# ------------------------------------------------------------------------------------------- callables
def _member_row(t, me):
    return app_tables.members.get(team=t, user=me)


@anvil.server.callable(require_user=True)
def get_alerts(team_id):
    t, me, role = M.access(team_id)
    rows = sorted(app_tables.alerts.search(team=t), key=lambda r: r["created"], reverse=True)[:40]
    m = _member_row(t, me)
    st = settings(t)
    can_edit = role == "owner" or (bool(t["is_demo"]) and C.is_admin(me))
    return {"settings": dict(st, webhook=st["webhook"] if can_edit else ("set" if st["webhook"] else "")),
            "kinds": [{"id": k, "label": v} for k, v in KINDS], "formats": [{"id": k, "label": v} for k, v in FORMATS.items()],
            "can_edit": can_edit, "member": m is not None, "notify": bool(m and m["notify"]), "demo": bool(t["is_demo"]),
            "history": [alert_dict(r) for r in rows]}


@anvil.server.callable(require_user=True)
def save_alerts(team_id, fields):
    t, me, role = M.access(team_id, owner=True)
    if not isinstance(fields, dict):
        return C.fail("Nothing to save.")
    cur = dict(t["alerts"] or {})
    if "webhook" in fields:
        if t["is_demo"] and fields["webhook"]:
            return C.fail("Demo crews never send alerts. Start your own crew to connect a webhook.")
        try:
            cur["webhook"] = clean_webhook(fields["webhook"])
        except ValueError as e:
            return C.fail(str(e))
    if "format" in fields:
        if fields["format"] not in FORMATS:
            return C.fail("Pick a webhook format from the list.")
        cur["format"] = fields["format"]
    if "review_hours" in fields:
        try:
            h = int(fields["review_hours"])
        except (TypeError, ValueError):
            return C.fail("Review wait is a number of hours.")
        if not 1 <= h <= 168:
            return C.fail("Review wait is between 1 and 168 hours.")
        cur["review_hours"] = h
    if "kinds" in fields and isinstance(fields["kinds"], dict):
        cur["kinds"] = {k: bool(fields["kinds"].get(k, True)) for k, _ in KINDS}
    t["alerts"] = cur
    M.log(t, "crew", "%s changed the crew's alert settings." % C.name_of(me), user=me, demo=bool(t["is_demo"]))
    return C.ok(settings=settings(t))


@anvil.server.callable(require_user=True)
def test_alerts(team_id):
    t, me, role = M.access(team_id, owner=True)
    st = settings(t)
    if t["is_demo"]:
        return C.fail("Demo crews never send alerts.")
    if not st["webhook"]:
        return C.fail("Save a webhook address first.")
    if C.rate_limited("test_alerts", 10, 3600):
        return C.fail("That's a lot of tests this hour. Try again later.")
    row = app_tables.alerts.add_row(team=t, kind="test", dedupe="test:%s" % C.iso(C.now()), card=None, created=C.now(), sent={},
                                    text="Test from %s: alerts for %s are wired up." % (C.name_of(me), t["name"]), is_demo=False)
    res = post(st["webhook"], payload(st["format"], t, [row], _origin()))
    row["sent"] = {"webhook": res}
    if res != "sent":
        return C.fail("The webhook didn't accept it (%s). Check the address." % res)
    return C.ok(result=res)


@anvil.server.callable(require_user=True)
def set_notify(team_id, on):
    t, me, role = M.access(team_id)
    m = _member_row(t, me)
    if m is None or t["is_demo"]:
        return C.fail("Join a crew of your own to get its alerts by email.")
    m["notify"] = bool(on)
    return C.ok(notify=bool(on))
