"""Small local persistence layer for prototype analytics and operational history."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from contextlib import contextmanager
from pathlib import Path
from typing import Any


class AnalyticsStore:
    def __init__(self, database_path: Path):
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
        except Exception:
            connection.rollback()
            raise
        else:
            connection.commit()
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS analytics_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    camera_id TEXT NOT NULL,
                    generated_at TEXT NOT NULL,
                    traffic_status TEXT NOT NULL,
                    average_occupancy REAL NOT NULL,
                    peak_occupancy REAL NOT NULL,
                    peak_vehicles_in_frame INTEGER NOT NULL,
                    vehicle_counts_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_analytics_camera_time
                    ON analytics_snapshots(camera_id, generated_at DESC);
                """
            )

    def record(self, camera_id: str, analytics: dict[str, Any], traffic_status: str) -> None:
        generated_at = analytics.get("generated_at") or datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO analytics_snapshots
                    (camera_id, generated_at, traffic_status, average_occupancy,
                     peak_occupancy, peak_vehicles_in_frame, vehicle_counts_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    camera_id,
                    generated_at,
                    traffic_status,
                    float(analytics.get("average_occupancy", 0) or 0),
                    float(analytics.get("peak_occupancy", 0) or 0),
                    int(analytics.get("peak_vehicles_in_frame", 0) or 0),
                    json.dumps(analytics.get("vehicle_counts", {})),
                ),
            )

    def history(self, camera_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 500))
        query = "SELECT * FROM analytics_snapshots"
        parameters: tuple[Any, ...] = ()
        if camera_id:
            query += " WHERE camera_id = ?"
            parameters = (camera_id,)
        query += " ORDER BY generated_at DESC LIMIT ?"
        parameters += (limit,)
        with self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [
            {
                "id": row["id"],
                "camera_id": row["camera_id"],
                "generated_at": row["generated_at"],
                "traffic_status": row["traffic_status"],
                "average_occupancy": row["average_occupancy"],
                "peak_occupancy": row["peak_occupancy"],
                "peak_vehicles_in_frame": row["peak_vehicles_in_frame"],
                "vehicle_counts": json.loads(row["vehicle_counts_json"]),
            }
            for row in rows
        ]
