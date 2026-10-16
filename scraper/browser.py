"""
InstaFlow Browser Controller
============================
Gestión del ciclo de vida del WebDriver de Chrome mediante Selenium Manager.
Implementa esperas explícitas, modo headless configurable, capturas de pantalla
y prevención de procesos zombi.
"""

import logging
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException, WebDriverException

import config
from .exceptions import ScrapingTimeoutError, InstaFlowError

logger = logging.getLogger("instaflow.browser")


class BrowserManager:
    """Administra la inicialización, configuración y finalización segura de Chrome."""

    def __init__(self, headless: bool | None = None):
        self.headless = config.HEADLESS if headless is None else headless
        self.driver: webdriver.Chrome | None = None

    def start(self) -> webdriver.Chrome:
        """
        Inicializa una nueva instancia de Google Chrome utilizando Selenium Manager.
        Configura opciones de rendimiento, evasión de interferencias y dimensiones.
        """
        if self.driver is not None:
            return self.driver

        options = Options()

        if self.headless:
            # Modo headless moderno de Chrome
            options.add_argument("--headless=new")

        # Configuración de ventana y rendimiento
        options.add_argument(f"--window-size={config.WINDOW_WIDTH},{config.WINDOW_HEIGHT}")
        options.add_argument(f"--lang={config.BROWSER_LANGUAGE}")
        options.add_argument(f"user-agent={config.IMAGE_USER_AGENT}")

        # Optimizaciones de estabilidad para Windows y contenedores
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-infobars")
        options.add_argument("--disable-notifications")
        options.add_argument("--mute-audio")

        # Evitar marcas obvias de automatización sin infringir términos
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

        # Ruta personalizada de Chrome si está configurada
        service = None
        if config.CHROME_BINARY_PATH:
            options.binary_location = config.CHROME_BINARY_PATH

        try:
            logger.info("Iniciando controlador Chrome con Selenium Manager...")
            # Selenium Manager resuelve automáticamente el chromedriver compatible
            self.driver = webdriver.Chrome(options=options)
            self.driver.set_page_load_timeout(config.PAGE_LOAD_TIMEOUT)
            self.driver.set_script_timeout(config.PAGE_LOAD_TIMEOUT)
            logger.info("Navegador Chrome iniciado correctamente.")
            return self.driver
        except WebDriverException as e:
            logger.error("Error al iniciar Google Chrome: %s", e)
            self.quit()
            raise InstaFlowError(
                f"No se pudo inicializar Google Chrome. Verifique que Chrome esté instalado. Detalle: {e}"
            ) from e

    def safe_get(self, url: str, timeout: int | None = None) -> bool:
        """
        Navega de forma segura a una URL respetando el timeout configurado.
        """
        if not self.driver:
            raise InstaFlowError("El navegador no ha sido iniciado.")

        effective_timeout = timeout or config.PAGE_LOAD_TIMEOUT
        try:
            self.driver.set_page_load_timeout(effective_timeout)
            logger.debug("Navegando a: %s", url)
            self.driver.get(url)
            return True
        except TimeoutException:
            logger.warning("Tiempo de espera agotado al cargar %s tras %ds", url, effective_timeout)
            # Detener la carga para permitir procesar lo recibido
            try:
                self.driver.execute_script("window.stop();")
            except Exception:
                pass
            return False
        except WebDriverException as e:
            logger.error("Error al navegar a %s: %s", url, e)
            raise ScrapingTimeoutError(f"Error de conexión o timeout al cargar {url}: {e}")

    def wait_for_element(self, by: By, value: str, timeout: int | None = None):
        """
        Espera explícitamente a que un elemento esté presente en el DOM.
        """
        if not self.driver:
            raise InstaFlowError("El navegador no ha sido iniciado.")

        wait_seconds = timeout or config.ELEMENT_TIMEOUT
        wait = WebDriverWait(self.driver, wait_seconds)
        try:
            return wait.until(EC.presence_of_element_located((by, value)))
        except TimeoutException:
            return None

    def execute_scroll(self, pixels: int = 1200) -> None:
        """Desplaza suavemente la ventana hacia abajo para activar carga diferida."""
        if self.driver:
            self.driver.execute_script(f"window.scrollBy({{top: {pixels}, behavior: 'smooth'}});")

    def capture_screenshot(self, target_path: Path) -> bool:
        """
        Captura la pantalla actual y la guarda en la ruta indicada.
        """
        if not self.driver:
            return False

        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            saved = self.driver.save_screenshot(str(target_path))
            if saved:
                logger.info("Captura de pantalla guardada en: %s", target_path)
            return saved
        except Exception as e:
            logger.warning("No se pudo guardar la captura de pantalla: %s", e)
            return False

    def get_page_source(self) -> str:
        """Retorna el código fuente HTML actual del navegador."""
        if not self.driver:
            return ""
        try:
            return self.driver.page_source
        except Exception:
            return ""

    def quit(self) -> None:
        """Cierra el navegador y libera recursos."""
        if self.driver:
            try:
                logger.debug("Cerrando instancia de Chrome...")
                self.driver.quit()
            except Exception as e:
                logger.debug("Aviso al cerrar Chrome: %s", e)
            finally:
                self.driver = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.quit()
