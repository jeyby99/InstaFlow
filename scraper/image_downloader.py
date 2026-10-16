"""
InstaFlow Image Downloader & Validator
======================================
Descarga segura de imágenes autorizadas, validación de integridad mediante Pillow,
generación de nombres de archivo no colisionables y protección contra SSRF.
"""

import hashlib
import io
import logging
from pathlib import Path
import requests
from PIL import Image

import config
from .validators import is_safe_image_url, sanitize_filename

logger = logging.getLogger("instaflow.images")


class ImageDownloader:
    """Descarga y valida imágenes de perfiles y publicaciones."""

    def __init__(self, session: requests.Session | None = None):
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": config.IMAGE_USER_AGENT})
        # Caché de URLs descargadas para evitar descargas duplicadas en la misma sesión
        self._download_cache: dict[str, str] = {}

    def _generate_filename(self, url: str, prefix: str = "img") -> str:
        """Genera un nombre de archivo único y seguro a partir del hash de la URL."""
        url_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
        safe_prefix = sanitize_filename(prefix, max_length=24)
        return f"{safe_prefix}_{url_hash}.jpg"

    def download_image(
        self,
        url: str | None,
        target_dir: Path,
        filename_prefix: str = "img",
    ) -> dict:
        """
        Descarga una imagen desde una URL pública autorizada y la valida con Pillow.

        Retorna:
            dict con:
                status: 'downloaded' | 'skipped' | 'failed' | 'not_available'
                local_path: str relativo para el frontend o None
                absolute_path: Path absoluto o None
                error: str descriptivo o None
        """
        if not url or not is_safe_image_url(url):
            return {
                "status": "not_available",
                "local_path": None,
                "absolute_path": None,
                "error": "URL de imagen ausente o no válida",
            }

        # Comprobar si ya fue descargada en esta sesión
        if url in self._download_cache:
            cached_rel = self._download_cache[url]
            return {
                "status": "downloaded",
                "local_path": cached_rel,
                "absolute_path": config.BASE_DIR / cached_rel,
                "error": None,
            }

        target_dir.mkdir(parents=True, exist_ok=True)
        filename = self._generate_filename(url, prefix=filename_prefix)
        file_path = target_dir / filename

        # Si ya existe en disco con contenido válido, validar y reutilizar
        if file_path.is_file() and file_path.stat().st_size > 100:
            try:
                with Image.open(file_path) as img:
                    img.verify()
                rel_path = file_path.relative_to(config.BASE_DIR).as_posix()
                self._download_cache[url] = rel_path
                return {
                    "status": "downloaded",
                    "local_path": rel_path,
                    "absolute_path": file_path,
                    "error": None,
                }
            except Exception:
                # Si está dañado en disco, proceder a volver a descargar
                pass

        try:
            response = self.session.get(
                url,
                timeout=config.IMAGE_DOWNLOAD_TIMEOUT,
                stream=True,
            )

            if response.status_code != 200:
                logger.warning("Fallo HTTP %s al descargar imagen: %s", response.status_code, url[:60])
                return {
                    "status": "failed",
                    "local_path": None,
                    "absolute_path": None,
                    "error": f"Error HTTP {response.status_code}",
                }

            # Validar tamaño máximo
            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) > config.MAX_IMAGE_SIZE_BYTES:
                return {
                    "status": "failed",
                    "local_path": None,
                    "absolute_path": None,
                    "error": "Tamaño de imagen excede el límite permitido",
                }

            raw_bytes = io.BytesIO()
            total_read = 0
            for chunk in response.iter_content(chunk_size=32768):
                total_read += len(chunk)
                if total_read > config.MAX_IMAGE_SIZE_BYTES:
                    return {
                        "status": "failed",
                        "local_path": None,
                        "absolute_path": None,
                        "error": "Tamaño de imagen excedido durante la transferencia",
                    }
                raw_bytes.write(chunk)

            raw_bytes.seek(0)

            # Validación de integridad con Pillow
            try:
                with Image.open(raw_bytes) as img:
                    img_format = img.format
                    # Convertir a RGB y guardar como JPEG optimizado si es necesario
                    if img.mode not in ("RGB", "L"):
                        rgb_img = img.convert("RGB")
                        rgb_img.save(file_path, format="JPEG", quality=90, optimize=True)
                    else:
                        img.save(file_path, format="JPEG", quality=90, optimize=True)
            except Exception as pe:
                logger.warning("Pillow no pudo validar la imagen: %s", pe)
                return {
                    "status": "failed",
                    "local_path": None,
                    "absolute_path": None,
                    "error": f"Archivo de imagen corrupto o no reconocido ({pe})",
                }

            rel_path = file_path.relative_to(config.BASE_DIR).as_posix()
            self._download_cache[url] = rel_path
            logger.info("Imagen guardada exitosamente: %s", rel_path)

            return {
                "status": "downloaded",
                "local_path": rel_path,
                "absolute_path": file_path,
                "error": None,
            }

        except requests.RequestException as re:
            logger.warning("Excepción de red al descargar imagen: %s", re)
            return {
                "status": "failed",
                "local_path": None,
                "absolute_path": None,
                "error": f"Error de red: {re}",
            }
        except Exception as e:
            logger.error("Error inesperado en descarga de imagen: %s", e)
            return {
                "status": "failed",
                "local_path": None,
                "absolute_path": None,
                "error": str(e),
            }
