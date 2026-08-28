from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterator


@dataclass(frozen=True)
class DatabaseActor:
    user_id: str
    role: str
    household_ids: tuple[str, ...]
    entity_ids: tuple[str, ...]
    entity_scope: tuple[str, ...]
    session_id: str
    auth_level: int
    step_up_until: object | None


class PortalDatabase:
    """PostgreSQL transaction boundary that installs only server-derived RLS scope."""

    def __init__(self, dsn: str, *, min_size: int = 2, max_size: int = 20) -> None:
        from psycopg.rows import dict_row
        from psycopg_pool import ConnectionPool

        self.pool = ConnectionPool(
            dsn, min_size=min_size, max_size=max_size, open=False, kwargs={"row_factory": dict_row}
        )

    def open(self) -> None:
        self.pool.open(wait=True)

    def close(self) -> None:
        self.pool.close()

    @contextmanager
    def actor_transaction(self, session_digest: str) -> Iterator[tuple[Any, DatabaseActor]]:
        with self.pool.connection() as conn, conn.transaction():
            row = conn.execute(
                "SELECT * FROM portal.authenticate_session(%s)",
                (session_digest,),
            ).fetchone()
            if row is None:
                raise PermissionError("invalid session")
            actor = DatabaseActor(
                user_id=str(row["user_id"]),
                role=str(row["actor_role"]),
                household_ids=tuple(str(item) for item in row["household_ids"]),
                entity_ids=tuple(str(item) for item in row["entity_ids"]),
                entity_scope=tuple(str(item) for item in row["entity_scope"]),
                session_id=str(row["session_id"]),
                auth_level=int(row["auth_level"]),
                step_up_until=row["step_up_until"],
            )
            settings = {
                "app.user_id": actor.user_id,
                "app.actor_role": actor.role,
                "app.household_ids": ",".join(actor.household_ids),
                "app.entity_ids": ",".join(actor.entity_ids),
                "app.entity_scope": ",".join(actor.entity_scope),
                "app.session_id": actor.session_id,
                "app.auth_level": str(actor.auth_level),
            }
            for key, value in settings.items():
                conn.execute("SELECT set_config(%s, %s, true)", (key, value))
            yield conn, actor

    @contextmanager
    def worker_transaction(self, worker_id: str) -> Iterator[Any]:
        with self.pool.connection() as conn, conn.transaction():
            conn.execute("SELECT set_config('app.worker_id', %s, true)", (worker_id,))
            conn.execute("SELECT set_config('app.actor_role', 'worker', true)")
            yield conn

    def health(self) -> bool:
        with self.pool.connection() as conn:
            row = conn.execute("SELECT 1 AS ok").fetchone()
            return bool(row and row["ok"] == 1)
