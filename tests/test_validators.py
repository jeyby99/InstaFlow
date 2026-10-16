"""
Tests for scraper.validators
============================
Pruebas de validación y normalización de usuarios, parseo de contadores,
sanitización de nombres de archivo y protección SSRF.
"""

import pytest
import sys
from pathlib import Path

# Asegurar que el directorio raíz esté en sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scraper.validators import (
    normalize_username,
    validate_username,
    parse_count_string,
    sanitize_filename,
    is_safe_image_url,
)


class TestValidators:
    """Conjunto de pruebas para validadores y funciones de normalización."""

    def test_normalize_username_with_at(self):
        assert normalize_username("@usuario_ejemplo") == "usuario_ejemplo"
        assert normalize_username("  @cuenta.oficial  ") == "cuenta.oficial"

    def test_normalize_username_from_url(self):
        url = "https://www.instagram.com/mi_perfil_top/"
        assert normalize_username(url) == "mi_perfil_top"
        url_without_scheme = "instagram.com/nombre.usuario"
        assert normalize_username(url_without_scheme) == "nombre.usuario"

    def test_validate_username_valid(self):
        valid_users = ["instagram", "john_doe", "jane.doe", "user_123", "a.b.c"]
        for u in valid_users:
            is_valid, norm, err = validate_username(u)
            assert is_valid is True, f"Fallo en usuario válido: {u}"
            assert err is None
            assert norm == u

    def test_validate_username_invalid(self):
        invalid_cases = [
            ("", "vacío"),
            ("   ", "espacios"),
            ("user name", "espacio intermedio"),
            ("user@instagram", "carácter arroba intermedio"),
            (".startdot", "inicia con punto"),
            ("enddot.", "termina con punto"),
            ("two..dots", "puntos consecutivos"),
            ("a" * 35, "demasiado largo"),
            ("accounts", "nombre reservado"),
            ("p", "nombre reservado"),
        ]
        for bad_u, reason in invalid_cases:
            is_valid, _, err = validate_username(bad_u)
            assert is_valid is False, f"Debería fallar por {reason}: '{bad_u}'"
            assert err is not None

    def test_parse_count_string_explicit_zero(self):
        # NUNCA sustituir 0 por None
        assert parse_count_string(0) == 0
        assert parse_count_string("0") == 0
        assert parse_count_string("0 publicaciones") == 0
        assert parse_count_string("0 posts") == 0
        assert parse_count_string("cero") == 0

    def test_parse_count_string_unknown_or_empty(self):
        # NUNCA sustituir dato ausente por cero!
        assert parse_count_string(None) is None
        assert parse_count_string("") is None
        assert parse_count_string("   ") is None
        assert parse_count_string("no disponible") is None
        assert parse_count_string("desconocido") is None

    def test_parse_count_string_millions(self):
        assert parse_count_string("1.5M") == 1_500_000
        assert parse_count_string("1,5M") == 1_500_000
        assert parse_count_string("2M seguidores") == 2_000_000
        assert parse_count_string("3.2 millones") == 3_200_000

    def test_parse_count_string_thousands(self):
        assert parse_count_string("15.2k") == 15_200
        assert parse_count_string("15,2K") == 15_200
        assert parse_count_string("120k seguidores") == 120_000
        assert parse_count_string("45 mil publicaciones") == 45_000

    def test_parse_count_string_formatted_numbers(self):
        assert parse_count_string("1,250") == 1250
        assert parse_count_string("1.250") == 1250
        assert parse_count_string("1 250") == 1250
        assert parse_count_string("12345") == 12345

    def test_sanitize_filename(self):
        unsafe = 'archivo:con/barras\\y*caracteres?prohibidos"<'
        sanitized = sanitize_filename(unsafe)
        assert ":" not in sanitized
        assert "/" not in sanitized
        assert "\\" not in sanitized
        assert "*" not in sanitized
        assert "?" not in sanitized
        assert '"' not in sanitized
        assert "<" not in sanitized

    def test_is_safe_image_url(self):
        # URLs legítimas
        assert is_safe_image_url("https://scontent.cdninstagram.com/v/t51/img.jpg") is True
        assert is_safe_image_url("https://instagram.fmad3-1.fna.fbcdn.net/p.jpg") is True

        # URLs inseguras o SSRF
        assert is_safe_image_url(None) is False
        assert is_safe_image_url("file:///etc/passwd") is False
        assert is_safe_image_url("http://localhost:5000/secret") is False
        assert is_safe_image_url("http://127.0.0.1/admin") is False
        assert is_safe_image_url("http://192.168.1.1/router") is False
