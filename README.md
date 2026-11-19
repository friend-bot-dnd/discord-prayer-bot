# Discord Prayer Bot

Plays scheduled prayer recordings into Discord voice channels, with a small
FastAPI dashboard for schedules and server settings.

## Run

```bash
cp .env.example .env      # set DISCORD_BOT_TOKEN and ADMIN_TOKEN
make up                   # bot + dashboard
make logs
```

The dashboard listens on `127.0.0.1:8700`; keep it behind a reverse proxy.

## Layout

- `bot/` — scheduler, voice playback, TTS, Discord commands
- `db/` — SQLite layer (WAL; shared by both containers)
- `dashboard/` — admin pages (schedules, servers, history)
- `media/prayers/` — audio (Git LFS)

## Time

Every schedule is stored as UTC plus the offset it was saved at, so a prayer
keeps the wall-clock time the admin chose across DST changes. One clock rule
lives in `bot/prayer_time.py`.

## Voice

Prayer audio travels inside Discord's E2EE (DAVE) session. A room with nobody
in it has no key group, so the bot waits for a listener before it starts and
pauses the moment the room empties. See `bot/voice_e2ee.py`.

## Daily ticket draw

Once per local day the bot posts a **Draw your ticket** button. A draw picks a
random member of the configured role (drawer excluded), replies privately, and
adds a heart; cooldown is 18h. Draw rows are logged before the reply is sent —
keep that ordering.

Needs **Server Members Intent** and **Send Messages** in the draw channel.

## Tests

```bash
pip install -r requirements-dev.txt
pytest tests/ -q
```
