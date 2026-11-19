# Discord Prayer Bot

Plays scheduled prayer recordings into Discord voice channels, with a small
FastAPI dashboard for schedules and server settings.

## Run

```bash
cp .env.example .env      # set DISCORD_BOT_TOKEN and ADMIN_TOKEN
make up                   # bot + dashboard
make logs
```

The dashboard listens on `127.0.0.1:8700`. Put it behind your reverse proxy;
it is not meant to be reachable directly.

## Layout

- `bot/` — scheduler, voice playback, TTS, Discord commands
- `db/` — SQLite layer (WAL; shared by both containers)
- `dashboard/` — admin pages (schedules, servers, history)
- `provider/` — HTTP client for the file provider
- `media/prayers/` — audio (Git LFS)

## Time

Every schedule is stored as UTC plus the offset it was saved at, so a prayer
keeps the wall-clock time the admin chose across DST changes. One clock rule
lives in `bot/prayer_time.py`; the scheduler and dashboard both use it.

## Voice

Prayer audio travels inside Discord's E2EE (DAVE) session. A room with nobody
in it has no key group, so the bot waits for a listener before it starts and
pauses the moment the room empties. See `bot/voice_e2ee.py`.

## Daily "Pray for a Friend" ticket draw

Once per local day the bot posts a message with a **Draw your ticket** button.
A draw picks a random member of the configured role (drawer excluded) and
replies privately; each draw adds a heart. Cooldown is 18h. Invariants live in
`docs/daily_draw_invariants.md` — do not simplify the log-first ordering away.

Needs the **Server Members Intent** enabled in the Discord developer portal, and
**Send Messages** in the draw channel.

## Tests

```bash
pip install -r requirements-dev.txt
pytest tests/ -q
```
