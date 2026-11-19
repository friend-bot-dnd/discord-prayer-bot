from datetime import datetime, timedelta

from db.database import Database
from db.prayer_listen import (
    checkpoint_open,
    close_session,
    open_session,
    top_listeners,
)

def test_session_credited_and_checkpoint_no_double(tmp_path):
    with Database(str(tmp_path / "t.db")) as db:
        t0 = datetime(2026, 9, 7, 12, 0, 0)
        open_session(db, "g", "u", "Ada", "Addie", at=t0)
        checkpoint_open(db, at=t0 + timedelta(seconds=40))
        close_session(db, "g", "u", at=t0 + timedelta(seconds=70))
        rows = top_listeners(db, "g", "alltime")
        assert len(rows) == 1
        assert rows[0]["seconds"] == 70

