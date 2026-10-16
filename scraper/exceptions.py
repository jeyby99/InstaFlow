"""
InstaFlow Exceptions
====================
Excepciones personalizadas para el flujo de scraping y validación.
"""


class InstaFlowError(Exception):
    """Excepción base para todos los errores de InstaFlow."""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class InvalidUsernameError(InstaFlowError):
    """Lanzada cuando el nombre de usuario de Instagram no cumple el formato válido."""
    pass


class ProfileNotFoundError(InstaFlowError):
    """Lanzada cuando Instagram indica que la página del perfil no existe."""
    pass


class PrivateProfileError(InstaFlowError):
    """Lanzada cuando el perfil es privado y la sesión actual no tiene permiso de acceso."""
    pass


class SessionExpiredError(InstaFlowError):
    """Lanzada cuando la sesión requerida ha expirado o Instagram solicita inicio de sesión obligatorio."""
    pass


class ScrapingTimeoutError(InstaFlowError):
    """Lanzada cuando una operación de red o carga de página excede el tiempo límite."""
    pass


class RateLimitDetectedError(InstaFlowError):
    """Lanzada cuando se detectan límites temporales impuestos por la plataforma."""
    pass


class JobCancelledError(InstaFlowError):
    """Lanzada cuando el usuario cancela de forma segura el trabajo en curso."""
    pass


class ImageDownloadError(InstaFlowError):
    """Lanzada ante errores irrecuperables en la descarga o validación de una imagen."""
    pass
