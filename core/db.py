import json
import sqlite3
import datetime
from typing import Optional, Dict, Any, List
from core.config import SUPABASE_URL, SUPABASE_KEY, SQLITE_DB_PATH


class DatabaseUpdateError(RuntimeError):
    """Raised when a videos row update fails or does not persist."""

class Database:
    def __init__(self):
        self.use_supabase = bool(SUPABASE_URL and SUPABASE_KEY)
        self.supabase = None
        if self.use_supabase:
            try:
                from supabase import create_client
                self.supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
            except Exception as e:
                print(f"[DB] Could not connect to Supabase: {e}. Falling back to SQLite.")
                self.use_supabase = False

        if not self.use_supabase:
            self._init_sqlite()

    def _init_sqlite(self):
        SQLITE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(SQLITE_DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS ideas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT NOT NULL,
                niche TEXT DEFAULT 'storytime',
                status TEXT DEFAULT 'approved',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                idea_id INTEGER,
                title TEXT,
                description TEXT,
                tags TEXT,
                script_json TEXT,
                video_path TEXT,
                storage_path TEXT,
                thumbnail_path TEXT,
                status TEXT DEFAULT 'queued',
                scheduled_publish_at TIMESTAMP,
                youtube_video_id TEXT,
                error_log TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (idea_id) REFERENCES ideas (id)
            )
            """)
            conn.commit()

    def add_idea(self, topic: str, niche: str = "storytime", status: str = "approved") -> int:
        if self.use_supabase:
            res = self.supabase.table("ideas").insert({
                "topic": topic,
                "niche": niche,
                "status": status
            }).execute()
            return res.data[0]["id"]
        else:
            with sqlite3.connect(SQLITE_DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO ideas (topic, niche, status) VALUES (?, ?, ?)",
                    (topic, niche, status)
                )
                conn.commit()
                return cursor.lastrowid

    def create_video_record(self, idea_id: Optional[int], title: str, description: str, tags: List[str], script_data: Dict[str, Any]) -> int:
        tags_str = ",".join(tags) if isinstance(tags, list) else str(tags)
        script_str = json.dumps(script_data)

        if self.use_supabase:
            res = self.supabase.table("videos").insert({
                "idea_id": idea_id,
                "title": title,
                "description": description,
                "tags": tags_str,
                "script_json": script_str,
                "status": "rendering"
            }).execute()
            return res.data[0]["id"]
        else:
            with sqlite3.connect(SQLITE_DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """INSERT INTO videos 
                    (idea_id, title, description, tags, script_json, status) 
                    VALUES (?, ?, ?, ?, ?, 'rendering')""",
                    (idea_id, title, description, tags_str, script_str)
                )
                conn.commit()
                return cursor.lastrowid

    def update_video_status(
        self,
        video_id: int,
        status: str,
        video_path: Optional[str] = None,
        storage_path: Optional[str] = None,
        thumbnail_path: Optional[str] = None,
        youtube_id: Optional[str] = None,
        error_log: Optional[str] = None
    ):
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        if self.use_supabase:
            data = {"status": status, "updated_at": now}
            if video_path is not None:
                data["video_path"] = video_path
            if storage_path is not None:
                data["storage_path"] = storage_path
            if thumbnail_path is not None:
                data["thumbnail_path"] = thumbnail_path
            if youtube_id is not None:
                data["youtube_video_id"] = youtube_id
            if error_log is not None:
                data["error_log"] = error_log

            try:
                res = self.supabase.table("videos").update(data).eq("id", video_id).execute()
            except Exception as e:
                err_str = str(e)
                hint = ""
                if "PGRST204" in err_str:
                    hint = (
                        "\nA column is missing from the Supabase 'videos' table. "
                        "Run the migration section of supabase_schema.sql in the Supabase SQL Editor."
                    )
                raise DatabaseUpdateError(
                    f"[DB] Failed to update videos row #{video_id} with {sorted(data)}: {err_str}{hint}"
                ) from e

            # Supabase returns the updated rows; zero rows means the id did not
            # match or RLS blocked the write, which is otherwise a silent no-op.
            rows = res.data or []
            if len(rows) != 1:
                raise DatabaseUpdateError(
                    f"[DB] Update of videos row #{video_id} affected {len(rows)} rows (expected 1). "
                    "Check that the row exists and that SUPABASE_KEY is the service-role key."
                )
            mismatched = [k for k in data if k != "updated_at" and rows[0].get(k) != data[k]]
            if mismatched:
                raise DatabaseUpdateError(
                    f"[DB] videos row #{video_id} did not persist fields {mismatched} after update."
                )
        else:
            with sqlite3.connect(SQLITE_DB_PATH) as conn:
                cursor = conn.cursor()
                updates = ["status = ?", "updated_at = CURRENT_TIMESTAMP"]
                params = [status]
                if video_path is not None:
                    updates.append("video_path = ?")
                    params.append(video_path)
                if storage_path is not None:
                    updates.append("storage_path = ?")
                    params.append(storage_path)
                if thumbnail_path is not None:
                    updates.append("thumbnail_path = ?")
                    params.append(thumbnail_path)
                if youtube_id is not None:
                    updates.append("youtube_video_id = ?")
                    params.append(youtube_id)
                if error_log is not None:
                    updates.append("error_log = ?")
                    params.append(error_log)
                params.append(video_id)
                try:
                    cursor.execute(f"UPDATE videos SET {', '.join(updates)} WHERE id = ?", params)
                except sqlite3.Error as e:
                    raise DatabaseUpdateError(f"[DB] Failed to update videos row #{video_id}: {e}") from e
                if cursor.rowcount != 1:
                    raise DatabaseUpdateError(
                        f"[DB] Update of videos row #{video_id} affected {cursor.rowcount} rows (expected 1)."
                    )
                conn.commit()

    def get_next_job(self, status: str = "queued") -> Optional[Dict[str, Any]]:
        """Fetch next item needing processing (or approval)"""
        # Status normalization to handle both panel and pipeline terminology
        if status in ("approved", "approved_for_upload"):
            target_statuses = ["approved", "approved_for_upload"]
        elif status in ("ready_for_review", "pending_review"):
            target_statuses = ["ready_for_review", "pending_review"]
        else:
            target_statuses = [status]

        if self.use_supabase:
            res = (
                self.supabase.table("videos")
                .select("*")
                .in_("status", target_statuses)
                .order("created_at")
                .limit(1)
                .execute()
            )
            if res.data:
                return res.data[0]
            return None
        else:
            with sqlite3.connect(SQLITE_DB_PATH) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                placeholders = ",".join("?" for _ in target_statuses)
                cursor.execute(
                    f"SELECT * FROM videos WHERE status IN ({placeholders}) ORDER BY created_at ASC LIMIT 1",
                    target_statuses
                )
                row = cursor.fetchone()
                return dict(row) if row else None

    def get_pending_ideas(self) -> List[Dict[str, Any]]:
        if self.use_supabase:
            res = self.supabase.table("ideas").select("*").eq("status", "approved").order("created_at").execute()
            return res.data or []
        else:
            with sqlite3.connect(SQLITE_DB_PATH) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM ideas WHERE status = 'approved' ORDER BY created_at ASC")
                return [dict(r) for r in cursor.fetchall()]

db = Database()
