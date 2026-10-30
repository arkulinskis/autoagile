# AutoAgile

An agile work board in the spirit of Jira, monday.com, Asana and Podio, built for **crews of humans and AI software
developers**. Young crews start in Kanban; their own data unlocks Scrum sprints, then a 3-month forecast, then a year
roadmap. Story points come from **complexity gates** (six questions) instead of guesswork, and AI agents work the board
through an HTTP API: pull the next card, claim, log, tick criteria, hand in for human review. 90s techno look.
Built on [Anvil](https://anvil.works).

- **App repo:** github.com/arkulinskis/autoagile (branch `master`). Anvil pulls `master`.
- **Live:** not published yet (expected https://autoagile.anvil.app).

## What it does

**For visitors:** a landing page (the four levels, a live complexity-gates widget, the agent API, features, FAQ),
sign-up with email and password, feedback form, Privacy & Terms (`#legal`).

**Crews** (`#crew`, `#crew/new`, `#crew/join`): start a crew (name, card prefix like NOVA, mission, start at level 1
Kanban or 2 Scrum), invite with a 6-character join code, roles (owner / member), hand over ownership, remove people,
WIP limits per column, sprint length, Definition of Done, leave or delete (type the prefix). Two **demo crews** are an
open sandbox for every signed-in person: **NOVA** (Nova FM, level 4, 8 closed sprints, 3 agents) and **PIXL** (Pixel
Bakery, level 1 Kanban, 4 of 6 checks towards Scrum). The header's crew chip switches crews.

**Deck** (`#deck`, home): LCD stats (cards this week + sparkline, average per week, median cycle time, Doing vs WIP,
Review vs WIP), a scrolling agent ticker, "Needs a human" (Review + blocked), your cards, alerts (over WIP, stale work,
reviews waiting over a day, unestimated Ready cards, sprint ending/over, level-up available), the maturity meter, the
sprint burndown, agents with live state, and the live feed.

**Board** (`#board`): Ready / Doing / Review / Done; at level 1 the Kanban flow, from level 2 the running sprint (with
its goal). Drag and drop between columns and within them; WIP limits glow red and ask before you break them; filters
(All / Mine / Humans / Agents) and search; aging on Doing/Review cards; blocked cards striped; phones show one column at a time.

**Backlog** (`#backlog`): a tracker-style ranked list (top / up / down), filters (unestimated, agent-ready, bugs), quick
add with a syntax: `#bug` type, `!1` priority, `~5` points by hand, `@name` assign a person or agent, `+epic`, other
`#words` become labels. From level 2: sprint planning panels (capacity bar against average velocity, add/remove cards,
plan up to 3 sprints, start a sprint). **Estimation Party** (`#backlog/party`): every unestimated card through the gates,
keyboard 1-4 per gate, Enter saves, S skips.

**Cards** (`#card/NOVA-12`): editable title, markdown-ish description, acceptance criteria checklist, the complexity
gates with the points ladder (1 TICK, 2 PULSE, 3 LOOP, 5 GROOVE, 8 BUILD, 13 DROP, 21 RAVE), verdicts (spike first,
split it), agent fit (AGENT SOLO / AGENT + HUMAN / HUMAN LED), the Definition of Ready for agents (6 checks), the
**agent brief** (one markdown spec: goal, criteria, gates, DoD, house rules, how to report back; copy or preview),
status buttons (+ Approve → Done from Review), assignee (people and agents), type, priority, epic, sprint, manual
points, labels, blocked + reason, links, activity timeline with comments and agent logs, delete.

**Plan** (`#plan/<tab>`):
- **Level:** the 4-level ladder, the checks for the next level with values vs targets, Level up (with a LEVEL UP
  rave), Force it (recorded as forced), step back, level history.
  - 1→2: 25 cards done, 6 weeks of history, weekly throughput spread ≤ 50%, WIP respected now, nothing stale in Doing, 70% of recent cards gated.
  - 2→3: 3 closed sprints, velocity within ±25%, 75% of commitments finished, 2 sprints of estimated backlog.
  - 3→4: 6 closed sprints, 80% predictability, velocity spread ≤ 20%, 3 sized epics.
- **Sprints** (level 2+): running sprint with goal and burndown (+ table), close (carry unfinished to the next sprint or
  the backlog) then the retro (LOUDER / MUTE / REMIX + action items), velocity chart, past sprints with predictability.
- **3 months** (level 3+): capacity range from the last 6 sprints, epics filled into the next ~6 sprints, bars to the
  likely sprint with optimistic/pessimistic whiskers, confidence SAFE / LIKELY / STRETCH / WON'T FIT.
- **Year** (level 4): four quarters with capacity vs load (overbooked flagged), epics per quarter with on track / at
  risk / LATE, move epics between quarters, a Later bucket.
- **Epics:** create/edit (size S/M/L/XL, quarter, status, colour), rank, progress.
Locked tabs show a dimmed preview and what unlocks them.

**Agents** (`#agents`): AI developers as crew members (name, kind such as Claude Code/Codex/Cursor/Custom, own WIP limit).
A token is shown once (only its SHA-256 is stored); pause/resume, new token, edit, remove. The review queue of agent
work, house rules (in every brief), an **agent console** that runs the real API as any agent (`help`, `whoami`, `next`,
`cards review`, `claim NOVA-12`, `log NOVA-12 text`, `check NOVA-12 0`, `submit NOVA-12 summary`, `release`, `propose`),
the HTTP API reference with curl examples, a CLAUDE.md snippet, and the agent feed.

**Agent HTTP API** (`<app>/_/api/agent/<op>`, `Authorization: Bearer aa_…` or `?token=`): `whoami`, `next`, `cards`,
`card`, `claim`, `log`, `check`, `submit`, `release`, `propose`, plus `manifest` (no token). Agents respect their own WIP
limit and the crew's Doing limit (409), paused agents get 423, bad tokens 401. Agents never move cards to Done.

**Insights** (`#insights`): throughput (12 weeks), cycle-time scatter with 50th/85th percentiles (humans vs agents),
cumulative flow, velocity, gate accuracy (median days per points value), agents vs humans (points, review wait), aging
WIP. Every chart has hover tooltips and a table view.

**For admins** (`#admin`; arkulinskis@gmail.com becomes an admin on first sign-in): feedback inbox, users, **Crews**
(every crew with owner and size; delete a real crew for abuse), demo data (remove / reload both demo crews).

## Setting it up in Anvil (once)

1. In the Anvil editor: **Create app → Clone from GitHub**, and paste `https://github.com/arkulinskis/autoagile`.
2. **Users** service: email + password, sign-up allowed (already set in `anvil.yaml`; check it).
3. Open the app in the editor. If it shows a **Schema Mismatch** alert, choose **"The schema of the source code is correct"** so Anvil creates the tables.
4. **Run** it and sign up with **arkulinskis@gmail.com** straight away (that account becomes the admin).
5. **Publish** (Publish → public URL, or your own domain).

## Working on it

See `.claude/skills/autoagile/SKILL.md`. In short:

```
python -I tools/check.py --ui                    # syntax, server tests, headless UI tests → ALL CHECKS PASSED
python -I tools/preview/devserver.py 8765        # the app on in-memory data: http://localhost:8765/  (?as=ana#deck, ?as=admin#admin)
python tools/deploy.py                           # dry run (needs PyYAML, so no -I)
python tools/deploy.py --push "Message"          # deploy: commit + push to GitHub, Anvil pulls it
```

## Project layout

```
web/            the interface: core.js/core.css (engine + techno design tokens), app.js (header with crew chip, footer), pages/*.html
                pages/_aa.html is the shared kit (window.AA): crews, card chips, gates widget, LCDs, windows, charts, rave
client_code/    Main.py (the only Anvil form: bridge to the server, sign-in), legal.py
server_code/    Gates (points rules), Model (access + dicts), Teams, Cards, Sprints, Plans, Metrics, Agents (+ HTTP API), Deck,
                DemoData, Admin, Accounts, Feedback, common, legal_server
assets/         icon.svg (three rising bars: columns, levels, an equaliser) + generated PNG icons
tools/          sync_to_anvil.py (settings + table schema), deploy.py, check.py, preview/ (dev server, UI tests, screenshots), testing/
```
