"""LocalStore — SQLite metadata + filesystem images."""
from __future__ import annotations
import uuid
import json
from datetime import datetime, timedelta
from pathlib import Path
import aiosqlite
import cv2
import numpy as np
from core.zone import Zone
from storage.store import BaseStore
import config


CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS evidence (
    id TEXT PRIMARY KEY,
    zone_id TEXT NOT NULL,
    zone_name TEXT NOT NULL,
    task_type TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    image_path TEXT NOT NULL,
    pdf_path TEXT,
    result TEXT NOT NULL,
    flagged INTEGER NOT NULL DEFAULT 0,
    retention_days INTEGER NOT NULL
)
"""


class LocalStore(BaseStore):
    def __init__(self, db_path: Path = config.DB_PATH) -> None:
        self.db_path = db_path
        self.images_dir = config.IMAGES_DIR

    async def init(self) -> None:
        config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        self.images_dir.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(CREATE_TABLE)
            await db.commit()

    async def save(self, frame: np.ndarray, zone: Zone, task_type: str, result: dict) -> dict:
        record_id = str(uuid.uuid4())
        ts = datetime.utcnow().isoformat()
        image_path = self.images_dir / f"{record_id}.jpg"
        cv2.imwrite(str(image_path), frame)

        # documentation task uses condition_score; inspection uses anomaly_detected
        score = result.get("condition_score")
        flagged = bool(
            (score is not None and score < 5)
            or result.get("anomaly_detected")
        )

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT INTO evidence
                   (id, zone_id, zone_name, task_type, timestamp, image_path,
                    result, flagged, retention_days)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    record_id, zone.id, zone.name, task_type, ts,
                    str(image_path), json.dumps(result), int(flagged),
                    zone.retention_days,
                ),
            )
            await db.commit()

        return await self.get(record_id)  # type: ignore[return-value]

    async def get(self, record_id: str) -> dict | None:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM evidence WHERE id=?", (record_id,)
            ) as cur:
                row = await cur.fetchone()
                return _row_to_dict(row) if row else None

    async def list(self, zone_id: str | None = None, limit: int = 50, offset: int = 0) -> list[dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            if zone_id:
                cur = await db.execute(
                    "SELECT * FROM evidence WHERE zone_id=? ORDER BY timestamp DESC LIMIT ? OFFSET ?",
                    (zone_id, limit, offset),
                )
            else:
                cur = await db.execute(
                    "SELECT * FROM evidence ORDER BY timestamp DESC LIMIT ? OFFSET ?",
                    (limit, offset),
                )
            rows = await cur.fetchall()
            return [_row_to_dict(r) for r in rows]

    async def attach_pdf(self, record_id: str, pdf_path: Path) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE evidence SET pdf_path=? WHERE id=?",
                (str(pdf_path), record_id),
            )
            await db.commit()

    async def purge_expired(self) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            # Find expired records
            cur = await db.execute("SELECT id, image_path, pdf_path, timestamp, retention_days FROM evidence")
            rows = await cur.fetchall()
            now = datetime.utcnow()
            to_delete = []
            for row in rows:
                ts = datetime.fromisoformat(row["timestamp"])
                if now - ts > timedelta(days=row["retention_days"]):
                    to_delete.append(row)

            for row in to_delete:
                Path(row["image_path"]).unlink(missing_ok=True)
                if row["pdf_path"]:
                    Path(row["pdf_path"]).unlink(missing_ok=True)
                await db.execute("DELETE FROM evidence WHERE id=?", (row["id"],))
            await db.commit()
            return len(to_delete)


def _row_to_dict(row: aiosqlite.Row) -> dict:
    d = dict(row)
    d["result"] = json.loads(d["result"])
    d["flagged"] = bool(d["flagged"])
    return d
