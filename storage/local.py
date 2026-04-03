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


CREATE_EVIDENCE_TABLE = """
CREATE TABLE IF NOT EXISTS evidence (
    id TEXT PRIMARY KEY,
    capture_id TEXT,
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

CREATE_ZONES_TABLE = """
CREATE TABLE IF NOT EXISTS zones (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    camera_url TEXT NOT NULL,
    polygon TEXT NOT NULL DEFAULT '[]',
    task_types TEXT NOT NULL DEFAULT '["documentation"]',
    retention_days INTEGER NOT NULL DEFAULT 90,
    cooldown_seconds REAL NOT NULL DEFAULT 10.0,
    motion_threshold REAL NOT NULL DEFAULT 0.02,
    sequence_interval REAL NOT NULL DEFAULT 0.0,
    trigger_mode TEXT NOT NULL DEFAULT 'motion',
    active INTEGER NOT NULL DEFAULT 0
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
            await db.execute(CREATE_EVIDENCE_TABLE)
            await db.execute(CREATE_ZONES_TABLE)
            # Migrate: rename task_type → task_types if old schema exists
            async with db.execute("PRAGMA table_info(zones)") as cur:
                cols = {row[1] async for row in cur}
            if "task_type" in cols and "task_types" not in cols:
                await db.execute("ALTER TABLE zones ADD COLUMN task_types TEXT NOT NULL DEFAULT '[\"documentation\"]'")
                await db.execute("UPDATE zones SET task_types = json_array(task_type)")
                await db.commit()
            if "motion_threshold" not in cols:
                await db.execute("ALTER TABLE zones ADD COLUMN motion_threshold REAL NOT NULL DEFAULT 0.02")
            if "sequence_interval" not in cols:
                await db.execute("ALTER TABLE zones ADD COLUMN sequence_interval REAL NOT NULL DEFAULT 0.0")
            if "trigger_mode" not in cols:
                await db.execute("ALTER TABLE zones ADD COLUMN trigger_mode TEXT NOT NULL DEFAULT 'motion'")
            await db.commit()
            # Migrate: add capture_id to evidence table
            async with db.execute("PRAGMA table_info(evidence)") as cur:
                ecols = {row[1] async for row in cur}
            if "capture_id" not in ecols:
                await db.execute("ALTER TABLE evidence ADD COLUMN capture_id TEXT")
                await db.execute("UPDATE evidence SET capture_id = id WHERE capture_id IS NULL")
                await db.commit()

    # ── Zone CRUD ────────────────────────────────────────────────────────────

    async def create_zone(self, zone: Zone) -> dict:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT INTO zones (id, name, camera_url, polygon, task_types,
                   trigger_mode, retention_days, cooldown_seconds, motion_threshold, sequence_interval, active)
                   VALUES (?,?,?,?,?,?,?,?,?,?,0)""",
                (
                    zone.id, zone.name, zone.camera_url,
                    json.dumps(zone.polygon), json.dumps(zone.task_types),
                    zone.trigger_mode, zone.retention_days, zone.cooldown_seconds,
                    zone.motion_threshold, zone.sequence_interval,
                ),
            )
            await db.commit()
        return await self.get_zone(zone.id)  # type: ignore[return-value]

    async def get_zone(self, zone_id: str) -> dict | None:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM zones WHERE id=?", (zone_id,)) as cur:
                row = await cur.fetchone()
                return _zone_row_to_dict(row) if row else None

    async def stats(self) -> dict:
        async with aiosqlite.connect(self.db_path) as db:
            async def scalar(sql: str) -> int:
                async with db.execute(sql) as cur:
                    row = await cur.fetchone()
                    return row[0] if row else 0
            return {
                "total_zones":    await scalar("SELECT COUNT(*) FROM zones"),
                "active_zones":   await scalar("SELECT COUNT(*) FROM zones WHERE active=1"),
                "total_records":  await scalar("SELECT COUNT(*) FROM evidence"),
                "flagged_records": await scalar("SELECT COUNT(*) FROM evidence WHERE flagged=1"),
            }

    async def list_zones(self) -> list[dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM zones ORDER BY name") as cur:
                rows = await cur.fetchall()
                return [_zone_row_to_dict(r) for r in rows]

    async def update_zone(self, zone_id: str, **fields) -> bool:
        allowed = {"name", "camera_url", "task_types", "trigger_mode", "retention_days", "cooldown_seconds", "motion_threshold", "sequence_interval"}
        sets, params = [], []
        for k, v in fields.items():
            if k not in allowed:
                continue
            sets.append(f"{k}=?")
            params.append(json.dumps(v) if k == "task_types" else v)
        if not sets:
            return False
        params.append(zone_id)
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(f"UPDATE zones SET {', '.join(sets)} WHERE id=?", params)
            await db.commit()
            return cur.rowcount > 0

    async def delete_zone(self, zone_id: str) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute("DELETE FROM zones WHERE id=?", (zone_id,))
            await db.commit()
            return cur.rowcount > 0

    async def set_zone_active(self, zone_id: str, active: bool) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                "UPDATE zones SET active=? WHERE id=?", (int(active), zone_id)
            )
            await db.commit()
            return cur.rowcount > 0

    async def save(self, frame: np.ndarray, zone: Zone, task_type: str, result: dict, capture_id: str | None = None) -> dict:
        record_id = str(uuid.uuid4())
        capture_id = capture_id or record_id
        ts = datetime.utcnow().isoformat()
        image_path = self.images_dir / f"{record_id}.jpg"
        cv2.imwrite(str(image_path), frame)

        # Tasks may set explicit flagged; fall back to type-specific heuristics
        if "flagged" in result:
            flagged = bool(result["flagged"])
        else:
            score = result.get("condition_score")
            flagged = bool(
                (score is not None and score < 5)
                or result.get("anomaly_detected")
            )

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT INTO evidence
                   (id, capture_id, zone_id, zone_name, task_type, timestamp, image_path,
                    result, flagged, retention_days)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    record_id, capture_id, zone.id, zone.name, task_type, ts,
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

    async def count(
        self,
        zone_id: str | None = None,
        flagged: bool | None = None,
    ) -> int:
        conditions = []
        params: list = []
        if zone_id:
            conditions.append("zone_id=?")
            params.append(zone_id)
        if flagged is not None:
            conditions.append("flagged=?")
            params.append(int(flagged))
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(f"SELECT COUNT(*) FROM evidence {where}", params) as cur:
                row = await cur.fetchone()
                return row[0] if row else 0

    async def list(
        self,
        zone_id: str | None = None,
        flagged: bool | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        conditions = []
        params: list = []
        if zone_id:
            conditions.append("zone_id=?")
            params.append(zone_id)
        if flagged is not None:
            conditions.append("flagged=?")
            params.append(int(flagged))
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        params += [limit, offset]
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                f"SELECT * FROM evidence {where} ORDER BY timestamp DESC LIMIT ? OFFSET ?",
                params,
            )
            rows = await cur.fetchall()
            return [_row_to_dict(r) for r in rows]

    async def list_captures(
        self,
        zone_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        where = "WHERE zone_id=?" if zone_id else ""
        params: list = ([zone_id] if zone_id else []) + [limit, offset]
        sql = f"""
            SELECT
                capture_id,
                MIN(timestamp) as timestamp,
                zone_id, zone_name,
                GROUP_CONCAT(task_type) as task_types_str,
                MAX(flagged) as flagged,
                MIN(image_path) as image_path
            FROM evidence
            {where}
            GROUP BY capture_id
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(sql, params)
            rows = await cur.fetchall()
            result = []
            for row in rows:
                d = dict(row)
                d["flagged"] = bool(d["flagged"])
                # De-duplicate task types while preserving order
                seen: set[str] = set()
                types: list[str] = []
                for t in (d.pop("task_types_str") or "").split(","):
                    t = t.strip()
                    if t and t not in seen:
                        seen.add(t)
                        types.append(t)
                d["task_types"] = types
                result.append(d)
            return result

    async def get_capture(self, capture_id: str) -> list[dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM evidence WHERE capture_id=? ORDER BY task_type",
                (capture_id,),
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

    async def purge_old_pdfs(self, retention_hours: int) -> int:
        """Delete PDF files older than retention_hours, keeping the evidence record."""
        cutoff = datetime.utcnow() - timedelta(hours=retention_hours)
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT id, pdf_path FROM evidence WHERE pdf_path IS NOT NULL AND timestamp < ?",
                (cutoff.isoformat(),),
            )
            rows = await cur.fetchall()
            for row in rows:
                Path(row["pdf_path"]).unlink(missing_ok=True)
                await db.execute("UPDATE evidence SET pdf_path=NULL WHERE id=?", (row["id"],))
            await db.commit()
            return len(rows)

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


def _zone_row_to_dict(row: aiosqlite.Row) -> dict:
    d = dict(row)
    d["polygon"] = json.loads(d["polygon"])
    d["task_types"] = json.loads(d.get("task_types") or '["documentation"]')
    d["active"] = bool(d["active"])
    return d
