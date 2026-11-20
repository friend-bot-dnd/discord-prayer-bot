# Changelog

## Unreleased
- Voice: scheduled prayers are audible to listeners who join or rejoin, including after the room emptied. Cause: `davey` 0.2 moved key derivation into a call discord.py 2.7.1 never makes; pinned `<0.2.0`.
- Voice: a prayer restarts once if the room cannot decrypt; the repair count survives the restart.
- Scheduler: the saved time is the guild's wall clock resolved in its zone, so DST no longer moves a prayer; "next prayer" uses the guild's date.
- Dashboard: signed expiring cookie, refuses the default token, reports failed schedule rows, `/health` no longer leaks the commit.
- Queue: a malformed command no longer wedges later commands; Play Now no longer blocks the queue while it waits for a listener.
- Config: pinned deps, `.dockerignore`, non-root image, pinned CI actions, default image command.
