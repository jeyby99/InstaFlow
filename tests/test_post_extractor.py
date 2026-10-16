"""
Tests for scraper.post_extractor
================================
Pruebas de extracción de publicaciones, deduplicación de posts, clasificación
de tipo de contenido (foto, carrusel, reel) y selección de miniatura de mayor resolución.
"""

import pytest
import sys
from bs4 import BeautifulSoup
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scraper.post_extractor import PostExtractor


class TestPostExtractor:
    """Pruebas del extractor de publicaciones en cuadrícula."""

    def test_parse_single_photo_post(self):
        html = """
        <a href="/p/C123abcXYZ/">
          <div>
            <img src="https://cdn.example.com/thumb_small.jpg"
                 srcset="https://cdn.example.com/150.jpg 150w, https://cdn.example.com/640.jpg 640w, https://cdn.example.com/320.jpg 320w"
                 alt="Foto en la playa al atardecer 🌅" />
          </div>
        </a>
        """
        soup = BeautifulSoup(html, "html.parser")
        extractor = PostExtractor(driver=None)
        post = extractor.parse_post_element(
            soup=soup,
            url="https://www.instagram.com/p/C123abcXYZ/",
            shortcode="C123abcXYZ",
            media_type_hint="photo",
        )

        assert post["shortcode"] == "C123abcXYZ"
        assert post["media_type"] == "photo"
        assert post["thumbnail_url"] == "https://cdn.example.com/640.jpg"
        assert post["caption"] == "Foto en la playa al atardecer 🌅"
        assert post["download_status"] == "pending"

    def test_parse_carousel_post(self):
        html = """
        <a href="/p/Carousel123/">
          <div>
            <img src="https://cdn.example.com/carousel_cover.jpg" alt="Recopilatorio de viaje" />
            <svg aria-label="Carrusel" role="img"></svg>
          </div>
        </a>
        """
        soup = BeautifulSoup(html, "html.parser")
        extractor = PostExtractor(driver=None)
        post = extractor.parse_post_element(
            soup=soup,
            url="https://www.instagram.com/p/Carousel123/",
            shortcode="Carousel123",
            media_type_hint="photo",
        )

        assert post["shortcode"] == "Carousel123"
        assert post["media_type"] == "carousel"
        assert post["thumbnail_url"] == "https://cdn.example.com/carousel_cover.jpg"

    def test_parse_reel_post(self):
        html = """
        <a href="/reel/Reel789xyz/">
          <div>
            <img src="https://cdn.example.com/reel_cover.jpg" alt="Tutorial rápido" />
            <svg aria-label="Clip" role="img"></svg>
          </div>
        </a>
        """
        soup = BeautifulSoup(html, "html.parser")
        extractor = PostExtractor(driver=None)
        post = extractor.parse_post_element(
            soup=soup,
            url="https://www.instagram.com/reel/Reel789xyz/",
            shortcode="Reel789xyz",
            media_type_hint="reel",
        )

        assert post["shortcode"] == "Reel789xyz"
        assert post["media_type"] == "reel"

    def test_extract_best_from_srcset(self):
        extractor = PostExtractor(driver=None)
        srcset = (
            "https://cdn.instagram.com/p150.jpg 150w, "
            "https://cdn.instagram.com/p1080.jpg 1080w, "
            "https://cdn.instagram.com/p640.jpg 640w"
        )
        best = extractor._extract_best_from_srcset(srcset)
        assert best == "https://cdn.instagram.com/p1080.jpg"

    def test_clean_caption_accessibility_prefix(self):
        extractor = PostExtractor(driver=None)
        raw_alt = "Photo by Leo Messi on October 10, 2026. Gran entrenamiento hoy con el equipo."
        cleaned = extractor._clean_caption(raw_alt)
        assert cleaned == "Gran entrenamiento hoy con el equipo."
