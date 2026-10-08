"""In-memory status of the news ingestion loop (reported in API responses; resets on restart)."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional


@dataclass
class NewsSyncState:
    enabled: bool = True
    last_attempt_at: Optional[datetime] = None
    last_success_at: Optional[datetime] = None
    #: Machine code of the last failure (e.g. PROVIDER_RATE_LIMITED); None after a success.
    last_error_code: Optional[str] = None

    def record(self, *, success: bool, error_code: Optional[str] = None) -> None:
        now = datetime.now(timezone.utc)
        self.last_attempt_at = now
        if success:
            self.last_success_at = now
        # A partially successful sync (e.g. page 1 ok, page 2 rate-limited) keeps its error code visible.
        self.last_error_code = error_code or (None if success else "PROVIDER_ERROR")


_state = NewsSyncState()


def get_news_sync_state() -> NewsSyncState:
    return _state
