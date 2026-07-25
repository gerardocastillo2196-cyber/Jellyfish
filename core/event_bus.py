"""core/event_bus.py — Motor de Eventos Global (EventBus) de Jellyfish OS.

Implementa un patrón Publish-Subscribe (PubSub) thread-safe para desacoplar
la lógica de orquestación técnica del renderizado visual (Rich / TUI / WebSockets).
"""

import time
import logging
import threading
from dataclasses import dataclass, field
from typing import Callable, Any, Dict, List

logger = logging.getLogger("jellyfish.event_bus")


class EventType:
    """Taxonomía de eventos del sistema Jellyfish OS."""
    SYSTEM_BOOT = "SYSTEM_BOOT"
    SYSTEM_SHUTDOWN = "SYSTEM_SHUTDOWN"
    
    AGENT_STATUS_CHANGE = "AGENT_STATUS_CHANGE"
    AGENT_THINKING = "AGENT_THINKING"
    AGENT_RESPONSE = "AGENT_RESPONSE"
    
    PHASE_STARTED = "PHASE_STARTED"
    PHASE_COMPLETED = "PHASE_COMPLETED"
    
    TASK_STARTED = "TASK_STARTED"
    TASK_PROGRESS = "TASK_PROGRESS"
    TASK_COMPLETED = "TASK_COMPLETED"
    TASK_FAILED = "TASK_FAILED"
    TASK_BLOCKED = "TASK_BLOCKED"
    
    SENTINEL_ALERT = "SENTINEL_ALERT"
    SENTINEL_RESOLVED = "SENTINEL_RESOLVED"
    
    ENVIRONMENT_WARNING = "ENVIRONMENT_WARNING"
    ENVIRONMENT_BLOCKING = "ENVIRONMENT_BLOCKING"
    
    ERROR_CRITICAL = "ERROR_CRITICAL"
    LOG_MESSAGE = "LOG_MESSAGE"


@dataclass
class Event:
    """Representa un evento emitido en el sistema."""
    type: str
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Retorna el evento como un diccionario estructurado (JSON serializable)."""
        return {
            "type": self.type,
            "payload": self.payload,
            "timestamp": self.timestamp,
        }


class EventBus:
    """Bus de eventos global thread-safe para orquestación reactiva."""

    def __init__(self):
        self._listeners: Dict[str, List[Callable[[Event], None]]] = {}
        self._global_listeners: List[Callable[[Event], None]] = []
        self._lock = threading.Lock()

    def subscribe(self, event_type: str, handler: Callable[[Event], None]) -> None:
        """Registra un suscriptor para un tipo de evento específico."""
        with self._lock:
            if event_type not in self._listeners:
                self._listeners[event_type] = []
            if handler not in self._listeners[event_type]:
                self._listeners[event_type].append(handler)

    def subscribe_all(self, handler: Callable[[Event], None]) -> None:
        """Registra un suscriptor global que escucha TODOS los eventos."""
        with self._lock:
            if handler not in self._global_listeners:
                self._global_listeners.append(handler)

    def unsubscribe(self, event_type: str, handler: Callable[[Event], None]) -> None:
        """Remueve un suscriptor de un tipo de evento."""
        with self._lock:
            if event_type in self._listeners and handler in self._listeners[event_type]:
                self._listeners[event_type].remove(handler)
            if handler in self._global_listeners:
                self._global_listeners.remove(handler)

    def publish(self, event_type: str, payload: Dict[str, Any] = None, **kwargs) -> Event:
        """Publica un evento a todos sus suscriptores registrados."""
        if payload is None:
            payload = {}
        if kwargs:
            payload.update(kwargs)

        event = Event(type=event_type, payload=payload)

        # Copiar handlers bajo el lock para evitar deadlock durante ejecuciones
        with self._lock:
            specific_handlers = list(self._listeners.get(event_type, []))
            global_handlers = list(self._global_listeners)

        # Ejecutar handlers específicos
        for handler in specific_handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error("Error en suscriptor de evento %s: %s", event_type, e, exc_info=True)

        # Ejecutar handlers globales
        for handler in global_handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error("Error en suscriptor global de evento %s: %s", event_type, e, exc_info=True)

        return event

    def clear(self) -> None:
        """Limpia todos los suscriptores registrados."""
        with self._lock:
            self._listeners.clear()
            self._global_listeners.clear()


# Instancia global singleton del EventBus
event_bus = EventBus()
