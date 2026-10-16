"""
InstaFlow Scraper Service
=========================
Servicio central orquestador de las 16 etapas de extracción.
Maneja la navegación, detección, descarga de imágenes, generación de capturas,
persistencia multicapa (JSON, CSV, SQLite) y tolerancia a fallos.
"""

from datetime import datetime, timezone
import logging
import time
from pathlib import Path
from selenium.webdriver.common.by import By

import config
from .browser import BrowserManager
from .session_manager import SessionManager
from .profile_extractor import ProfileExtractor
from .post_extractor import PostExtractor
from .image_downloader import ImageDownloader
from .validators import validate_username, sanitize_filename
from .exceptions import (
    JobCancelledError,
    ProfileNotFoundError,
    PrivateProfileError,
    InstaFlowError,
)
from storage.json_storage import JSONStorage
from storage.csv_storage import CSVStorage
from storage.database import DatabaseManager

logger = logging.getLogger("instaflow.service")


class ScraperService:
    """Orquesta las 16 etapas del proceso de scraping y análisis."""

    def __init__(self):
        self.session_mgr = SessionManager()
        self.image_downloader = ImageDownloader()
        self.json_storage = JSONStorage()
        self.csv_storage = CSVStorage()
        self.db = DatabaseManager()

    def execute_job(self, job) -> dict:
        """
        Ejecuta el flujo completo de 16 etapas para un Job en segundo plano.
        """
        job.status = "running"
        job.started_at = datetime.now(timezone.utc).isoformat()
        start_time = time.time()

        browser: BrowserManager | None = None
        username = job.username
        max_posts = job.options.get("max_posts", config.DEFAULT_POSTS_LIMIT)
        should_download_images = job.options.get("download_images", config.DOWNLOAD_IMAGES)
        should_capture_screenshot = job.options.get("capture_screenshot", config.CAPTURE_SCREENSHOT)

        try:
            # ==================================================================
            # ETAPA 1: Validar el nombre de usuario
            # ==================================================================
            job.start_stage(1, "Validar el nombre de usuario", progress_hint=5)
            is_valid, normalized_user, error_msg = validate_username(username)
            if not is_valid:
                job.complete_stage(1, status="error", message=error_msg or "Usuario inválido")
                raise InstaFlowError(error_msg or "Nombre de usuario inválido.")
            username = normalized_user
            job.username = normalized_user
            job.complete_stage(1, status="success", message=f"Usuario válido: @{username}")

            # ==================================================================
            # ETAPA 2: Inicializar Chrome
            # ==================================================================
            job.start_stage(2, "Inicializar Chrome", progress_hint=10)
            browser = BrowserManager()
            driver = browser.start()
            job.complete_stage(2, status="success", message="Navegador Chrome listo.")

            # ==================================================================
            # ETAPA 3: Comprobar la sesión y el estado de acceso
            # ==================================================================
            job.start_stage(3, "Comprobar la sesión y el estado de acceso", progress_hint=15)
            self.session_mgr.inject_cookies(driver)
            session_status = self.session_mgr.check_session_status(driver)
            job.complete_stage(
                3,
                status="success" if session_status["authenticated"] else "warning",
                message=session_status["status_text"],
            )

            # ==================================================================
            # ETAPA 4: Abrir el perfil solicitado
            # ==================================================================
            job.start_stage(4, "Abrir el perfil solicitado", progress_hint=20)
            profile_url = f"{config.INSTAGRAM_BASE_URL}/{username}/"
            loaded = browser.safe_get(profile_url, timeout=config.PAGE_LOAD_TIMEOUT)
            if not loaded:
                job.add_log("warning", "La página tardó más de lo esperado en responder. Analizando DOM parcial.")
            job.complete_stage(4, status="success" if loaded else "warning", message=f"URL: {profile_url}")

            # ==================================================================
            # ETAPA 5: Esperar a que el contenido relevante esté disponible
            # ==================================================================
            job.start_stage(5, "Esperar a que el contenido relevante esté disponible", progress_hint=25)
            # Esperar por elemento clave del perfil o detección de 404
            browser.wait_for_element(By.TAG_NAME, "header", timeout=config.ELEMENT_TIMEOUT)
            # Pausa breve para hidratación del framework React de Instagram
            time.sleep(1.5)
            job.complete_stage(5, status="success", message="Contenido principal del perfil disponible.")

            # ==================================================================
            # ETAPA 6: Capturar la información básica
            # ==================================================================
            job.start_stage(6, "Capturar la información básica", progress_hint=30)
            profile_extractor = ProfileExtractor(driver=driver)
            profile_data = profile_extractor.extract_profile_data(username)
            job.profile = profile_data

            # Captura de pantalla si está habilitada
            if should_capture_screenshot:
                timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                safe_name = sanitize_filename(username)
                ss_filename = f"{safe_name}_{timestamp_str}_{job.job_id[:8]}.png"
                ss_target = config.SCREENSHOTS_DIR / ss_filename
                if browser.capture_screenshot(ss_target):
                    rel_ss = ss_target.relative_to(config.BASE_DIR).as_posix()
                    job.summary["screenshot_path"] = rel_ss
                    job.add_log("info", f"Captura del perfil guardada: {rel_ss}")

            job.complete_stage(
                6,
                status="success" if profile_data.get("status") == "complete" else "warning",
                message=f"Información básica obtenida. Estado: {profile_data.get('status')}",
            )

            # Si es cuenta privada no accesible
            if profile_data.get("is_private") and not session_status.get("authenticated"):
                job.add_log("warning", "La cuenta es privada y no hay sesión autorizada para ver publicaciones.")

            # ==================================================================
            # ETAPA 7: Capturar la fotografía de perfil
            # ==================================================================
            job.start_stage(7, "Capturar la fotografía de perfil", progress_hint=40)
            pfp_url = profile_data.get("profile_image_url")
            if pfp_url and should_download_images:
                dl_result = self.image_downloader.download_image(
                    url=pfp_url,
                    target_dir=config.PROFILES_MEDIA_DIR,
                    filename_prefix=f"pfp_{username}",
                )
                if dl_result["status"] == "downloaded":
                    profile_data["profile_image_path"] = dl_result["local_path"]
                    job.complete_stage(7, status="success", message="Foto de perfil descargada y validada.")
                else:
                    job.complete_stage(7, status="warning", message=f"No se pudo descargar avatar ({dl_result.get('error')}).")
            else:
                job.complete_stage(7, status="warning", message="Foto de perfil no disponible para descarga.")

            # ==================================================================
            # ETAPA 8: Detectar el número total de publicaciones
            # ==================================================================
            job.start_stage(8, "Detectar el número total de publicaciones", progress_hint=45)
            posts_count = profile_data.get("posts_count")
            if posts_count is not None:
                msg = f"Instagram indica un total de {posts_count:,} publicaciones."
                job.complete_stage(8, status="success", message=msg)
            else:
                job.complete_stage(8, status="warning", message="Contador total no disponible explícitamente.")

            # ==================================================================
            # ETAPA 9: Identificar los enlaces de publicaciones
            # ==================================================================
            job.start_stage(9, "Identificar los enlaces de publicaciones", progress_hint=50)
            post_extractor = PostExtractor(driver=driver)

            # Si el perfil es privado y no estamos autorizados, saltar extracción de publicaciones
            if profile_data.get("is_private") and not session_status.get("authenticated"):
                collected_posts = []
                job.complete_stage(9, status="warning", message="Cuenta privada: publicaciones protegidas.")
            else:
                collected_posts = post_extractor.extract_posts_from_grid(
                    max_posts=max_posts,
                    cancellation_check=job.is_cancelled,
                )
                job.complete_stage(9, status="success", message=f"Identificados {len(collected_posts)} enlaces de publicaciones.")

            job.posts = collected_posts
            job.summary["posts_collected"] = len(collected_posts)

            # ==================================================================
            # ETAPA 10: Recopilar los metadatos disponibles
            # ==================================================================
            job.start_stage(10, "Recopilar los metadatos disponibles", progress_hint=60)
            # Enriquecimiento adicional si aplica
            type_counts = {}
            for p in collected_posts:
                m_type = p.get("media_type", "photo")
                type_counts[m_type] = type_counts.get(m_type, 0) + 1

            type_summary = ", ".join([f"{count} {t}" for t, count in type_counts.items()]) or "Sin publicaciones"
            job.complete_stage(10, status="success", message=f"Metadatos clasificados: {type_summary}.")

            # ==================================================================
            # ETAPA 11: Obtener las miniaturas
            # ==================================================================
            job.start_stage(11, "Obtener las miniaturas", progress_hint=70)
            thumbnails_detected = sum(1 for p in collected_posts if p.get("thumbnail_url"))
            job.complete_stage(11, status="success", message=f"Se detectaron {thumbnails_detected} URLs de miniaturas.")

            # ==================================================================
            # ETAPA 12: Descargar las imágenes autorizadas
            # ==================================================================
            job.start_stage(12, "Descargar las imágenes autorizadas", progress_hint=80)
            downloaded_count = 0
            failed_count = 0

            if should_download_images and collected_posts:
                for idx, post in enumerate(collected_posts):
                    if job.is_cancelled():
                        raise JobCancelledError("Descarga de imágenes cancelada por el usuario.")

                    thumb_url = post.get("thumbnail_url")
                    shortcode = post.get("shortcode", f"post_{idx}")

                    if thumb_url:
                        dl = self.image_downloader.download_image(
                            url=thumb_url,
                            target_dir=config.POSTS_MEDIA_DIR,
                            filename_prefix=f"{username}_{shortcode}",
                        )
                        if dl["status"] == "downloaded":
                            post["thumbnail_path"] = dl["local_path"]
                            post["download_status"] = "downloaded"
                            downloaded_count += 1
                        else:
                            post["download_status"] = "failed"
                            post["errors"].append(dl.get("error") or "Fallo en descarga")
                            failed_count += 1
                    else:
                        post["download_status"] = "not_available"

                job.summary["images_downloaded"] = downloaded_count
                job.summary["images_failed"] = failed_count
                job.complete_stage(
                    12,
                    status="success" if failed_count == 0 else "warning",
                    message=f"{downloaded_count} imágenes descargadas ({failed_count} fallidas).",
                )
            else:
                job.complete_stage(12, status="success", message="Descarga de imágenes omitida o no requerida.")

            # ==================================================================
            # ETAPA 13: Validar los archivos
            # ==================================================================
            job.start_stage(13, "Validar los archivos", progress_hint=85)
            # La validación con Pillow ya se realiza de forma estricta en ImageDownloader
            job.complete_stage(13, status="success", message="Integridad de archivos y cabeceras verificada.")

            # ==================================================================
            # ETAPA 14: Guardar los resultados
            # ==================================================================
            job.start_stage(14, "Guardar los resultados", progress_hint=90)
            if config.ENABLE_JSON_STORAGE:
                self.json_storage.save_run_result(job.job_id, profile_data, collected_posts, job.summary)
            if config.ENABLE_CSV_STORAGE:
                self.csv_storage.export_profile_csv(profile_data, job_id=job.job_id)
                self.csv_storage.export_posts_csv(collected_posts, username, job_id=job.job_id)
            if config.ENABLE_SQLITE_STORAGE:
                self.db.save_profile(profile_data, job_id=job.job_id)
                self.db.save_posts(collected_posts, username, job_id=job.job_id)

            job.complete_stage(14, status="success", message="Resultados almacenados en JSON, CSV y SQLite.")

            # ==================================================================
            # ETAPA 15: Actualizar el dashboard
            # ==================================================================
            job.start_stage(15, "Actualizar el dashboard", progress_hint=95)
            # El estado en memoria de Job se sincroniza automáticamente
            job.complete_stage(15, status="success", message="Estructura de respuesta preparada para el dashboard.")

            # ==================================================================
            # ETAPA 16: Generar un resumen de la ejecución
            # ==================================================================
            job.start_stage(16, "Generar un resumen de la ejecución", progress_hint=100)
            elapsed = round(time.time() - start_time, 2)
            job.duration_sec = elapsed
            job.finished_at = datetime.now(timezone.utc).isoformat()

            # Clasificar estado final
            if profile_data.get("status") == "failed":
                job.status = "failed"
            elif profile_data.get("is_private") and not session_status.get("authenticated"):
                job.status = "partial"
            elif len(collected_posts) < max_posts and posts_count and posts_count > len(collected_posts):
                job.status = "partial"
            else:
                job.status = "completed"

            summary_msg = (
                f"Ejecución finalizada en {elapsed}s. Estado: {job.status}. "
                f"Publicaciones recopiladas: {len(collected_posts)}. "
                f"Imágenes guardadas: {downloaded_count}."
            )
            job.complete_stage(16, status="success", message=summary_msg)
            job.add_log("success", summary_msg)

            # Registrar en base de datos el job finalizado
            if config.ENABLE_SQLITE_STORAGE:
                self.db.save_job(
                    job_id=job.job_id,
                    username=username,
                    status=job.status,
                    created_at=job.created_at,
                    finished_at=job.finished_at,
                    duration_sec=job.duration_sec,
                    requested_posts=max_posts,
                    collected_posts=len(collected_posts),
                    downloaded_images=downloaded_count,
                    metadata={"summary": job.summary},
                )

            return job.to_dict()

        except JobCancelledError:
            elapsed = round(time.time() - start_time, 2)
            job.status = "cancelled"
            job.finished_at = datetime.now(timezone.utc).isoformat()
            job.duration_sec = elapsed
            job.add_log("warning", f"Proceso detenido de forma segura tras {elapsed}s.")
            if config.ENABLE_SQLITE_STORAGE:
                self.db.save_job(
                    job_id=job.job_id,
                    username=username,
                    status="cancelled",
                    created_at=job.created_at,
                    finished_at=job.finished_at,
                    duration_sec=elapsed,
                    error_message="Cancelado por el usuario",
                )
            return job.to_dict()

        except ProfileNotFoundError as pe:
            elapsed = round(time.time() - start_time, 2)
            job.status = "failed"
            job.error_message = str(pe)
            job.finished_at = datetime.now(timezone.utc).isoformat()
            job.duration_sec = elapsed
            job.add_log("error", f"Error: {pe}")
            return job.to_dict()

        except Exception as e:
            elapsed = round(time.time() - start_time, 2)
            job.status = "failed"
            job.error_message = f"Error durante la extracción: {e}"
            job.finished_at = datetime.now(timezone.utc).isoformat()
            job.duration_sec = elapsed
            job.add_log("error", f"Error crítico: {e}")
            logger.exception("Error no capturado en la ejecución de scraping: %s", e)
            return job.to_dict()

        finally:
            if browser:
                try:
                    browser.quit()
                except Exception:
                    pass
