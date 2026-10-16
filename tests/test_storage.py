"""
Tests for storage module
========================
Pruebas de persistencia en JSON, generación de CSV con Pandas (UTF-8 BOM)
y operaciones CRUD en base de datos SQLite.
"""

import os
import pytest
import sys
import tempfile
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from storage.json_storage import JSONStorage
from storage.csv_storage import CSVStorage
from storage.database import DatabaseManager


class TestStorage:
    """Pruebas de la capa de almacenamiento."""

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            yield Path(td)

    def test_json_storage_save_and_load(self, temp_dir):
        storage = JSONStorage(target_dir=temp_dir)
        profile_data = {
            "username": "tester",
            "full_name": "Usuario Test",
            "biography": "Bio con tildes y emojis 🌟🎉",
            "followers_count": 1200,
            "following_count": 300,
            "posts_count": 50,
            "status": "complete",
        }
        posts = [
            {"post_id": "ig_1", "shortcode": "abc", "media_type": "photo"}
        ]
        summary = {"posts_collected": 1, "images_downloaded": 1}

        saved_path = storage.save_run_result("test-job-uuid-1234", profile_data, posts, summary)
        assert saved_path.is_file()

        # Cargar de nuevo
        loaded = storage.load_profile_result("tester")
        assert loaded is not None
        assert loaded["profile"]["username"] == "tester"
        assert loaded["profile"]["biography"] == "Bio con tildes y emojis 🌟🎉"
        assert len(loaded["posts"]) == 1

    def test_csv_storage_profile_and_posts(self, temp_dir):
        storage = CSVStorage(target_dir=temp_dir)
        profile_data = {
            "username": "tester",
            "full_name": "José Pérez",
            "biography": "Línea 1\nLínea 2",
            "followers_count": 5000,
            "following_count": 250,
            "posts_count": 15,
            "status": "complete",
        }
        posts = [
            {
                "post_id": "ig_post1",
                "shortcode": "p1",
                "url": "https://instagram.com/p/p1/",
                "media_type": "photo",
                "caption": "Foto increíble en Madrid 🇪🇸",
                "like_count": 150,
                "comment_count": 12,
                "thumbnail_path": "media/posts/thumb1.jpg",
                "thumbnail_url": "https://cdn.example.com/thumb1.jpg",
                "download_status": "downloaded",
            }
        ]

        # Exportar CSV de perfil
        prof_csv = storage.export_profile_csv(profile_data, job_id="job123")
        assert prof_csv.is_file()
        df_prof = pd.read_csv(prof_csv, encoding="utf-8-sig")
        assert len(df_prof) == 1
        assert df_prof["Username"].iloc[0] == "tester"
        assert df_prof["Nombre Completo"].iloc[0] == "José Pérez"

        # Exportar CSV de publicaciones
        posts_csv = storage.export_posts_csv(posts, "tester", job_id="job123")
        assert posts_csv.is_file()
        df_posts = pd.read_csv(posts_csv, encoding="utf-8-sig")
        assert len(df_posts) == 1
        assert df_posts["Shortcode"].iloc[0] == "p1"
        assert "Madrid 🇪🇸" in df_posts["Descripción / Pie"].iloc[0]

    def test_sqlite_database_operations(self, temp_dir):
        db_path = temp_dir / "test_instaflow.db"
        db = DatabaseManager(db_path=db_path)

        # 1. Guardar trabajo
        db.save_job(
            job_id="job-uuid-999",
            username="analyst",
            status="completed",
            created_at="2026-10-15T12:00:00Z",
            finished_at="2026-10-15T12:00:30Z",
            duration_sec=30.0,
            requested_posts=10,
            collected_posts=8,
            downloaded_images=8,
        )

        jobs = db.get_recent_jobs(limit=5)
        assert len(jobs) >= 1
        assert jobs[0]["job_id"] == "job-uuid-999"

        # 2. Guardar perfil
        profile = {
            "username": "analyst",
            "full_name": "Data Analyst",
            "biography": "Python & Data",
            "followers_count": 980,
            "following_count": 120,
            "posts_count": 45,
            "is_private": False,
            "is_verified": False,
            "status": "complete",
        }
        db.save_profile(profile, job_id="job-uuid-999")
        latest = db.get_latest_profile("analyst")
        assert latest is not None
        assert latest["username"] == "analyst"
        assert latest["followers_count"] == 980
        assert latest["is_private"] is False

        # 3. Guardar posts
        posts = [
            {"post_id": "ig_1", "shortcode": "code1", "url": "https://ig.com/p/code1/", "caption": "Post 1"}
        ]
        db.save_posts(posts, "analyst", "job-uuid-999")
        db_posts = db.get_profile_posts("analyst", limit=10)
        assert len(db_posts) == 1
        assert db_posts[0]["shortcode"] == "code1"

        # 4. Limpieza de datos
        db.clear_all_data()
        assert len(db.get_recent_jobs()) == 0
        assert db.get_latest_profile("analyst") is None
