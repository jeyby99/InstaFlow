"""
Tests for scraper.profile_extractor
===================================
Pruebas de extracción de perfiles con simulación de HTML, etiquetas Open Graph,
metadatos JSON-LD, cuentas privadas y perfiles no existentes.
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scraper.profile_extractor import ProfileExtractor
from scraper.exceptions import ProfileNotFoundError


class TestProfileExtractor:
    """Pruebas del extractor de perfiles sin depender de la red."""

    def test_extract_from_open_graph_spanish(self):
        html = """
        <html>
        <head>
          <title>Leo Messi (@leomessi) • Instagram</title>
          <meta property="og:title" content="Leo Messi (@leomessi) • Fotos y vídeos de Instagram" />
          <meta property="og:description" content="500M seguidores, 300 seguidos, 1.150 publicaciones - Bienvenidos a la cuenta oficial de Leo Messi" />
          <meta property="og:image" content="https://scontent.cdninstagram.com/avatar_messi.jpg" />
        </head>
        <body>
          <header>
            <span class="verified-icon" aria-label="Verificado"></span>
          </header>
        </body>
        </html>
        """
        extractor = ProfileExtractor(driver=None)
        data = extractor.extract_profile_data("leomessi", html_content=html)

        assert data["username"] == "leomessi"
        assert data["full_name"] == "Leo Messi"
        assert data["followers_count"] == 500_000_000
        assert data["following_count"] == 300
        assert data["posts_count"] == 1150
        assert data["profile_image_url"] == "https://scontent.cdninstagram.com/avatar_messi.jpg"
        assert "Bienvenidos a la cuenta oficial" in (data["biography"] or "")
        assert data["is_verified"] is True
        assert data["is_private"] is False
        assert data["status"] == "complete"

    def test_extract_from_open_graph_spanish_siguiendo(self):
        html = """
        <html>
        <head>
          <title>el rubius WTF (@elrubiuswtf) • Instagram</title>
          <meta property="og:title" content="el rubius WTF (@elrubiuswtf) • Fotos y vídeos de Instagram" />
          <meta property="og:description" content="17M seguidores, 679 siguiendo, 672 publicaciones - Ver fotos y vídeos de Instagram de el rubius WTF" />
          <meta property="og:image" content="https://scontent.cdninstagram.com/avatar_rubius.jpg" />
        </head>
        <body></body>
        </html>
        """
        extractor = ProfileExtractor(driver=None)
        data = extractor.extract_profile_data("elrubiuswtf", html_content=html)

        assert data["username"] == "elrubiuswtf"
        assert data["followers_count"] == 17_000_000
        assert data["following_count"] == 679
        assert data["posts_count"] == 672

    def test_extract_from_open_graph_english(self):
        html = """
        <html>
        <head>
          <title>NASA (@nasa) • Instagram photos and videos</title>
          <meta property="og:title" content="NASA (@nasa) • Instagram photos and videos" />
          <meta property="og:description" content="97.5M Followers, 75 Following, 4,500 Posts - Exploring the universe and our home planet." />
          <meta property="og:image" content="https://scontent.cdninstagram.com/avatar_nasa.jpg" />
        </head>
        <body></body>
        </html>
        """
        extractor = ProfileExtractor(driver=None)
        data = extractor.extract_profile_data("nasa", html_content=html)

        assert data["username"] == "nasa"
        assert data["full_name"] == "NASA"
        assert data["followers_count"] == 97_500_000
        assert data["following_count"] == 75
        assert data["posts_count"] == 4500
        assert "Exploring the universe" in (data["biography"] or "")

    def test_extract_from_json_ld(self):
        html = """
        <html>
        <head>
          <script type="application/ld+json">
          {
            "@context": "https://schema.org",
            "@type": "Person",
            "name": "Jane Doe",
            "description": "Fotógrafa y creadora digital 📷✨",
            "image": "https://cdn.example.com/jane.jpg"
          }
          </script>
        </head>
        <body></body>
        </html>
        """
        extractor = ProfileExtractor(driver=None)
        data = extractor.extract_profile_data("janedoe", html_content=html)

        assert data["full_name"] == "Jane Doe"
        assert "Fotógrafa y creadora digital" in data["biography"]
        assert data["profile_image_url"] == "https://cdn.example.com/jane.jpg"

    def test_detect_profile_not_found(self):
        html = """
        <html>
        <head><title>Esta página no está disponible • Instagram</title></head>
        <body>
          <h2>Sorry, this page isn't available.</h2>
          <p>The link you followed may be broken, or the page may have been removed.</p>
        </body>
        </html>
        """
        extractor = ProfileExtractor(driver=None)
        with pytest.raises(ProfileNotFoundError):
            extractor.extract_profile_data("non_existent_user_9999", html_content=html)

    def test_detect_private_account(self):
        html = """
        <html>
        <head>
          <meta property="og:title" content="Cuenta Privada (@private_user)" />
          <meta property="og:description" content="150 seguidores, 120 seguidos, 45 publicaciones" />
        </head>
        <body>
          <div>Esta cuenta es privada</div>
          <div>Sigue a esta cuenta para ver sus fotos y vídeos.</div>
        </body>
        </html>
        """
        extractor = ProfileExtractor(driver=None)
        data = extractor.extract_profile_data("private_user", html_content=html)

        assert data["is_private"] is True
        assert data["followers_count"] == 150
        assert data["posts_count"] == 45

    def test_empty_biography_handling(self):
        html = """
        <html>
        <head>
          <meta property="og:title" content="Sin Bio (@nobio)" />
          <meta property="og:description" content="10 seguidores, 5 seguidos, 0 publicaciones" />
        </head>
        <body></body>
        </html>
        """
        extractor = ProfileExtractor(driver=None)
        data = extractor.extract_profile_data("nobio", html_content=html)

        assert data["biography"] is None
        assert data["posts_count"] == 0
