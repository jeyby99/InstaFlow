"""
InstaFlow Post Extractor
========================
Extracción robusta de publicaciones desde la cuadrícula de Instagram.
Identifica enlaces (/p/ y /reel/), detecta tipos de contenido (foto, carrusel,
video, reel), extrae miniaturas de mayor resolución desde srcset y aísla fallos por publicación.
"""

import logging
import re
import time
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.webdriver import WebDriver

import config
from .validators import parse_count_string
from .exceptions import JobCancelledError

logger = logging.getLogger("instaflow.post_extractor")


class PostExtractor:
    """Extrae publicaciones, miniaturas y metadatos de la cuadrícula del perfil."""

    def __init__(self, driver: WebDriver | None = None):
        self.driver = driver

    def extract_posts_from_grid(
        self,
        max_posts: int = config.DEFAULT_POSTS_LIMIT,
        cancellation_check=None,
    ) -> list[dict]:
        """
        Navega y desplaza la cuadrícula del perfil para recolectar hasta `max_posts` publicaciones.
        Respeta límites de desplazamiento, detecta estancamiento y aísla errores individuales.
        """
        if not self.driver:
            logger.warning("No hay driver disponible para extraer publicaciones de la cuadrícula.")
            return []

        posts_dict: dict[str, dict] = {}
        target_limit = min(max_posts, config.MAX_POSTS_LIMIT)
        scroll_attempts = 0
        consecutive_stalls = 0
        last_found_count = 0

        logger.info("Iniciando extracción de publicaciones en cuadrícula (meta: %d)...", target_limit)

        while len(posts_dict) < target_limit and scroll_attempts < config.MAX_SCROLL_ATTEMPTS:
            # Comprobar cancelación solicitada
            if cancellation_check and cancellation_check():
                logger.info("Cancelación detectada durante la recolección de publicaciones.")
                raise JobCancelledError("Extracción de publicaciones cancelada por el usuario.")

            # Extraer enlaces visibles actualmente en el DOM
            current_batch = self._extract_visible_posts()
            for post in current_batch:
                shortcode = post.get("shortcode")
                if shortcode and shortcode not in posts_dict:
                    posts_dict[shortcode] = post
                    if len(posts_dict) >= target_limit:
                        break

            # Comprobar si se descubrieron nuevas publicaciones
            if len(posts_dict) == last_found_count:
                consecutive_stalls += 1
                if consecutive_stalls >= 3:
                    logger.info("No se detectaron nuevas publicaciones tras 3 desplazamientos. Finalizando cuadrícula.")
                    break
            else:
                consecutive_stalls = 0
                last_found_count = len(posts_dict)

            if len(posts_dict) >= target_limit:
                break

            # Desplazar hacia abajo suavemente para cargar el siguiente bloque
            self.driver.execute_script(f"window.scrollBy({{top: 900, behavior: 'smooth'}});")
            time.sleep(config.SCROLL_PAUSE_TIME)
            scroll_attempts += 1

        collected_posts = list(posts_dict.values())[:target_limit]
        logger.info("Extracción de cuadrícula finalizada: %d publicaciones detectadas.", len(collected_posts))
        return collected_posts

    def _extract_visible_posts(self) -> list[dict]:
        """Analiza los elementos ancla de publicaciones actualmente visibles en el navegador."""
        if not self.driver:
            return []

        posts: list[dict] = []
        try:
            # Buscar todos los enlaces a publicaciones o reels
            elements = self.driver.find_elements(By.XPATH, "//a[contains(@href, '/p/') or contains(@href, '/reel/')]")
            for elem in elements:
                try:
                    href = elem.get_attribute("href") or ""
                    shortcode, media_type_hint = self._parse_shortcode_from_url(href)
                    if not shortcode:
                        continue

                    outer_html = elem.get_attribute("outerHTML") or ""
                    soup = BeautifulSoup(outer_html, "html.parser")
                    post_data = self.parse_post_element(soup, href, shortcode, media_type_hint)
                    posts.append(post_data)
                except Exception as pe:
                    logger.debug("Aviso al procesar elemento individual de publicación: %s", pe)
                    continue
        except Exception as e:
            logger.warning("Aviso al buscar elementos en cuadrícula: %s", e)

        return posts

    def parse_post_element(
        self,
        soup: BeautifulSoup,
        url: str,
        shortcode: str,
        media_type_hint: str = "photo",
    ) -> dict:
        """
        Construye el diccionario de datos de una publicación a partir de su elemento HTML.
        Garantiza que ningún fallo impida procesar las demás publicaciones.
        """
        post = {
            "post_id": f"ig_{shortcode}",
            "shortcode": shortcode,
            "url": url,
            "caption": None,
            "published_at": None,
            "media_type": media_type_hint,
            "like_count": None,
            "comment_count": None,
            "thumbnail_url": None,
            "thumbnail_path": None,
            "media_items": [],
            "download_status": "pending",
            "errors": [],
        }

        # 1. Extraer miniatura desde <img>
        img_tag = soup.find("img")
        if img_tag:
            # Intentar obtener la mejor resolución de srcset
            srcset = img_tag.get("srcset")
            thumbnail_url = self._extract_best_from_srcset(srcset) if srcset else None

            # Fallback a src o currentSrc
            if not thumbnail_url:
                thumbnail_url = img_tag.get("src")

            post["thumbnail_url"] = thumbnail_url

            # Texto alternativo suele contener la descripción o pie de foto
            alt_text = img_tag.get("alt")
            if alt_text:
                post["caption"] = self._clean_caption(alt_text)

        # 2. Detección diferenciada del tipo de contenido
        post["media_type"] = self._detect_media_type(soup, url, media_type_hint)

        # 3. Registrar elemento de medio primario si hay miniatura
        if post["thumbnail_url"]:
            post["media_items"].append({
                "url": post["thumbnail_url"],
                "media_type": "image" if post["media_type"] in ("photo", "carousel") else "thumbnail",
                "index": 0,
            })

        return post

    def _parse_shortcode_from_url(self, url: str) -> tuple[str | None, str]:
        """Extrae el shortcode y una pista inicial de tipo (/p/ o /reel/)."""
        if not url:
            return None, "unknown"

        # Coincidencia con /p/{shortcode}/
        p_match = re.search(r"/p/([a-zA-Z0-9_-]+)", url)
        if p_match:
            return p_match.group(1), "photo"

        # Coincidencia con /reel/{shortcode}/
        reel_match = re.search(r"/reel/([a-zA-Z0-9_-]+)", url)
        if reel_match:
            return reel_match.group(1), "reel"

        return None, "unknown"

    def _extract_best_from_srcset(self, srcset_str: str | None) -> str | None:
        """
        Analiza un atributo srcset de HTML y selecciona la URL con mayor resolución.
        Ej: 'https://... 150w, https://... 240w, https://... 640w'
        """
        if not srcset_str:
            return None

        candidates = []
        for item in srcset_str.split(","):
            parts = item.strip().split(" ")
            if not parts:
                continue
            url = parts[0]
            width = 0
            if len(parts) > 1 and parts[1].endswith("w"):
                try:
                    width = int(parts[1][:-1])
                except ValueError:
                    width = 0
            candidates.append((width, url))

        if not candidates:
            return None

        # Ordenar de mayor a menor ancho
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]

    def _detect_media_type(self, soup: BeautifulSoup, url: str, initial_hint: str) -> str:
        """
        Detecta si la publicación es una foto, carrusel, video o reel.
        """
        if "/reel/" in url:
            return "reel"

        # Detectar indicador visual de carrusel (icono de capas múltiples)
        carousel_indicators = [
            'aria-label="Carousel"',
            'aria-label="Carrusel"',
            'aria-label="Secuencia"',
            'aria-label="Post con varias imágenes"',
        ]
        soup_str = str(soup)
        for ind in carousel_indicators:
            if ind.lower() in soup_str.lower():
                return "carousel"

        # Detectar icono de video
        video_indicators = [
            'aria-label="Clip"',
            'aria-label="Video"',
            'aria-label="Vídeo"',
        ]
        for ind in video_indicators:
            if ind.lower() in soup_str.lower():
                return "video"

        return initial_hint if initial_hint in ("photo", "reel", "video") else "photo"

    def _clean_caption(self, alt_text: str) -> str:
        """
        Limpia el texto descriptivo de la imagen generado por Instagram si corresponde,
        o preserva el pie de foto original si está en el alt.
        """
        cleaned = alt_text.strip()
        # Si tiene el prefijo descriptivo de accesibilidad de Instagram
        prefix_match = re.match(r"(?i)^photo by .*? on .*?\.\s*(.*)$", cleaned)
        if prefix_match:
            extracted = prefix_match.group(1).strip()
            if extracted and not extracted.startswith("May be an image of"):
                return extracted

        return cleaned
