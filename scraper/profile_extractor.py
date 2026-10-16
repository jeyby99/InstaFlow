"""
InstaFlow Profile Extractor
===========================
Extracción multiescalonada y resiliente de datos de perfiles de Instagram.
Combina etiquetas Open Graph, metadatos estructurados JSON-LD y selectores semánticos DOM.
Conserva saltos de línea y emojis en la biografía.
"""

from datetime import datetime, timezone
import json
import logging
import re
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.webdriver import WebDriver

import config
from .validators import parse_count_string
from .exceptions import ProfileNotFoundError, PrivateProfileError

logger = logging.getLogger("instaflow.profile_extractor")


class ProfileExtractor:
    """Extrae la información pública o autorizada del perfil de Instagram."""

    def __init__(self, driver: WebDriver | None = None):
        self.driver = driver

    def extract_profile_data(self, username: str, html_content: str | None = None) -> dict:
        """
        Analiza el perfil utilizando el HTML proporcionado o el del navegador actual.
        Retorna el diccionario estructurado del perfil según la especificación del proyecto.
        """
        source = html_content or (self.driver.page_source if self.driver else "")
        if not source:
            return self._build_empty_profile(username, errors=["No se pudo obtener el contenido HTML de la página."])

        soup = BeautifulSoup(source, "html.parser")

        # 1. Verificar si la página no existe (404 / usuario no encontrado)
        if self._is_not_found(soup, source):
            logger.warning("Perfil no encontrado para el usuario: %s", username)
            raise ProfileNotFoundError(f"El perfil '@{username}' no existe o no está disponible.")

        # 2. Inicializar estructura base
        profile_data = {
            "username": username,
            "full_name": None,
            "biography": None,
            "profile_image_url": None,
            "profile_image_path": None,
            "followers_count": None,
            "following_count": None,
            "posts_count": None,
            "profile_url": f"{config.INSTAGRAM_BASE_URL}/{username}/",
            "is_private": None,
            "is_verified": None,
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "status": "partial",
            "errors": [],
        }

        # 3. Detectar si la cuenta es privada
        is_private = self._is_private_account(soup, source)
        profile_data["is_private"] = is_private

        # 4. Estrategia A: Metadatos Open Graph (muy fiables para contadores y avatar)
        self._extract_from_open_graph(soup, profile_data)

        # 5. Estrategia B: Metadatos JSON-LD estructurados
        self._extract_from_json_ld(soup, profile_data)

        # 6. Estrategia C: Selectores semánticos directos en el DOM
        self._extract_from_dom_selectors(soup, profile_data)

        # 7. Si hay un driver activo, intentar extracción complementaria interactiva
        if self.driver:
            self._extract_from_live_driver(self.driver, profile_data)

        # Determinar estado de completitud
        key_fields = ["followers_count", "following_count", "posts_count", "profile_image_url"]
        available_keys = [f for f in key_fields if profile_data.get(f) is not None]

        if len(available_keys) >= 3 and profile_data.get("full_name"):
            profile_data["status"] = "complete"
        elif len(available_keys) > 0 or profile_data.get("biography"):
            profile_data["status"] = "partial"
        else:
            profile_data["status"] = "failed"
            profile_data["errors"].append("No se pudieron extraer datos esenciales del perfil.")

        return profile_data

    def _is_not_found(self, soup: BeautifulSoup, source: str) -> bool:
        """Determina si la página indica que el perfil no existe."""
        not_found_texts = [
            "sorry, this page isn't available",
            "esta página no está disponible",
            "the link you followed may be broken",
            "es posible que el enlace que has seguido sea incorrecto",
            "page not found",
        ]
        source_lower = source.lower()
        title = soup.find("title")
        title_text = title.get_text().lower() if title else ""

        if any(nft in title_text for nft in not_found_texts):
            return True

        h2_tags = soup.find_all("h2")
        for h2 in h2_tags:
            h2_text = h2.get_text().lower()
            if any(nft in h2_text for nft in not_found_texts):
                return True

        return False

    def _is_private_account(self, soup: BeautifulSoup, source: str) -> bool:
        """Detecta si la cuenta está marcada como privada."""
        private_indicators = [
            "esta cuenta es privada",
            "this account is private",
            "sigue a esta cuenta para ver sus fotos y vídeos",
            "follow to see their photos and videos",
        ]
        source_lower = source.lower()
        for ind in private_indicators:
            if ind in source_lower:
                return True
        return False

    def _extract_from_open_graph(self, soup: BeautifulSoup, data: dict) -> None:
        """Extrae contadores, bio, nombre y foto desde etiquetas <meta> Open Graph."""
        # og:image (foto de perfil)
        og_image = soup.find("meta", property="og:image")
        if og_image and og_image.get("content"):
            data["profile_image_url"] = og_image["content"]

        # og:title (Nombre y usuario)
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            title_text = og_title["content"]
            # Formato típico: "Nombre Visible (@username) • Fotos y vídeos de Instagram"
            match = re.search(r"^(.*?)\s*\(@[\w.]+\)", title_text)
            if match and not data["full_name"]:
                full_name = match.group(1).strip()
                if full_name:
                    data["full_name"] = full_name

        # og:description (Contadores y biografía)
        og_desc = soup.find("meta", property="og:description")
        if og_desc and og_desc.get("content"):
            desc_text = og_desc["content"]
            self._parse_og_description(desc_text, data)

    def _parse_og_description(self, desc_text: str, data: dict) -> None:
        """
        Parsea cadenas como:
        '10.5M Followers, 50 Following, 1,234 Posts - See Instagram photos and videos from ...'
        o en español:
        '17M seguidores, 679 siguiendo, 672 publicaciones - Ver fotos y vídeos de Instagram de ...'
        o '10.5M seguidores, 50 seguidos, 1.234 publicaciones'
        """
        # Separar contadores de la descripción
        parts = desc_text.split(" - ", 1)
        counters_part = parts[0]

        # Extraer Followers / Seguidores
        followers_match = re.search(
            r"(?:^|[\s,])([\d][\d.,\s]*[kKmM]?)\s*(?:followers?|seguidores?|seguidors?|abonn[eé]s?)\b",
            desc_text,
            re.IGNORECASE,
        )
        if followers_match and data["followers_count"] is None:
            data["followers_count"] = parse_count_string(followers_match.group(1))

        # Extraer Following / Seguidos / Siguiendo
        following_match = re.search(
            r"(?:^|[\s,])([\d][\d.,\s]*[kKmM]?)\s*(?:following|seguidos?|seguidas?|siguiendo|seguindo|abonnements?|seguiti)\b",
            desc_text,
            re.IGNORECASE,
        )
        if following_match and data["following_count"] is None:
            data["following_count"] = parse_count_string(following_match.group(1))

        # Soporte inverso para Following ("siguiendo a 679", "following 50", etc.)
        if data["following_count"] is None:
            rev_following = re.search(
                r"(?:following|seguidos?|seguidas?|siguiendo|seguindo)\s*(?:a\s*)?([\d][\d.,\s]*[kKmM]?)\b",
                desc_text,
                re.IGNORECASE,
            )
            if rev_following:
                data["following_count"] = parse_count_string(rev_following.group(1))

        # Extraer Posts / Publicaciones
        posts_match = re.search(
            r"(?:^|[\s,])([\d][\d.,\s]*[kKmM]?)\s*(?:posts?|publicaciones|publicaci[oó]n|publicac[oõ]es)\b",
            desc_text,
            re.IGNORECASE,
        )
        if posts_match and data["posts_count"] is None:
            data["posts_count"] = parse_count_string(posts_match.group(1))

        # Biografía en la segunda parte si está incluida
        if len(parts) > 1 and not data["biography"]:
            raw_bio = parts[1]
            # Limpiar prefijo 'See Instagram photos and videos from...'
            bio_cleaned = re.sub(
                r"(?i)^(?:see instagram photos and videos from|mira las fotos y v[ií]deos de instagram de|ve las fotos y v[ií]deos de|ver fotos y v[ií]deos de instagram de).*?:\s*",
                "",
                raw_bio,
            ).strip('" ')
            if bio_cleaned and bio_cleaned != data.get("full_name"):
                data["biography"] = bio_cleaned

    def _extract_from_json_ld(self, soup: BeautifulSoup, data: dict) -> None:
        """Extrae metadatos estructurados Schema.org si están disponibles."""
        scripts = soup.find_all("script", type="application/ld+json")
        for script in scripts:
            try:
                content = script.string or script.get_text()
                if not content:
                    continue
                parsed = json.loads(content)
                if isinstance(parsed, dict):
                    if parsed.get("@type") in ("Person", "ProfilePage", "Organization"):
                        if not data["full_name"] and parsed.get("name"):
                            data["full_name"] = parsed["name"]
                        if not data["biography"] and parsed.get("description"):
                            data["biography"] = parsed["description"]
                        if not data["profile_image_url"] and parsed.get("image"):
                            data["profile_image_url"] = parsed["image"]
            except Exception:
                continue

    def _extract_from_dom_selectors(self, soup: BeautifulSoup, data: dict) -> None:
        """Extrae datos mediante selectores semánticos de elementos de la interfaz."""
        # 1. Avatar del perfil
        if not data["profile_image_url"]:
            img_candidate = soup.find(
                "img",
                alt=re.compile(r"(profile picture|foto del perfil|foto de perfil)", re.IGNORECASE),
            )
            if img_candidate and img_candidate.get("src"):
                data["profile_image_url"] = img_candidate["src"]

        # 2. Nombre completo / visible
        if not data["full_name"]:
            # Típicamente está en un span o div en el encabezado
            name_span = soup.find("span", class_=re.compile(r"x1lliihq.*x193iq5w", re.IGNORECASE))
            if name_span and name_span.get_text().strip():
                cand = name_span.get_text().strip()
                if cand != data["username"]:
                    data["full_name"] = cand

        # 3. Verificación
        if data["is_verified"] is None:
            verified_svg = soup.find(
                lambda tag: tag.name in ("svg", "span")
                and any(
                    "verificado" in (tag.get("aria-label") or "").lower()
                    or "verified" in (tag.get("aria-label") or "").lower()
                    or "verificada" in (tag.get("title") or "").lower()
                    for _ in [0]
                )
            )
            data["is_verified"] = verified_svg is not None

        # 4. Biografía con preservación de saltos de línea
        if not data["biography"]:
            # Buscar secciones que contengan la biografía
            bio_candidates = soup.find_all(["div", "h1", "span"], class_=re.compile(r"_aa_c|_aaco", re.IGNORECASE))
            for cand in bio_candidates:
                text = cand.get_text(separator="\n").strip()
                if text and len(text) > 3 and text != data["username"] and text != data["full_name"]:
                    data["biography"] = text
                    break

    def _extract_from_live_driver(self, driver: WebDriver, data: dict) -> None:
        """Intenta extraer valores directamente mediante la API de Selenium si aún faltan campos."""
        try:
            if data["followers_count"] is not None and data["following_count"] is not None and data["posts_count"] is not None:
                return

            # Buscar contadores en elementos del encabezado (a, li, span, button)
            elements = driver.find_elements(
                By.XPATH,
                "//header//a | //header//ul//li | //header//span | //header//button | //a[contains(@href, 'following') or contains(@href, 'followers')]"
            )
            for el in elements:
                try:
                    text = el.text.strip()
                    if not text:
                        continue
                    lower_text = text.lower()
                    if "publicaci" in lower_text or "posts" in lower_text:
                        if data["posts_count"] is None:
                            cnt = parse_count_string(text)
                            if cnt is not None:
                                data["posts_count"] = cnt
                    elif "seguidor" in lower_text or "follower" in lower_text:
                        if data["followers_count"] is None:
                            cnt = parse_count_string(text)
                            if cnt is not None:
                                data["followers_count"] = cnt
                    elif "siguiendo" in lower_text or "seguid" in lower_text or "following" in lower_text:
                        if data["following_count"] is None:
                            cnt = parse_count_string(text)
                            if cnt is not None:
                                data["following_count"] = cnt
                except Exception:
                    continue
        except Exception as e:
            logger.debug("Aviso en extracción interactiva con Selenium: %s", e)

    def _build_empty_profile(self, username: str, errors: list[str]) -> dict:
        """Crea un objeto de perfil vacío con estado de error."""
        return {
            "username": username,
            "full_name": None,
            "biography": None,
            "profile_image_url": None,
            "profile_image_path": None,
            "followers_count": None,
            "following_count": None,
            "posts_count": None,
            "profile_url": f"{config.INSTAGRAM_BASE_URL}/{username}/",
            "is_private": None,
            "is_verified": None,
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "status": "failed",
            "errors": errors,
        }
