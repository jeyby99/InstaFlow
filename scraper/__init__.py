"""
InstaFlow Scraper Module
========================
Componentes de automatización de navegador, extracción de perfiles,
publicaciones, imágenes y gestión de trabajos en segundo plano.
"""

from .exceptions import (
    InstaFlowError,
    InvalidUsernameError,
    ProfileNotFoundError,
    PrivateProfileError,
    SessionExpiredError,
    ScrapingTimeoutError,
    RateLimitDetectedError,
    JobCancelledError,
    ImageDownloadError,
)

__all__ = [
    "InstaFlowError",
    "InvalidUsernameError",
    "ProfileNotFoundError",
    "PrivateProfileError",
    "SessionExpiredError",
    "ScrapingTimeoutError",
    "RateLimitDetectedError",
    "JobCancelledError",
    "ImageDownloadError",
]
