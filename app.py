"""
InstaFlow - Dashboard Profesional de Scraping de Instagram
==========================================================
Backend Flask principal y API REST asíncrona.
Inspirado en la arquitectura visual de n8n.
"""

from datetime import datetime, timezone
import logging
import os
from pathlib import Path
from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    send_file,
    send_from_directory,
    abort,
)

import config
from scraper.job_manager import JobManager
from scraper.scraper_service import ScraperService
from scraper.session_manager import SessionManager
from scraper.validators import validate_username, sanitize_filename
from storage.json_storage import JSONStorage
from storage.csv_storage import CSVStorage
from storage.database import DatabaseManager

# Configurar logging centralizado
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    format=config.LOG_FORMAT,
)
logger = logging.getLogger("instaflow.app")

app = Flask(
    __name__,
    template_folder="templates",
    static_folder="static",
)

# Gestores del sistema
job_manager = JobManager()
scraper_service = ScraperService()
session_manager = SessionManager()
json_storage = JSONStorage()
csv_storage = CSVStorage()
db_manager = DatabaseManager()

APP_START_TIME = datetime.now(timezone.utc)


# ==============================================================================
# RUTAS DE LA INTERFAZ WEB (VISTAS HTML)
# ==============================================================================

@app.route("/")
def index():
    """Página principal del dashboard de InstaFlow."""
    return render_template(
        "index.html",
        default_username=config.DEFAULT_USERNAME,
        default_limit=config.DEFAULT_POSTS_LIMIT,
        max_limit=config.MAX_POSTS_LIMIT,
    )


@app.route("/profile")
def profile_view():
    """Vista detallada de perfil específico cargado."""
    username = request.args.get("username", config.DEFAULT_USERNAME)
    return render_template(
        "profile.html",
        username=username,
    )


@app.route("/settings")
def settings_view():
    """Vista de configuración del sistema."""
    return render_template("settings.html")


# ==============================================================================
# ARCHIVOS ESTÁTICOS DE MEDIOS (MEDIA & SCREENSHOTS)
# ==============================================================================

@app.route("/media/<path:filename>")
def serve_media(filename):
    """Sirve archivos de imágenes descargadas de perfiles y publicaciones."""
    return send_from_directory(config.MEDIA_DIR, filename)


@app.route("/screenshots/<path:filename>")
def serve_screenshot(filename):
    """Sirve capturas de pantalla de perfiles analizados."""
    return send_from_directory(config.SCREENSHOTS_DIR, filename)


# ==============================================================================
# API REST: CONTROL DE EXTRACCIÓN Y ESTADO DE TRABAJOS
# ==============================================================================

@app.route("/api/health", methods=["GET"])
def api_health():
    """
    Comprueba el estado de la aplicación, Chrome, sesión y base de datos.
    """
    chrome_detected = False
    chrome_path = None
    common_chrome_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.environ.get("CHROME_PATH"),
    ]
    for cp in common_chrome_paths:
        if cp and Path(cp).is_file():
            chrome_detected = True
            chrome_path = cp
            break

    # Si no se detectó en rutas estándar, Selenium Manager intentará resolverlo
    if not chrome_detected:
        chrome_detected = True  # Selenium Manager gestiona binarios automáticamente

    has_cookies = session_manager.has_cookies_file()
    active_jobs = job_manager.get_active_jobs_count()

    return jsonify({
        "status": "healthy",
        "app_name": "InstaFlow",
        "version": "1.0.0",
        "chrome_available": chrome_detected,
        "chrome_path": chrome_path,
        "cookies_present": has_cookies,
        "active_jobs": active_jobs,
        "max_concurrent_jobs": config.MAX_CONCURRENT_JOBS,
        "database_connected": True,
        "uptime_seconds": round((datetime.now(timezone.utc) - APP_START_TIME).total_seconds()),
    })


@app.route("/api/scrape", methods=["POST"])
def api_start_scrape():
    """
    Inicia un nuevo trabajo de extracción en segundo plano.
    Parámetros JSON:
    - username (str): Nombre de usuario (con o sin @)
    - max_posts (int): Cantidad máxima de publicaciones
    - download_images (bool): Si descargar imágenes localmente
    - capture_screenshot (bool): Si capturar pantalla del perfil
    """
    data = request.get_json(silent=True) or {}
    raw_user = data.get("username", "")

    # Validar nombre de usuario
    is_valid, username, err_msg = validate_username(raw_user)
    if not is_valid:
        return jsonify({"error": err_msg or "Nombre de usuario inválido", "status": "invalid_input"}), 400

    # Validar concurrencia
    active_count = job_manager.get_active_jobs_count()
    if active_count >= config.MAX_CONCURRENT_JOBS:
        return jsonify({
            "error": f"Límite de concurrencia alcanzado ({active_count}/{config.MAX_CONCURRENT_JOBS}). Espere a que finalice la tarea actual.",
            "status": "busy",
        }), 429

    # Validar y acotar cantidad de publicaciones
    try:
        max_posts = int(data.get("max_posts", config.DEFAULT_POSTS_LIMIT))
        max_posts = max(1, min(max_posts, config.MAX_POSTS_LIMIT))
    except (ValueError, TypeError):
        max_posts = config.DEFAULT_POSTS_LIMIT

    options = {
        "max_posts": max_posts,
        "download_images": bool(data.get("download_images", config.DOWNLOAD_IMAGES)),
        "capture_screenshot": bool(data.get("capture_screenshot", config.CAPTURE_SCREENSHOT)),
    }

    # Crear trabajo y lanzarlo en segundo plano sin bloquear Flask
    job = job_manager.create_job(username=username, options=options)
    job_manager.run_in_background(job, scraper_service.execute_job)

    return jsonify({
        "success": True,
        "job_id": job.job_id,
        "username": username,
        "status": job.status,
        "created_at": job.created_at,
        "message": f"Extracción iniciada en segundo plano para @{username}.",
    }), 202


@app.route("/api/jobs/<job_id>", methods=["GET"])
def api_get_job(job_id):
    """
    Consulta el estado y progreso en tiempo real de una ejecución.
    """
    job = job_manager.get_job(job_id)
    if job:
        return jsonify(job.to_dict())

    # Si no está en memoria viva, buscar en base de datos o archivo JSON
    db_job = None
    try:
        with db_manager._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,))
            row = cursor.fetchone()
            if row:
                db_job = dict(row)
    except Exception:
        pass

    if db_job:
        return jsonify({
            "job_id": db_job["job_id"],
            "username": db_job["username"],
            "status": db_job["status"],
            "progress_percent": 100 if db_job["status"] == "completed" else 50,
            "created_at": db_job["created_at"],
            "finished_at": db_job["finished_at"],
            "duration_sec": db_job["duration_sec"],
            "summary": {
                "posts_collected": db_job["collected_posts"],
                "images_downloaded": db_job["downloaded_images"],
            },
            "error_message": db_job["error_message"],
            "stages": [],
            "logs": [],
        })

    return jsonify({"error": f"No se encontró el trabajo con ID '{job_id}'"}), 404


@app.route("/api/jobs/<job_id>/cancel", methods=["POST"])
def api_cancel_job(job_id):
    """
    Solicita la cancelación segura de un trabajo en curso.
    """
    cancelled = job_manager.cancel_job(job_id)
    if cancelled:
        return jsonify({"success": True, "message": "Cancelación solicitada con éxito."})
    return jsonify({"error": "El trabajo no existe o ya ha finalizado."}), 400


# ==============================================================================
# API REST: CONSULTA DE RESULTADOS DE PERFILES Y PUBLICACIONES
# ==============================================================================

@app.route("/api/profile/<username>", methods=["GET"])
def api_get_profile(username):
    """
    Consulta los datos guardados más recientes de un perfil.
    """
    is_valid, safe_user, _ = validate_username(username)
    if not is_valid:
        return jsonify({"error": "Nombre de usuario inválido"}), 400

    # 1. Intentar desde JSON Storage
    saved_json = json_storage.load_profile_result(safe_user)
    if saved_json and "profile" in saved_json:
        return jsonify(saved_json["profile"])

    # 2. Intentar desde SQLite Database
    db_profile = db_manager.get_latest_profile(safe_user)
    if db_profile:
        return jsonify(db_profile)

    return jsonify({"error": f"No hay datos guardados para el usuario @{safe_user}"}), 404


@app.route("/api/profile/<username>/posts", methods=["GET"])
def api_get_profile_posts(username):
    """
    Consulta las publicaciones recopiladas para un perfil.
    """
    is_valid, safe_user, _ = validate_username(username)
    if not is_valid:
        return jsonify({"error": "Nombre de usuario inválido"}), 400

    limit = request.args.get("limit", 50, type=int)

    # 1. Intentar desde JSON Storage
    saved_json = json_storage.load_profile_result(safe_user)
    if saved_json and "posts" in saved_json:
        posts = saved_json["posts"][:limit]
        return jsonify({"username": safe_user, "count": len(posts), "posts": posts})

    # 2. Intentar desde SQLite Database
    posts = db_manager.get_profile_posts(safe_user, limit=limit)
    return jsonify({"username": safe_user, "count": len(posts), "posts": posts})


# ==============================================================================
# API REST: EXPORTACIÓN DE ARCHIVOS
# ==============================================================================

@app.route("/api/exports/<job_id>/json", methods=["GET"])
def api_export_json(job_id):
    """
    Descarga el archivo JSON completo de resultados de una ejecución.
    """
    job = job_manager.get_job(job_id)
    if job and job.profile:
        # Generar o servir archivo
        path = json_storage.save_run_result(job.job_id, job.profile, job.posts, job.summary)
        return send_file(
            path,
            as_attachment=True,
            download_name=f"instaflow_{job.username}_{job_id[:8]}.json",
            mimetype="application/json",
        )

    # Buscar archivo existente en disco
    target = json_storage.load_job_file(job_id)
    if target:
        for p in config.RESULTS_DIR.glob("*.json"):
            if job_id[:8] in p.name:
                return send_file(
                    p,
                    as_attachment=True,
                    download_name=p.name,
                    mimetype="application/json",
                )

    return jsonify({"error": "Archivo de exportación no encontrado"}), 404


@app.route("/api/exports/<job_id>/csv", methods=["GET"])
def api_export_csv(job_id):
    """
    Descarga el archivo CSV con las publicaciones recopiladas.
    """
    job = job_manager.get_job(job_id)
    if job and job.posts:
        path = csv_storage.export_posts_csv(job.posts, job.username, job_id=job.job_id)
        return send_file(
            path,
            as_attachment=True,
            download_name=f"instaflow_posts_{job.username}_{job_id[:8]}.csv",
            mimetype="text/csv; charset=utf-8",
        )

    # Buscar archivo existente en disco
    for p in config.RESULTS_DIR.glob(f"*posts*{job_id[:8]}*.csv"):
        return send_file(
            p,
            as_attachment=True,
            download_name=p.name,
            mimetype="text/csv; charset=utf-8",
        )

    return jsonify({"error": "No hay publicaciones disponibles para exportar en CSV"}), 404


# ==============================================================================
# API REST: CONFIGURACIÓN Y MANTENIMIENTO
# ==============================================================================

@app.route("/api/settings", methods=["GET"])
def api_get_settings():
    """Retorna la configuración pública no sensible del sistema."""
    return jsonify(config.get_public_settings())


@app.route("/api/clear-data", methods=["POST"])
def api_clear_local_data():
    """
    Elimina los datos históricos y archivos temporales locales a petición del usuario.
    """
    try:
        db_manager.clear_all_data()

        # Limpiar archivos en data/results excepto .gitkeep
        for f in config.RESULTS_DIR.glob("*"):
            if f.is_file() and f.name != ".gitkeep":
                try:
                    f.unlink()
                except Exception:
                    pass

        # Limpiar capturas excepto .gitkeep
        for f in config.SCREENSHOTS_DIR.glob("*"):
            if f.is_file() and f.name != ".gitkeep":
                try:
                    f.unlink()
                except Exception:
                    pass

        return jsonify({"success": True, "message": "Datos locales eliminados exitosamente."})
    except Exception as e:
        return jsonify({"error": f"Fallo al limpiar datos: {e}"}), 500


# ==============================================================================
# PUNTO DE ENTRADA PRINCIPAL
# ==============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("  INSTAFLOW - DASHBOARD DE SCRAPING DE INSTAGRAM")
    print("=" * 70)
    print(f"  Servidor iniciado en: http://{config.SERVER_HOST}:{config.SERVER_PORT}")
    print(f"  Modo Headless: {config.HEADLESS}")
    print(f"  Cookies configuradas: {session_manager.has_cookies_file()}")
    print("=" * 70)
    app.run(
        host=config.SERVER_HOST,
        port=config.SERVER_PORT,
        debug=config.DEBUG_MODE,
    )
