from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


@dataclass
class FrozenClock:
    value: datetime

    def now(self) -> datetime:
        if self.value.tzinfo is None:
            return self.value.replace(tzinfo=UTC)
        return self.value.astimezone(UTC)

    def advance(self, **kwargs: int) -> None:
        self.value = self.now() + timedelta(**kwargs)
