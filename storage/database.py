"""
InstaFlow SQLite Database Manager
=================================
Almacenamiento persistente e histórico de ejecuciones, perfiles y publicaciones
en base de datos SQLite relacional.
"""

from contextlib import contextmanager
from datetime import datetime
import json
import logging
from pathlib import Path
import sqlite3

import config

logger = logging.getLogger("instaflow.storage.db")


class DatabaseManager:
    """Gestiona las tablas y transacciones de la base de datos SQLite."""

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or config.SQLITE_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    @contextmanager
    def _get_connection(self):
        """Crea una conexión con row_factory activo y garantiza su cierre al finalizar."""
        conn = sqlite3.connect(str(self.db_path), timeout=15.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def init_db(self) -> None:
        """Inicializa el esquema de tablas si no existen."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Tabla de ejecuciones/trabajos
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    username TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    finished_at TEXT,
                    duration_sec REAL,
                    requested_posts INTEGER,
                    collected_posts INTEGER DEFAULT 0,
                    downloaded_images INTEGER DEFAULT 0,
                    error_message TEXT,
                    metadata_json TEXT
                )
            """)

            # Tabla histórica de perfiles
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS profiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT,
                    username TEXT NOT NULL,
                    full_name TEXT,
                    biography TEXT,
                    followers_count INTEGER,
                    following_count INTEGER,
                    posts_count INTEGER,
                    profile_url TEXT,
                    is_private INTEGER,
                    is_verified INTEGER,
                    profile_image_url TEXT,
                    profile_image_path TEXT,
                    scraped_at TEXT NOT NULL,
                    status TEXT,
                    FOREIGN KEY (job_id) REFERENCES jobs (job_id)
                )
            """)

            # Tabla de publicaciones
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS posts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    username TEXT NOT NULL,
                    post_id TEXT NOT NULL,
                    shortcode TEXT NOT NULL,
                    url TEXT NOT NULL,
                    caption TEXT,
                    published_at TEXT,
                    media_type TEXT,
                    like_count INTEGER,
                    comment_count INTEGER,
                    thumbnail_url TEXT,
                    thumbnail_path TEXT,
                    download_status TEXT,
                    media_items_json TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (job_id) REFERENCES jobs (job_id)
                )
            """)

            # Índices para consultas eficientes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_username ON jobs(username);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_profiles_username ON profiles(username);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_posts_username ON posts(username);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_posts_job_id ON posts(job_id);")

            conn.commit()
            logger.debug("Esquema de base de datos SQLite verificado.")

    def save_job(
        self,
        job_id: str,
        username: str,
        status: str,
        created_at: str,
        finished_at: str | None = None,
        duration_sec: float | None = None,
        requested_posts: int = 0,
        collected_posts: int = 0,
        downloaded_images: int = 0,
        error_message: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        """Inserta o actualiza un registro de trabajo en la tabla jobs."""
        meta_str = json.dumps(metadata or {}, ensure_ascii=False)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO jobs (
                    job_id, username, status, created_at, finished_at,
                    duration_sec, requested_posts, collected_posts,
                    downloaded_images, error_message, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    status=excluded.status,
                    finished_at=excluded.finished_at,
                    duration_sec=excluded.duration_sec,
                    collected_posts=excluded.collected_posts,
                    downloaded_images=excluded.downloaded_images,
                    error_message=excluded.error_message,
                    metadata_json=excluded.metadata_json
            """, (
                job_id, username, status, created_at, finished_at,
                duration_sec, requested_posts, collected_posts,
                downloaded_images, error_message, meta_str
            ))
            conn.commit()

    def save_profile(self, profile_data: dict, job_id: str | None = None) -> int:
        """Inserta una captura de perfil en la tabla profiles."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO profiles (
                    job_id, username, full_name, biography, followers_count,
                    following_count, posts_count, profile_url, is_private,
                    is_verified, profile_image_url, profile_image_path,
                    scraped_at, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job_id,
                profile_data.get("username"),
                profile_data.get("full_name"),
                profile_data.get("biography"),
                profile_data.get("followers_count"),
                profile_data.get("following_count"),
                profile_data.get("posts_count"),
                profile_data.get("profile_url"),
                1 if profile_data.get("is_private") is True else (0 if profile_data.get("is_private") is False else None),
                1 if profile_data.get("is_verified") is True else (0 if profile_data.get("is_verified") is False else None),
                profile_data.get("profile_image_url"),
                profile_data.get("profile_image_path"),
                profile_data.get("scraped_at") or datetime.now().isoformat(),
                profile_data.get("status"),
            ))
            conn.commit()
            return cursor.lastrowid

    def save_posts(self, posts: list[dict], username: str, job_id: str) -> int:
        """Inserta las publicaciones asociadas a un trabajo."""
        now_str = datetime.now().isoformat()
        inserted = 0
        with self._get_connection() as conn:
            cursor = conn.cursor()
            for p in posts:
                media_items_json = json.dumps(p.get("media_items") or [], ensure_ascii=False)
                cursor.execute("""
                    INSERT INTO posts (
                        job_id, username, post_id, shortcode, url, caption,
                        published_at, media_type, like_count, comment_count,
                        thumbnail_url, thumbnail_path, download_status,
                        media_items_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    job_id,
                    username,
                    p.get("post_id", f"ig_{p.get('shortcode')}"),
                    p.get("shortcode", ""),
                    p.get("url", ""),
                    p.get("caption"),
                    p.get("published_at"),
                    p.get("media_type", "photo"),
                    p.get("like_count"),
                    p.get("comment_count"),
                    p.get("thumbnail_url"),
                    p.get("thumbnail_path"),
                    p.get("download_status", "pending"),
                    media_items_json,
                    now_str,
                ))
                inserted += 1
            conn.commit()
        return inserted

    def get_latest_profile(self, username: str) -> dict | None:
        """Obtiene la última información de perfil registrada para el usuario."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM profiles WHERE username = ? ORDER BY id DESC LIMIT 1
            """, (username.lower(),))
            row = cursor.fetchone()
            if row:
                d = dict(row)
                d["is_private"] = bool(d["is_private"]) if d["is_private"] is not None else None
                d["is_verified"] = bool(d["is_verified"]) if d["is_verified"] is not None else None
                return d
            return None

    def get_profile_posts(self, username: str, limit: int = 50) -> list[dict]:
        """Obtiene las publicaciones más recientes del usuario desde la base de datos."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM posts WHERE username = ? ORDER BY id DESC LIMIT ?
            """, (username.lower(), limit))
            rows = cursor.fetchall()
            posts = []
            for r in rows:
                p = dict(r)
                if p.get("media_items_json"):
                    try:
                        p["media_items"] = json.loads(p["media_items_json"])
                    except Exception:
                        p["media_items"] = []
                posts.append(p)
            return posts

    def get_recent_jobs(self, limit: int = 15) -> list[dict]:
        """Obtiene el historial de ejecuciones recientes."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?
            """, (limit,))
            return [dict(r) for r in cursor.fetchall()]

    def clear_all_data(self) -> None:
        """Limpia los datos históricos en la base de datos."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM posts;")
            cursor.execute("DELETE FROM profiles;")
            cursor.execute("DELETE FROM jobs;")
            conn.commit()
            logger.info("Base de datos SQLite limpiada completamente.")
