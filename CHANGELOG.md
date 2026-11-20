# Changelog

## Unreleased
- Voice: prayers wait for a listener, pause when the room empties, and re-key when the group epoch changes.
- Scheduler: per-schedule UTC offset for DST; playback runs as a task so one prayer cannot block other servers.
- Dashboard: signed expiring session cookie, refuses the default token, reports failed schedule rows, `/health` no longer leaks the commit.
- Queue: a malformed command no longer wedges skip/pause/disconnect.
- Config: pinned deps, dev requirements split out, `.dockerignore`, non-root image, CI actions pinned, image has a default command.

Earlier: prayer opener, 91st Psalm, pre-join/post-stay, TTS greetings, per-server voices, history, bulk enable/disable, `/start`, `/exit`, `/next`, `/help`, ticket draw.
