# Changelog

## Unreleased
- Voice: prayers wait for a listener and pause when the room empties, so audio is never sent into a channel Discord stopped encrypting.
- Scheduler: per-schedule UTC offset for DST; playback runs as a task so one prayer cannot block other servers.
- Dashboard: signed expiring session cookie, refuses the default token, reports failed schedule rows, `/health` no longer leaks the commit.
- Queue: a malformed command no longer wedges skip/pause/disconnect.
- Config: pinned deps, dev requirements split out, `.dockerignore`, non-root image, CI actions pinned, image has a default command.

## Earlier
Prayer session opener, 91st Psalm, pre-join/post-stay, TTS greetings, per-server voices, history, bulk enable/disable, `/start`, `/exit`, `/next`, `/help`, and the daily ticket draw.
