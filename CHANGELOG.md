# Changelog

## Unreleased
- Voice: prayers are audible to listeners who join or rejoin, including after the room emptied. Cause: `davey` 0.2 moved key derivation into a call discord.py 2.7.1 never makes; pinned `<0.2.0`.
- Voice: a prayer restarts once if the room cannot decrypt; the count survives the restart.
- Scheduler: saved times are wall clock in the guild's zone, so DST no longer moves a prayer; "next prayer" uses the guild's date.
- Dashboard: signed expiring cookie, refuses the default token, reports failed schedule rows; `/health` drops the commit.
- Queue: a malformed command cannot wedge later ones; Play Now reports back and does not block the queue.
- Config: pinned deps, `.dockerignore`, non-root image, pinned CI actions; ruff (errors only) in CI.
