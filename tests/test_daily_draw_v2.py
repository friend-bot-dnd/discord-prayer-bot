

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from bot.daily_draw_v2 import (
    decide_tick_action,
    draw_day,
)

PARIS = ZoneInfo("Europe/Paris")

def _local(y, m, d, hh, mm=0, ss=0):
    return datetime(y, m, d, hh, mm, ss, tzinfo=PARIS)

def _is_unambiguous(st: datetime) -> bool:
    utc = st.astimezone(ZoneInfo("UTC"))
    back = utc.astimezone(st.tzinfo)
    return (back.year, back.month, back.day, back.hour, back.minute) == (
        st.year, st.month, st.day, st.hour, st.minute)

def test_full_draw_day_yields_exactly_five_posts_no_0800():
    actions = []
    msg_id, stored_cycle, slot, hearts = None, None, None, 0
    cursor = _local(2026, 9, 10, 7, 0)
    end = _local(2026, 9, 11, 7, 0)
    while cursor <= end:
        action, due_k, hearts_out = decide_tick_action(cursor, msg_id, stored_cycle, slot, hearts)
        if action in ("post", "repost", "new_day"):
            actions.append((cursor.hour, action, due_k))
            msg_id = f"m-{due_k}-{cursor.hour}"
            stored_cycle = draw_day(cursor)
            slot = due_k
            hearts = hearts_out
        cursor += timedelta(hours=1)
    hours = [h for h, _a, _k in actions]
    assert hours == [7, 12, 17, 22, 3, 7]
    assert 8 not in hours

