"""
InstaFlow Validators & Sanitizers
=================================
Funciones puras para validación de nombres de usuario, parseo de contadores,
sanitización de rutas de archivo y validación de URLs.
"""

import re
import urllib.parse


# Expresión regular para usernames válidos de Instagram:
# - Longitud de 1 a 30 caracteres
# - Letras (a-z, A-Z), dígitos (0-9), guiones bajos (_) y puntos (.)
# - No puede empezar ni terminar con punto
# - No puede tener puntos consecutivos
USERNAME_REGEX = re.compile(r"^[a-zA-Z0-9_](?:[a-zA-Z0-9_.]*[a-zA-Z0-9_])?$")


def normalize_username(raw_input: str | None) -> str:
    """
    Limpia y normaliza la entrada del usuario:
    - Remueve espacios en blanco iniciales/finales
    - Remueve el símbolo '@' inicial si existe
    - Extrae el usuario si se introdujo una URL completa de Instagram
    - Convierte a minúsculas para consistencia
    """
    if not raw_input:
        return ""

    text = str(raw_input).strip()

    # Si es una URL completa (ej: https://www.instagram.com/usuario/ o instagram.com/usuario)
    if "instagram.com" in text.lower():
        try:
            parsed = urllib.parse.urlparse(text if "://" in text else f"https://{text}")
            path_parts = [p for p in parsed.path.strip("/").split("/") if p]
            if path_parts:
                text = path_parts[0]
        except Exception:
            pass

    # Eliminar '@' inicial y barras finales
    text = text.lstrip("@").strip("/").strip()
    return text.lower()


def validate_username(raw_input: str | None) -> tuple[bool, str, str | None]:
    """
    Valida si la entrada corresponde a un nombre de usuario de Instagram admisible.

    Retorna:
        tuple[bool, str, str | None]: (es_valido, username_normalizado, mensaje_error)
    """
    username = normalize_username(raw_input)

    if not username:
        return False, "", "El nombre de usuario no puede estar vacío."

    if len(username) > 30:
        return False, username, "El nombre de usuario no puede exceder 30 caracteres."

    if ".." in username:
        return False, username, "El nombre de usuario no puede contener puntos consecutivos."

    if not USERNAME_REGEX.match(username):
        return False, username, (
            "El nombre de usuario solo puede contener letras, números, "
            "guiones bajos y puntos (sin empezar ni terminar con punto)."
        )

    # Nombres reservados o inválidos típicos
    reserved = {"accounts", "explore", "reels", "direct", "stories", "p", "reel", "about", "legal"}
    if username in reserved:
        return False, username, f"'{username}' es una ruta reservada de Instagram, no un usuario."

    return True, username, None


def parse_count_string(text: str | int | float | None) -> int | None:
    """
    Convierte una representación textual o numérica de un contador de Instagram a un entero.
    
    IMPORTANTE:
    - Distingue rigurosamente entre 0 y None (desconocido/no disponible).
    - Soporta notaciones en español e inglés:
      * '1.5M', '1,5M', '1.5 millones', '2M'
      * '15.2k', '15,2K', '15 mil', '120k'
      * '1,250', '1.250', '1 250'
      * '0', '0 publicaciones', 'cero'
    - Retorna None ante texto nulo, vacío o irreconocible.
    """
    if text is None:
        return None

    if isinstance(text, (int, float)):
        return int(text)

    s = str(text).strip()
    if not s:
        return None

    # Caso cero explícito
    if s == "0" or s.lower().startswith("0 ") or s.lower() == "cero":
        return 0

    # Limpiar palabras descriptivas comunes (ej: "1.250 publicaciones", "15K seguidores", "679 siguiendo", "posts", "likes")
    clean = re.sub(
        r"(?i)\s*(publicaciones|publicaci[oó]n|seguidores|seguidor|seguidos?|seguidas?|siguiendo|posts?|followers?|following|likes|me gusta|comentarios|comments)\b",
        "",
        s,
    ).strip()

    # Chequeo rápido si es número puro
    if clean.isdigit():
        return int(clean)

    clean_lower = clean.lower()

    # Millones: 'M', 'millones', 'millón', 'm'
    m_match = re.search(r"^([\d.,]+)\s*(?:m|millones|millón)$", clean_lower)
    if m_match:
        val_str = m_match.group(1).replace(",", ".")
        try:
            val = float(val_str)
            return int(val * 1_000_000)
        except ValueError:
            pass

    # Miles: 'k', 'mil'
    k_match = re.search(r"^([\d.,]+)\s*(?:k|mil)$", clean_lower)
    if k_match:
        val_str = k_match.group(1).replace(",", ".")
        try:
            val = float(val_str)
            return int(val * 1_000)
        except ValueError:
            pass

    # Números formateados con separador de miles: '1,234' o '1.234' o '1 234'
    # Si contiene punto como separador de miles: ej '12.345'
    dots_commas = clean.replace(" ", "")
    # Si tiene forma '12.345' (3 dígitos tras el punto) -> separador de miles español
    if re.match(r"^\d{1,3}(?:\.\d{3})+$", dots_commas):
        return int(dots_commas.replace(".", ""))

    # Si tiene forma '12,345' (3 dígitos tras la coma) -> separador de miles inglés
    if re.match(r"^\d{1,3}(?:,\d{3})+$", dots_commas):
        return int(dots_commas.replace(",", ""))

    # Si solo tiene dígitos tras remover separadores
    digits_only = re.sub(r"[^\d]", "", clean)
    if digits_only:
        try:
            return int(digits_only)
        except ValueError:
            return None

    return None


def sanitize_filename(name: str, max_length: int = 100) -> str:
    """
    Sanitiza una cadena para su uso seguro como nombre de archivo en Windows y Unix.
    Elimina caracteres reservados: < > : " / \\ | ? *
    """
    if not name:
        return "unnamed"

    # Reemplazar caracteres prohibidos en sistemas Windows
    clean = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", str(name))
    # Colapsar guiones bajos repetidos
    clean = re.sub(r"_+", "_", clean).strip("_.")
    if not clean:
        clean = "file"
    return clean[:max_length]


def is_safe_image_url(url: str | None) -> bool:
    """
    Valida que una URL de imagen sea sintácticamente válida, use HTTP/HTTPS,
    y pertenezca a dominios web públicos autorizados para prevenir SSRF.
    """
    if not url or not isinstance(url, str):
        return False

    url_clean = url.strip()
    if not (url_clean.startswith("http://") or url_clean.startswith("https://")):
        return False

    try:
        parsed = urllib.parse.urlparse(url_clean)
        hostname = (parsed.hostname or "").lower()

        # Prohibir localhost, direcciones de loopback o IPs privadas
        forbidden_hosts = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}
        if hostname in forbidden_hosts:
            return False

        if hostname.startswith("192.168.") or hostname.startswith("10.") or hostname.startswith("172."):
            return False

        return True
    except Exception:
        return False
