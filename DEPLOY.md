# Putting this on GitHub + your Hetzner box

## GitHub

Its own repo, same as your other bots (`Support-bot-1`, `GreenGangBot`).
Doesn't need to be public — the *bot* being invitable by anyone has
nothing to do with whether the *code repo* is public. Start private,
make it public later if you ever want people forking it.

```bash
cd himyar-welcome-bot
git init
git add .
git commit -m "Initial commit: Himyar Welcome Bot template"
```

Before pushing, double-check secrets aren't tracked:

```bash
git status   # .env and data/ should NOT appear — .gitignore already excludes them
```

Create the repo on GitHub (web UI, or `gh repo create`), then:

```bash
git remote add origin git@github.com:<you>/himyar-welcome-bot.git
git branch -M main
git push -u origin main
```

## Hetzner

SSH into the box, then:

```bash
mkdir -p ~/bots && cd ~/bots
git clone git@github.com:<you>/himyar-welcome-bot.git
cd himyar-welcome-bot

python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

cp .env.example .env
nano .env   # paste your real DISCORD_TOKEN, leave DEV_GUILD_ID blank once you're going public
```

Don't just run `python bot.py` in your SSH session — it dies the moment
you disconnect. Run it as a systemd service instead, so it survives
reboots and auto-restarts if it ever crashes:

```bash
# copy deploy/himyar-welcome-bot.service to /etc/systemd/system/,
# editing the three CHANGE_ME paths/user first
sudo cp deploy/himyar-welcome-bot.service /etc/systemd/system/
sudo nano /etc/systemd/system/himyar-welcome-bot.service   # fix CHANGE_ME

sudo systemctl daemon-reload
sudo systemctl enable --now himyar-welcome-bot
sudo systemctl status himyar-welcome-bot   # should show "active (running)"
```

Useful commands afterward:

```bash
journalctl -u himyar-welcome-bot -f      # tail logs live
sudo systemctl restart himyar-welcome-bot
```

### Updating later

```bash
cd ~/bots/himyar-welcome-bot
git pull
.venv/bin/pip install -r requirements.txt   # only needed if requirements.txt changed
sudo systemctl restart himyar-welcome-bot
```

### If this goes on your "public bots" Hetzner box specifically

You mentioned splitting into two boxes — one for public bots, one for
client/private servers. If the public-bots box isn't provisioned yet,
that's a separate step (new Hetzner server, same Ubuntu 24.04 + SSH key
setup you already did for the first one) before any of the above.

### When you add more Himyar bots later

Same pattern per bot: its own repo, its own folder under `~/bots/`, its
own `.service` file (`himyar-roles-bot.service`, etc.), each with its
own `data/settings.sqlite3` so they don't collide.
