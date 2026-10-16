"""
InstaFlow Background Job Manager
================================
Gestión asíncrona de trabajos de scraping mediante hilos en segundo plano (Threading).
Proporciona identificadores únicos (UUID), seguimiento granular de 16 etapas,
captura de registros en tiempo real y cancelación segura sin bloquear Flask.
"""

from datetime import datetime, timezone
import logging
import threading
import uuid
from typing import Callable, Any

import config
from .exceptions import JobCancelledError

logger = logging.getLogger("instaflow.job_manager")


class Job:
    """Representa el estado, progreso, etapas y resultados de una ejecución."""

    def __init__(self, job_id: str, username: str, options: dict | None = None):
        self.job_id = job_id
        self.username = username
        self.options = options or {}
        self.status = "queued"  # queued, running, completed, partial, failed, cancelled
        self.progress_percent = 0
        self.current_stage = "Inicializando"
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.started_at: str | None = None
        self.finished_at: str | None = None
        self.duration_sec: float | None = None

        # Historial de etapas detalladas
        self.stages: list[dict] = []
        # Registros de eventos para el panel de actividad
        self.logs: list[dict] = []

        # Resultados finales
        self.profile: dict | None = None
        self.posts: list[dict] = []
        self.summary: dict = {
            "posts_requested": self.options.get("max_posts", config.DEFAULT_POSTS_LIMIT),
            "posts_collected": 0,
            "images_downloaded": 0,
            "images_failed": 0,
            "screenshot_path": None,
        }
        self.error_message: str | None = None

        # Señal de cancelación segura
        self._cancel_event = threading.Event()

    def is_cancelled(self) -> bool:
        """Comprueba si el usuario ha solicitado cancelar esta ejecución."""
        return self._cancel_event.is_set()

    def request_cancel(self) -> None:
        """Emite la señal de cancelación cooperativa."""
        self._cancel_event.set()
        self.add_log("warning", "Solicitud de cancelación recibida. Finalizando de forma segura...")

    def add_log(self, level: str, message: str, stage: str | None = None) -> None:
        """Añade una entrada cronológica al panel de actividad."""
        entry = {
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "level": level,  # 'info', 'success', 'warning', 'error'
            "message": message,
            "stage": stage or self.current_stage,
        }
        self.logs.append(entry)
        logger.info("[Job %s] [%s] %s", self.job_id[:8], level.upper(), message)

    def start_stage(self, stage_number: int, name: str, progress_hint: int | None = None) -> dict:
        """Inicia una nueva etapa del proceso de extracción."""
        if self.is_cancelled():
            raise JobCancelledError("Trabajo cancelado.")

        if progress_hint is not None:
            self.progress_percent = min(100, max(0, progress_hint))

        self.current_stage = f"Etapa {stage_number}: {name}"
        stage_entry = {
            "stage_number": stage_number,
            "name": name,
            "status": "running",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "finished_at": None,
            "duration_sec": None,
            "message": "En progreso...",
        }
        self.stages.append(stage_entry)
        self.add_log("info", f"Iniciando: {name}", stage=name)
        return stage_entry

    def complete_stage(self, stage_number: int, status: str = "success", message: str = "Completada") -> None:
        """Marca una etapa como finalizada registrando su duración."""
        for st in reversed(self.stages):
            if st["stage_number"] == stage_number:
                st["status"] = status
                st["message"] = message
                st["finished_at"] = datetime.now(timezone.utc).isoformat()
                try:
                    start_dt = datetime.fromisoformat(st["started_at"])
                    end_dt = datetime.fromisoformat(st["finished_at"])
                    st["duration_sec"] = round((end_dt - start_dt).total_seconds(), 2)
                except Exception:
                    st["duration_sec"] = 0.0

                log_level = "success" if status == "success" else ("warning" if status == "warning" else "error")
                self.add_log(log_level, f"{st['name']}: {message} ({st['duration_sec']}s)", stage=st["name"])
                break

    def to_dict(self) -> dict:
        """Genera el diccionario de estado para la API."""
        return {
            "job_id": self.job_id,
            "username": self.username,
            "status": self.status,
            "progress_percent": self.progress_percent,
            "current_stage": self.current_stage,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_sec": self.duration_sec,
            "stages": self.stages,
            "logs": self.logs[-50:],  # Últimos 50 mensajes de registro
            "summary": self.summary,
            "profile": self.profile,
            "posts_count": len(self.posts),
            "posts": self.posts,
            "error_message": self.error_message,
        }


class JobManager:
    """Administrador centralizado de trabajos concurrentes y cola de ejecución."""

    def __init__(self):
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def create_job(self, username: str, options: dict | None = None) -> Job:
        """Crea y registra un nuevo trabajo con un UUID v4 único."""
        with self._lock:
            # Control de capacidad de historial
            if len(self._jobs) >= config.JOB_HISTORY_LIMIT:
                # Eliminar el más antiguo
                oldest_id = next(iter(self._jobs))
                del self._jobs[oldest_id]

            job_id = str(uuid.uuid4())
            job = Job(job_id=job_id, username=username, options=options)
            self._jobs[job_id] = job
            return job

    def get_job(self, job_id: str) -> Job | None:
        """Obtiene una referencia al trabajo según su identificador."""
        with self._lock:
            return self._jobs.get(job_id)

    def cancel_job(self, job_id: str) -> bool:
        """Solicita la cancelación de un trabajo."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job and job.status in ("queued", "running"):
                job.request_cancel()
                return True
            return False

    def get_active_jobs_count(self) -> int:
        """Retorna la cantidad de trabajos actualmente en ejecución."""
        with self._lock:
            return sum(1 for j in self._jobs.values() if j.status in ("queued", "running"))

    def run_in_background(self, job: Job, target_func: Callable[[Job], Any]) -> threading.Thread:
        """Lanza la ejecución del trabajo en un hilo independiente (daemon)."""
        thread = threading.Thread(
            target=target_func,
            args=(job,),
            name=f"InstaFlow-Worker-{job.job_id[:8]}",
            daemon=True,
        )
        thread.start()
        return thread
