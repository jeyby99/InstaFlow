"""
InstaFlow JSON Storage
======================
Persistencia y lectura de resultados de scraping en formato JSON UTF-8.
Conserva caracteres especiales, tildes y emojis sin secuencias de escape.
"""

from datetime import datetime
import json
import logging
from pathlib import Path

import config
from scraper.validators import sanitize_filename

logger = logging.getLogger("instaflow.storage.json")


class JSONStorage:
    """Administra el guardado y lectura de resultados en archivos JSON."""

    def __init__(self, target_dir: Path | None = None):
        self.target_dir = target_dir or config.RESULTS_DIR
        self.target_dir.mkdir(parents=True, exist_ok=True)

    def save_run_result(self, job_id: str, profile_data: dict, posts: list[dict], summary: dict) -> Path:
        """
        Guarda la ejecución completa en un archivo JSON único y actualiza el archivo _latest.
        """
        username = sanitize_filename(profile_data.get("username", "unknown"))
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{username}_{timestamp}_{job_id[:8]}.json"
        file_path = self.target_dir / filename

        full_payload = {
            "job_id": job_id,
            "saved_at": datetime.now().isoformat(),
            "profile": profile_data,
            "posts": posts,
            "summary": summary,
        }

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(full_payload, f, ensure_ascii=False, indent=2)

            # Actualizar también archivo de conveniencia <username>_latest.json
            latest_path = self.target_dir / f"{username}_latest.json"
            with open(latest_path, "w", encoding="utf-8") as f:
                json.dump(full_payload, f, ensure_ascii=False, indent=2)

            logger.info("Resultados JSON guardados en: %s", file_path)
            return file_path
        except Exception as e:
            logger.error("Error al guardar archivo JSON de resultados: %s", e)
            raise

    def load_profile_result(self, username: str) -> dict | None:
        """Carga el resultado más reciente guardado para un nombre de usuario dado."""
        safe_user = sanitize_filename(username)
        latest_path = self.target_dir / f"{safe_user}_latest.json"
        if latest_path.is_file():
            try:
                with open(latest_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning("No se pudo leer %s: %s", latest_path, e)

        # Buscar el archivo más reciente que coincida con el patrón
        matching_files = sorted(
            self.target_dir.glob(f"{safe_user}_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for p in matching_files:
            if not p.name.endswith("_latest.json"):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        return json.load(f)
                except Exception:
                    continue

        return None

    def load_job_file(self, job_id: str) -> dict | None:
        """Busca y carga un archivo de resultado asociado a un job_id específico."""
        for p in self.target_dir.glob("*.json"):
            if job_id[:8] in p.name:
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if data.get("job_id") == job_id:
                            return data
                except Exception:
                    continue
        return None
