# Himyar Welcome Bot (template)

A Python (discord.py) Discord bot — welcome messages, goodbye messages,
and server activity logs — built so **every setting lives inside
Discord itself**. No website, no login, no separate dashboard to keep
in sync with the bot. An admin runs `/settings`, gets a private panel
with buttons/dropdowns, and every server that invites the bot configures
itself independently.

This is meant to be your first public Himyar bot and also a reusable
**pattern** — the `/settings` panel structure in `cogs/settings.py` is
built so you copy it into Himyar Roles / Himyar Music / Himyar Support
later instead of building a website for those too.

## Features

- **Welcome messages** — sent to a channel you pick, with a custom
  message template (`{mention}`, `{name}`, `{server}`, `{member_count}`, …).
- **Goodbye messages** — same idea, for `on_member_remove`.
- **Server logs** — message edits/deletes, joins/leaves, bans/unbans,
  nickname changes, role changes, channel create/delete — each one
  individually toggleable.
- **`/settings`** — one slash command opens an in-Discord control panel
  (ephemeral, only the admin who ran it can see or use it): buttons to
  jump between sections, a channel picker (Discord's native channel
  select menu), toggle buttons, and a modal (popup text box) for editing
  message templates.
- Per-server config stored in SQLite (`data/settings.sqlite3`) — one
  file, no external database to host.

## Project layout

```
bot.py                    entry point — loads cogs, syncs slash commands
cogs/
  settings.py              /settings command + the whole in-Discord UI
  welcome.py               on_member_join / on_member_remove handlers
  logging_events.py        message/member/channel event logging
utils/
  database.py              per-guild settings storage (SQLite)
  formatting.py            {placeholder} substitution for message templates
data/                      settings.sqlite3 lives here (gitignored)
requirements.txt
.env.example
```

## 1. Create the bot in Discord's Developer Portal

1. Go to https://discord.com/developers/applications → **New Application**.
2. Give it a name (you can rename later) and, optionally, an icon —
   this becomes the bot's public profile once people start inviting it.
3. Left sidebar → **Bot** → **Add Bot**.
4. Under **Privileged Gateway Intents**, turn on:
   - **Server Members Intent** — required for join/leave, nickname and
     role-change logging.
   - **Message Content Intent** — required so edit/delete logs can show
     the actual message text.

   These are free to enable while your bot is in fewer than 100 servers.
   Past 100 servers Discord requires **bot verification** to keep them
   (a short review form) — worth knowing now since you're planning a
   public bot, not a blocker today.
5. Click **Reset Token** → copy it. Paste it into `.env` (see below).
   Treat this token like a password — anyone with it can log in as your
   bot in every server it's in.

## 2. Configure and run locally

```bash
cd himyar-welcome-bot
python -m venv .venv && source .venv/bin/activate   # optional but recommended
pip install -r requirements.txt

cp .env.example .env
# edit .env, paste DISCORD_TOKEN=...
```

While developing, also set `DEV_GUILD_ID` in `.env` to your own test
server's ID (right-click the server icon → Copy Server ID, with
Developer Mode on in Discord settings). This makes slash commands
appear instantly in that one server instead of waiting up to an hour
for Discord's global command cache. Leave it blank once you're ready to
go public — global sync is what makes `/settings` show up in *every*
server that invites the bot.

```bash
python bot.py
```

You should see `Logged in as <BotName> ...` in the console.

## 3. Invite it to a server

Developer Portal → your application → **OAuth2** → **URL Generator**:

- **Scopes**: `bot`, `applications.commands`
- **Bot Permissions**: at minimum — `Send Messages`, `Embed Links`,
  `Read Message History`, `View Channels`, `Manage Nicknames` is *not*
  needed, but if you add moderation features later you'll want more.
  A safe starting set: `View Channels`, `Send Messages`, `Embed Links`,
  `Read Message History`, `Ban Members` (only if you later log
  ban/unban actions the bot itself performs — logging bans done by
  humans/other bots doesn't need this).

Copy the generated URL at the bottom of the page — that's the same
"click to add to your server" link you'd share publicly once this bot
is running somewhere permanent (Railway, your Hetzner box, etc.),
same as your other bots.

## 4. Using it

In any server the bot is in, someone with **Manage Server** permission
runs `/settings`. That opens the private panel:

- **👋 Welcome / 👋 Goodbye** — toggle on/off, pick a channel with
  Discord's channel picker, click "Edit message text" to open a popup
  and write a custom message using the placeholders shown.
- **🧾 Logging** — toggle on/off, pick the log channel, and use the
  dropdown to choose exactly which event types get logged.

Nothing needs re-inviting or re-authorizing when settings change —
it's all just database rows keyed by guild ID.

## Extending this template

- **Add a new welcome/goodbye placeholder**: edit
  `utils/formatting.py`'s `render_template`.
- **Add a new loggable event**: add an entry to `LOG_EVENT_CHOICES` in
  `utils/database.py`, then add the matching `@commands.Cog.listener()`
  in `cogs/logging_events.py` (copy an existing one — they all follow
  "check the gate → build an embed → `_send`").
- **Add a whole new configurable feature** (e.g. auto-role on join,
  reaction roles): add columns to `guild_settings` in
  `utils/database.py`, add a new section button to `MainMenuView` and a
  branch in `build_section_embed`/`SectionView` in `cogs/settings.py`.
  The panel/section/modal scaffolding stays the same.
- **Reusing this for Himyar Roles / Music / Support**: keep
  `utils/database.py` + the Panel/SectionView pattern in
  `cogs/settings.py`, swap in that bot's own settings columns and
  sections (e.g. Roles: which roles are self-assignable; Music:
  default volume, DJ role).

## Deploying

Same shape as your existing bots: this runs as a single long-lived
Python process, so it drops onto Railway (like `Support-bot-1`) or your
Hetzner box the same way — `pip install -r requirements.txt`, set
`DISCORD_TOKEN` as an environment variable instead of a `.env` file if
your host prefers that, `python bot.py`. Make sure whatever host you
use persists the `data/` folder (or point `DB_PATH` at a mounted
volume) so settings survive a redeploy — SQLite is a single file, so a
plain persistent disk/volume is all it needs.

One thing to plan for as this goes public and grows: discord.py
requires **sharding** past roughly 2,500 servers on one bot (Discord
enforces this) — not a concern at launch, just something to revisit if
Himyar bots take off.
