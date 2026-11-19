# Changelog

## Unreleased

### Fixed
- Voice: prayers wait for a listener and pause when the room empties, so audio
  is never sent into a channel Discord has already stopped encrypting.
- Scheduler: follow daylight saving via a per-schedule offset; playback runs as
  a task so one long prayer cannot block other servers.
- Dashboard: signed expiring session cookie instead of storing the admin token;
  the app refuses to start on the default token.
- Dashboard: a bad schedule row is reported instead of a false "Saved".
- Queue: a malformed command no longer wedges skip/pause/disconnect.

### Changed
- Softer idle leave (30s) after the channel empties.
- Status refresh and daily-draw ticks run per server in parallel.
- Config: pinned dependencies, split dev requirements, `.dockerignore`, the
  image runs as a non-root user, CI actions pinned by commit.

## Earlier
- Prayer session opener, 91st Psalm, pre-join/post-stay windows, TTS greetings
  and blessings, per-server voices, logging channel, prayer history, bulk
  enable/disable, `/start`, `/exit`, `/next`, `/help`.
- Daily "Pray for a Friend" ticket draw with a persistent button, 18h cooldown,
  append-only draw log.
