"""
Tests for Flask REST API Endpoints
==================================
Pruebas unitarias de las rutas de la API de InstaFlow con el cliente de pruebas de Flask.
"""

import json
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import app, job_manager


class TestAPIEndpoints:
    """Pruebas de respuestas y códigos HTTP de la API."""

    @pytest.fixture
    def client(self):
        app.config["TESTING"] = True
        with app.test_client() as client:
            yield client

    def test_health_endpoint(self, client):
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "healthy"
        assert "chrome_available" in data
        assert "cookies_present" in data
        assert "active_jobs" in data

    def test_settings_endpoint(self, client):
        response = client.get("/api/settings")
        assert response.status_code == 200
        data = response.get_json()
        assert "default_username" in data
        assert "max_posts_limit" in data
        assert "headless" in data

    def test_scrape_validation_invalid_username(self, client):
        # Username vacío
        res1 = client.post("/api/scrape", json={"username": ""})
        assert res1.status_code == 400

        # Username con caracteres prohibidos
        res2 = client.post("/api/scrape", json={"username": "user with spaces"})
        assert res2.status_code == 400

    def test_scrape_valid_launch(self, client):
        # Crear job de prueba sin llamar a Instagram real
        res = client.post("/api/scrape", json={"username": "valid_user_test", "max_posts": 5})
        assert res.status_code == 202
        data = res.get_json()
        assert data["success"] is True
        assert "job_id" in data
        assert data["username"] == "valid_user_test"

        # Comprobar consulta de estado del job
        job_id = data["job_id"]
        job_res = client.get(f"/api/jobs/{job_id}")
        assert job_res.status_code == 200
        job_data = job_res.get_json()
        assert job_data["job_id"] == job_id
        assert job_data["username"] == "valid_user_test"

    def test_job_not_found(self, client):
        res = client.get("/api/jobs/non-existent-uuid-000000")
        assert res.status_code == 404

    def test_cancel_non_existent_job(self, client):
        res = client.post("/api/jobs/invalid-id/cancel")
        assert res.status_code == 400
