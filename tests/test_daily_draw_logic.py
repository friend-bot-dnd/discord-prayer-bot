
from __future__ import annotations

from datetime import datetime, timezone

from bot.daily_draw_logic import (
    build_message_text,
)

def test_build_message_text_five_hearts_exact_shape():
    assert build_message_text("Text", 5) == "Text " + "❤️" * 5

NOW = datetime(2026, 9, 8, 12, 0, 0, tzinfo=timezone.utc)

DRAWN_AT = datetime(2026, 9, 8, 11, 30, 5, tzinfo=timezone.utc)

PARIS = "Europe/Paris"

