"""
InstaFlow Session Manager
=========================
Administración segura de sesiones autorizadas mediante cookies locales.
Excluye credenciales de los registros y gestiona la inyección de cookies en Selenium.
"""

import json
import logging
from pathlib import Path
from selenium import webdriver

import config

logger = logging.getLogger("instaflow.session")


class SessionManager:
    """Gestiona la autenticación autorizada con cookies locales."""

    def __init__(self, cookies_file: Path | None = None):
        self.cookies_file = cookies_file or config.COOKIES_FILE

    def has_cookies_file(self) -> bool:
        """Indica si el archivo de cookies existe localmente."""
        return self.cookies_file.is_file() and self.cookies_file.stat().st_size > 5

    def load_cookies(self) -> list[dict]:
        """
        Carga las cookies desde el archivo JSON local.
        Nunca expone los valores en los logs.
        """
        if not self.has_cookies_file():
            return []

        try:
            with open(self.cookies_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            if isinstance(data, list):
                logger.info("Archivo cookies.json cargado exitosamente (%d entradas).", len(data))
                return data
            logger.warning("El formato de cookies.json no es una lista válida.")
            return []
        except Exception as e:
            logger.warning("No se pudo leer cookies.json: %s", e)
            return []

    def inject_cookies(self, driver: webdriver.Chrome) -> int:
        """
        Navega al dominio base de Instagram e inyecta las cookies autorizadas.
        Retorna la cantidad de cookies inyectadas con éxito.
        """
        cookies = self.load_cookies()
        if not cookies:
            logger.info("No hay cookies locales configuradas; se procederá en modo público.")
            return 0

        # Para inyectar cookies, Selenium debe estar primero en el dominio
        try:
            driver.get(config.INSTAGRAM_BASE_URL)
        except Exception as e:
            logger.warning("Aviso al abrir página base para inyectar cookies: %s", e)

        injected = 0
        for cookie in cookies:
            if not isinstance(cookie, dict) or "name" not in cookie or "value" not in cookie:
                continue

            cookie_dict = {
                "name": str(cookie["name"]),
                "value": str(cookie["value"]),
                "domain": cookie.get("domain", ".instagram.com"),
                "path": cookie.get("path", "/"),
            }
            if "secure" in cookie:
                cookie_dict["secure"] = bool(cookie["secure"])
            if "httpOnly" in cookie:
                cookie_dict["httpOnly"] = bool(cookie["httpOnly"])

            try:
                driver.add_cookie(cookie_dict)
                injected += 1
            except Exception as e:
                logger.debug("No se pudo inyectar cookie %s: %s", cookie["name"], e)

        logger.info("Se inyectaron %d cookies autorizadas en la sesión.", injected)
        return injected

    def check_session_status(self, driver: webdriver.Chrome) -> dict:
        """
        Verifica si la sesión actual con el navegador es autorizada o anónima/pública.
        """
        has_file = self.has_cookies_file()

        try:
            # Comprobar indicadores en la página actual
            current_url = driver.current_url or ""
            page_source = driver.page_source or ""

            # Si Instagram redirige a login
            if "/accounts/login/" in current_url:
                return {
                    "authenticated": False,
                    "cookie_file_present": has_file,
                    "status_text": "No autenticado (Redirigido a pantalla de inicio de sesión)",
                    "code": "login_required",
                }

            # Si detectamos elementos de usuario logueado en la barra lateral o superior
            # Instagram suele tener enlaces a direct, nuevo post, o avatar de perfil
            is_logged_in = any(
                tag in page_source
                for tag in [
                    'aria-label="Direct"',
                    'aria-label="Mensajes"',
                    'aria-label="Nueva publicación"',
                    'aria-label="New post"',
                    'href="/direct/inbox/"',
                    'data-testid="user-avatar"',
                ]
            )

            if is_logged_in:
                return {
                    "authenticated": True,
                    "cookie_file_present": has_file,
                    "status_text": "Sesión autorizada activa",
                    "code": "authenticated",
                }

            # Si no está logueado pero se puede consultar información pública
            return {
                "authenticated": False,
                "cookie_file_present": has_file,
                "status_text": "Modo público (sin sesión activa o cookies anónimas)",
                "code": "public_mode",
            }
        except Exception as e:
            return {
                "authenticated": False,
                "cookie_file_present": has_file,
                "status_text": f"Estado desconocido ({e})",
                "code": "unknown",
            }
