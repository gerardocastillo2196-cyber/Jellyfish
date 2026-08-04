"""core.state_proxy — Vista controlada del estado para plugins y skills.

REGLA DE SEGURIDAD: Los plugins y skills NUNCA reciben JellyfishState
directamente. Solo acceden a métodos explícitamente expuestos aquí.

Esto previene que un plugin mal codificado o un hook alucinado mute
state.active_agent, state.history u otros campos críticos que
romperían la orquestación Scrum.

Referencia de acoplamiento:
    - core/plugin_manager.py → crea StateProxy y lo pasa a plugins
    - core/orchestration/task_runner.py → pasa StateProxy como contexto a hooks
    - plugins/* → reciben StateProxy en initialize()
"""

import os
import logging
import threading
import asyncio
import aiofiles
from typing import Optional

logger = logging.getLogger("jellyfish.state_proxy")


class FileLockManager:
    """Gestor de cerrojos de archivo para concurrencia segura en archivos .md y repositorio Git."""
    _locks: dict[str, asyncio.Lock] = {}
    _sync_locks: dict[str, threading.Lock] = {}
    _global_lock = threading.Lock()

    @classmethod
    def get_lock(cls, filepath: str) -> asyncio.Lock:
        real_path = os.path.realpath(filepath)
        with cls._global_lock:
            if real_path not in cls._locks:
                cls._locks[real_path] = asyncio.Lock()
            return cls._locks[real_path]

    @classmethod
    def get_sync_lock(cls, filepath: str) -> threading.Lock:
        real_path = os.path.realpath(filepath)
        with cls._global_lock:
            if real_path not in cls._sync_locks:
                cls._sync_locks[real_path] = threading.Lock()
            return cls._sync_locks[real_path]


class StateProxy:
    """Vista de solo lectura del estado de Jellyfish para plugins y skills.

    Expone métodos específicos de consulta y mutaciones controladas con locks concurrentes.
    """

    def __init__(self, state):
        self._state = state

    # ── Lecturas seguras ──────────────────────────────────────

    def get_active_project(self) -> str:
        """Ruta del proyecto activo (solo lectura)."""
        return getattr(self._state, "active_project", "")

    def get_active_agent(self) -> str:
        """Nombre del agente activo (solo lectura)."""
        return getattr(self._state, "active_agent", "default")

    def get_active_agency(self) -> str:
        """Nombre de la agencia activa (solo lectura)."""
        return getattr(self._state, "active_agency", "default")

    def get_agency_catalog(self) -> dict:
        """Catálogo de agencias y sus agentes (copia defensiva)."""
        catalog = getattr(self._state, "agency_catalog", {})
        return {k: list(v) for k, v in catalog.items()}

    def get_provider_info(self) -> dict:
        """Información del proveedor LLM activo (sin API keys)."""
        return {
            "provider": getattr(self._state, "provider", "unknown"),
            "model": getattr(self._state, "model", "unknown"),
        }

    def get_project_methodology(self) -> str:
        """Metodología del proyecto activo (scrum/cascada)."""
        return getattr(self._state, "project_methodology", "scrum")

    def read_project_file(self, filename: str) -> str:
        """Lee un archivo del proyecto activo de forma segura con sync locks."""
        project = self.get_active_project()
        if not project:
            return ""

        filename_clean = filename.replace("`", "").strip()
        filepath = os.path.join(project, filename_clean)
        real_path = os.path.realpath(filepath)
        if not real_path.startswith(os.path.realpath(project)):
            logger.warning("Path traversal bloqueado: %s", filepath)
            return ""

        lock = FileLockManager.get_sync_lock(real_path)
        with lock:
            try:
                with open(real_path, "r", encoding="utf-8", errors="ignore") as f:
                    return f.read()
            except (OSError, IOError):
                return ""

    async def aread_project_file(self, filename: str) -> str:
        """Lee un archivo de forma asinscróna no bloqueante con aiofiles y asyncio.Lock."""
        project = self.get_active_project()
        if not project:
            return ""

        filename_clean = filename.replace("`", "").strip()
        filepath = os.path.join(project, filename_clean)
        real_path = os.path.realpath(filepath)
        if not real_path.startswith(os.path.realpath(project)):
            logger.warning("Path traversal bloqueado: %s", filepath)
            return ""

        lock = FileLockManager.get_lock(real_path)
        async with lock:
            try:
                async with aiofiles.open(real_path, "r", encoding="utf-8", errors="ignore") as f:
                    return await f.read()
            except (OSError, IOError):
                return ""

    def get_blackboard_variable(self, key: str, default=None):
        """Obtiene una variable del Blackboard (registro central)."""
        if hasattr(self._state, "blackboard"):
            return self._state.blackboard.get(key, default)
        return default

    async def aget_blackboard_variable(self, key: str, default=None):
        """Obtiene una variable del Blackboard de forma asíncrona."""
        if hasattr(self._state, "blackboard") and hasattr(self._state.blackboard, "aget"):
            return await self._state.blackboard.aget(key, default)
        return self.get_blackboard_variable(key, default)

    def set_blackboard_variable(self, key: str, value) -> None:
        """Registra una variable en el Blackboard de forma segura."""
        if hasattr(self._state, "blackboard"):
            self._state.blackboard.set(key, value)

    async def aset_blackboard_variable(self, key: str, value) -> None:
        """Registra una variable en el Blackboard de forma asíncrona."""
        if hasattr(self._state, "blackboard") and hasattr(self._state.blackboard, "aset"):
            await self._state.blackboard.aset(key, value)
        else:
            self.set_blackboard_variable(key, value)

    # ── Mutaciones controladas ────────────────────────────────

    def update_board_status(self, task_id: str, new_status: str) -> bool:
        """Actualiza el estado de una tarea con protección de cerrojos síncronos."""
        allowed_statuses = {"TODO", "IN_PROGRESS", "DONE", "FAILED", "BLOCKED", "✅", "❌", "🔄", "BLOCKED ⛔"}
        if new_status not in allowed_statuses:
            logger.warning("Estado no permitido para board: %s", new_status)
            return False

        project = self.get_active_project()
        if not project:
            return False

        board_path = os.path.realpath(os.path.join(project, "SPRINT_BOARD.md"))
        lock = FileLockManager.get_sync_lock(board_path)
        with lock:
            try:
                content = self.read_project_file("SPRINT_BOARD.md")
                if not content or task_id not in content:
                    return False

                lines = content.splitlines()
                updated_lines = []
                for line in lines:
                    if task_id in line and "|" in line:
                        if new_status in ("DONE", "✅"):
                            line = line.rstrip() + " ✅"
                        elif new_status in ("FAILED", "❌"):
                            line = line.rstrip() + " ❌"
                        elif new_status in ("BLOCKED", "BLOCKED ⛔"):
                            line = line.rstrip() + " ⛔ BLOCKED (Circuit Breaker)"
                    updated_lines.append(line)

                with open(board_path, "w", encoding="utf-8") as f:
                    f.write("\n".join(updated_lines))
                return True

            except Exception as e:
                logger.error("Error actualizando board: %s", e)
                return False

    async def aupdate_board_status(self, task_id: str, new_status: str) -> bool:
        """Actualiza el estado de una tarea asincrónamente con aiofiles."""
        allowed_statuses = {"TODO", "IN_PROGRESS", "DONE", "FAILED", "BLOCKED", "✅", "❌", "🔄", "BLOCKED ⛔"}
        if new_status not in allowed_statuses:
            logger.warning("Estado no permitido para board: %s", new_status)
            return False

        project = self.get_active_project()
        if not project:
            return False

        board_path = os.path.realpath(os.path.join(project, "SPRINT_BOARD.md"))
        lock = FileLockManager.get_lock(board_path)
        async with lock:
            try:
                async with aiofiles.open(board_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = await f.read()
                if not content or task_id not in content:
                    return False

                lines = content.splitlines()
                updated_lines = []
                for line in lines:
                    if task_id in line and "|" in line:
                        if new_status in ("DONE", "✅"):
                            line = line.rstrip() + " ✅"
                        elif new_status in ("FAILED", "❌"):
                            line = line.rstrip() + " ❌"
                        elif new_status in ("BLOCKED", "BLOCKED ⛔"):
                            line = line.rstrip() + " ⛔ BLOCKED (Circuit Breaker)"
                    updated_lines.append(line)

                async with aiofiles.open(board_path, "w", encoding="utf-8") as f:
                    await f.write("\n".join(updated_lines))
                return True

            except Exception as e:
                logger.error("Error actualizando board async: %s", e)
                return False

    def append_to_history(self, role: str, content: str) -> None:
        """Añade un mensaje al historial de forma segura.

        Valida el rol y trunca contenido excesivo.
        """
        valid_roles = {"user", "assistant", "system"}
        if role not in valid_roles:
            logger.warning("Rol inválido para historial: %s (permitidos: %s)", role, valid_roles)
            return

        if hasattr(self._state, "history"):
            # Truncar a 5000 chars para evitar inyección masiva
            self._state.history.append({
                "role": role,
                "content": content[:5000],
            })

    def get_context_file_count(self) -> int:
        """Número de archivos en el contexto activo."""
        return len(getattr(self._state, "context_files", set()))

    def get_session_tokens(self) -> int:
        """Tokens consumidos en la sesión activa."""
        return getattr(self._state, "session_tokens", 0)

    def __repr__(self) -> str:
        return (
            f"<StateProxy project={self.get_active_project()!r} "
            f"agent={self.get_active_agent()!r} "
            f"agency={self.get_active_agency()!r}>"
        )
