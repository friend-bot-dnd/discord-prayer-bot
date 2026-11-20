# Changelog

## Unreleased
- Voice: prayers wait for a listener, pause when the room empties, and re-key when the group epoch changes.
- Scheduler: per-schedule UTC offset for DST; playback runs as a task so one prayer cannot block other servers.
- Dashboard: signed expiring cookie, refuses the default token, reports failed schedule rows, `/health` no longer leaks the commit.
- Queue: a malformed command no longer wedges skip/pause/disconnect.
- Config: pinned deps, dev requirements split out, `.dockerignore`, non-root image, pinned CI actions, default image command.
