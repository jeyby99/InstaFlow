"""
InstaFlow CSV Storage
=====================
Exportación de perfiles y publicaciones a formato CSV utilizando Pandas.
Aplica codificación UTF-8 con BOM ('utf-8-sig') para compatibilidad nativa
con Microsoft Excel en Windows, conservando emojis y caracteres especiales.
"""

from datetime import datetime
import logging
from pathlib import Path
import pandas as pd

import config
from scraper.validators import sanitize_filename

logger = logging.getLogger("instaflow.storage.csv")


class CSVStorage:
    """Gestiona la generación de archivos CSV tabulares con Pandas."""

    def __init__(self, target_dir: Path | None = None):
        self.target_dir = target_dir or config.RESULTS_DIR
        self.target_dir.mkdir(parents=True, exist_ok=True)

    def export_profile_csv(self, profile_data: dict, job_id: str | None = None) -> Path:
        """
        Exporta los datos esenciales del perfil a un archivo CSV.
        """
        username = sanitize_filename(profile_data.get("username", "unknown"))
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        suffix = f"_{job_id[:8]}" if job_id else ""
        filename = f"{username}_profile_{timestamp}{suffix}.csv"
        file_path = self.target_dir / filename

        # Aplanar datos en una fila de DataFrame
        row = {
            "Username": profile_data.get("username"),
            "Nombre Completo": profile_data.get("full_name"),
            "Seguidores": profile_data.get("followers_count"),
            "Seguidos": profile_data.get("following_count"),
            "Total Publicaciones": profile_data.get("posts_count"),
            "Es Privada": profile_data.get("is_private"),
            "Verificada": profile_data.get("is_verified"),
            "URL Perfil": profile_data.get("profile_url"),
            "Foto Perfil (Local)": profile_data.get("profile_image_path"),
            "Foto Perfil (Remota)": profile_data.get("profile_image_url"),
            "Fecha Extracción": profile_data.get("scraped_at"),
            "Estado Extracción": profile_data.get("status"),
            "Biografía": profile_data.get("biography"),
        }

        df = pd.DataFrame([row])
        # utf-8-sig permite a Excel abrir acentos y emojis sin caracteres extraños
        df.to_csv(file_path, index=False, encoding="utf-8-sig")
        logger.info("Perfil exportado a CSV en: %s", file_path)
        return file_path

    def export_posts_csv(self, posts: list[dict], username: str, job_id: str | None = None) -> Path:
        """
        Exporta el conjunto de publicaciones recopiladas a un archivo CSV.
        """
        safe_user = sanitize_filename(username)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        suffix = f"_{job_id[:8]}" if job_id else ""
        filename = f"{safe_user}_posts_{timestamp}{suffix}.csv"
        file_path = self.target_dir / filename

        rows = []
        for p in posts:
            rows.append({
                "Post ID": p.get("post_id"),
                "Shortcode": p.get("shortcode"),
                "URL Instagram": p.get("url"),
                "Tipo de Contenido": p.get("media_type"),
                "Descripción / Pie": p.get("caption"),
                "Me Gusta": p.get("like_count"),
                "Comentarios": p.get("comment_count"),
                "Miniatura (Local)": p.get("thumbnail_path"),
                "Miniatura (Remota)": p.get("thumbnail_url"),
                "Estado Descarga": p.get("download_status"),
                "Cantidad Elementos Medio": len(p.get("media_items") or []),
                "Fecha Publicación": p.get("published_at"),
            })

        if not rows:
            # Generar CSV con cabeceras aunque la lista esté vacía
            df = pd.DataFrame(columns=[
                "Post ID", "Shortcode", "URL Instagram", "Tipo de Contenido",
                "Descripción / Pie", "Me Gusta", "Comentarios",
                "Miniatura (Local)", "Miniatura (Remota)", "Estado Descarga",
                "Cantidad Elementos Medio", "Fecha Publicación"
            ])
        else:
            df = pd.DataFrame(rows)

        df.to_csv(file_path, index=False, encoding="utf-8-sig")
        logger.info("Publicaciones exportadas a CSV en: %s (%d filas)", file_path, len(rows))
        return file_path
