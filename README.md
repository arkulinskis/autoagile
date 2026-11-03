# AutoAgile

An agile work board in the spirit of Jira, monday.com, Asana and Podio, built for **crews of humans and AI software
developers**. Young crews start in Kanban; their own data unlocks Scrum sprints, then a 3-month forecast, then a year
roadmap. Story points come from **complexity gates** (six questions) instead of guesswork, and AI agents work the board
through an HTTP API: pull the next card, claim, log, tick criteria, hand in for human review. d3 reports forecast
when work lands; requests from outside the crew always get an answer; Jira and Trello history imports with its dates,
and everything exports any time. 90s techno look.
Built on [Anvil](https://anvil.works).

- **App repo:** github.com/arkulinskis/autoagile (branch `master`). Anvil pulls `master`.
- **Live:** https://autoagile.anvil.app

## What it does

**For visitors:** a landing page (the four levels, a live complexity-gates widget, the agent API, features, FAQ),
sign-up with email and password or Google, feedback form, Privacy & Terms (`#legal`).

**Crews** (`#crew`, `#crew/new`, `#crew/join`): start a crew (name, card prefix like NOVA, mission, start at level 1
Kanban or 2 Scrum), invite with a 6-character join code, roles (owner / member), hand over ownership, remove people,
WIP limits per column, sprint length, Definition of Done, leave or delete (type the prefix). Two **demo crews** are an
open sandbox for every signed-in person: **NOVA** (Nova FM, level 4, 8 closed sprints, 3 agents) and **PIXL** (Pixel
Bakery, level 1 Kanban, 4 of 6 checks towards Scrum). The header's crew chip switches crews.

**Deck** (`#deck`, home): LCD stats (cards this week + sparkline, average per week, median cycle time, Doing vs WIP,
Review vs WIP), a scrolling agent ticker, "Needs a human" (Review + blocked), your cards, alerts (over WIP, stale work,
reviews waiting over a day, unestimated Ready cards, sprint ending/over, level-up available), the maturity meter, the
sprint burndown, agents with live state, and the live feed.

**Board** (`#board`): the crew's columns. Every column belongs to one of four stages (Ready, Doing, Review, Done); Crew
settings can split a stage into several columns (NOVA: Doing -> Build + Test), each with its own WIP limit. At level 1 the
Kanban flow, from level 2 the running sprint (with its goal). Drag and drop between columns and within them; WIP limits glow
red and ask before you break them; **swimlanes** by person, epic, priority or type (dropping a card in another lane
re-assigns it); filters (All / Mine / Humans / Agents) and the **filter language** (`@name #bug-or-label !1 ~5 >3 <8 +epic
is:blocked is:agent is:human is:mine is:unestimated is:ready`, plus words); aging on Doing/Review cards; blocked cards
striped; phones show one column at a time.

**Command palette**: Ctrl K (or `/` when not typing) jumps to any page or card, or adds a card with the quick-add syntax.
`g` + a letter jumps too (`g b` board, `g l` backlog, `g r` reports, `g q` requests...).

**Backlog** (`#backlog`): a tracker-style ranked list (top / up / down), filters (unestimated, agent-ready, bugs, and the
filter language), quick
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

**Reports** (`#reports/<tab>`, drawn with d3 v7.9.0, self-hosted in `assets/`): **burn-up** (crew, a sprint or an epic;
cards or points; a forecast cone from the 15th/50th/85th percentile weeks), **forecast** (Monte Carlo, 5,000 runs of the
real weekly throughput: "when will these N cards be done?" with 50/85/95% dates, and "how many by this date?"), **flow**
(cumulative flow by stage with a brush strip to zoom, Little's law read-out), **cycle time** (control chart, humans vs
agents, 50th/85th lines, rolling average, Shift+scroll zoom, click a dot to open the card), **epic map** (treemap: cards
sized by points, coloured by stage), **work mix** (finished per week by type or by humans/agents). Range 4/12/26 weeks or
all; every chart has tooltips, a table view, CSV download and Print.

**Insights** (`#insights`, linked from Reports): throughput (12 weeks), cycle-time scatter with 50th/85th percentiles
(humans vs agents), cumulative flow, velocity, gate accuracy (median days per points value), agents vs humans (points,
review wait), aging WIP. Every chart has hover tooltips and a table view.

**Requests** (`#requests`, and `#ask/<code>` for people outside the crew): a share link lets anyone signed in add requests
and vote; they see the requests and the answers, never the board. The crew promises an answer within 7, 14 or 30 days:
Accept (becomes a backlog card labelled `request`; the requester sees it move to Shipped), Later or Decline (both need a
reason). Overdue requests show on the Deck and raise an alert. Stats: open, overdue, median days to answer, answered on
time, shipped.

**Alerts** (Crew settings): one webhook (Slack, Teams, Mattermost and Discord, or JSON for anything else), set by the owner,
and an email digest each member can switch on for themselves. Kinds: an agent hands in work, work waits in Review longer
than N hours (24 by default), a card is blocked, a column goes over its WIP limit, a sprint ends tomorrow or is overdue, a
request passes the answer promise. Each condition is announced once (dedupe key), checked when someone opens the Deck or an
agent uses the API (at most every 10 minutes per crew). Demo crews keep a history and never send.

**Import and export** (`#import`): reads a Jira CSV (several Labels and Comment columns, Jira dates, epics by Parent summary
or Epic Link, story points), a Trello board JSON, any CSV (fields guessed, all editable), or an AutoAgile export. Map
statuses to columns, preview, import in batches of 200. Dates are kept, so throughput, cycle times and level checks count
the past. Cards remember their source key, so importing twice skips duplicates; people are matched by email or name.
Export: everything as JSON (cards with comments, epics, sprints and retros, requests, settings) or the cards as a CSV with
Jira-style column names.

**For admins** (`#admin`; arkulinskis@gmail.com becomes an admin on first sign-in): feedback inbox, users, **Crews**
(every crew with owner and size; delete a real crew for abuse), demo data (remove / reload both demo crews).

## Setting it up in Anvil (once)

1. In the Anvil editor: **Create app → Clone from GitHub**, and paste `https://github.com/arkulinskis/autoagile`.
2. **Users** service: email + password and "Continue with Google", sign-up allowed (already set in `anvil.yaml`; check it). **Email** service: on
   (anvil.yaml adds it; alert digests use it).
3. Open the app in the editor. If it shows a **Schema Mismatch** alert, choose **"The schema of the source code is correct"** so Anvil creates the tables.
4. **Run** it and sign up with **arkulinskis@gmail.com** straight away (that account becomes the admin).
5. **Publish** (Publish → public URL, or your own domain).

<!-- libraries:start -->
## Libraries and outside services

What this project uses besides its own code. Generated by `APP_MAKER/tools/libraries.py`; to change it, edit `APP_MAKER/libraries/catalog.py` and re-run the script.

| Name | How it gets in | Used here for |
|---|---|---|
| [D3.js](https://d3js.org) 7.9.0 | Copied into the app | the reports: burndown, burnup, cumulative flow, throughput and cycle time |
| [YouTube embeds](https://developers.google.com/youtube/player_parameters) | Outside web service | Plays a YouTube video inside the page (the privacy-friendlier youtube-nocookie address). |
| [Google Fonts](https://fonts.google.com) | Loaded from a CDN | Chakra Petch, Orbitron, VT323 |

**Built into the browser:** localStorage, Clipboard, File downloads (Blob).

**Anvil platform:** Anvil, Anvil Data Tables, Anvil Google service, Anvil JS bridge (anvil.js), Anvil Users, Anvil HTTP, Anvil Email.

**Build and test tools (not shipped):** Node.js, PyYAML, Headless Chrome (DevTools Protocol).

<!-- libraries:end -->

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
                pages/_aa.html is the shared kit (window.AA): crews, card chips, gates widget, LCDs, windows, charts, rave,
                d3 loader, CSV in/out, the filter language, the command palette
client_code/    Main.py (the only Anvil form: bridge to the server, sign-in), legal.py
server_code/    Gates (points rules), Model (access + dicts + board columns), Teams, Cards, Sprints, Plans, Metrics, Agents
                (+ HTTP API), Deck, Reports, Requests, Alerts, Transfer (import/export), DemoData, Admin, Accounts, Feedback,
                common, legal_server
assets/         icon.svg (three rising bars: columns, levels, an equaliser) + generated PNG icons, d3.v7.9.0.min.js
tools/          sync_to_anvil.py (settings + table schema), deploy.py, check.py, preview/ (dev server, UI tests, screenshots), testing/
```
