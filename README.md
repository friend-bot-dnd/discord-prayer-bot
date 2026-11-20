# Discord Prayer Bot

Plays scheduled prayer recordings into Discord voice channels, with a small
FastAPI dashboard for schedules and server settings.

## Run

```bash
cp .env.example .env      # set the two tokens
make up                   # bot + dashboard
make logs
```

Dashboard: `127.0.0.1:8700`, behind a reverse proxy.

## Layout

- `bot/` scheduler, voice playback, TTS, commands; `db/` SQLite (WAL, shared by both containers)
- `dashboard/` admin pages; `media/prayers/` audio (Git LFS)

## Time and voice

Schedules keep their wall clock across DST (UTC + saved offset, `bot/prayer_time.py`). Audio rides Discord's E2EE (DAVE) session: the bot waits for a listener, pauses when the room empties, and re-installs media keys when the group epoch changes (`bot/voice_e2ee.py`).

## Daily ticket draw

Once per local day the bot posts a **Draw your ticket** button: a random member of the configured role (drawer excluded) gets a private reply and a heart, cooldown 18h. Rows are logged before the reply — keep that order.

Needs **Server Members Intent** and **Send Messages** in the draw channel.

## Tests

```bash
pip install -r requirements-dev.txt
pytest tests/ -q
```
