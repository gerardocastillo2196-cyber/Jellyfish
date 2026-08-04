"""core/event_bus.py — Motor de Eventos Global (EventBus) de Jellyfish OS.

Implementa un patrón Publish-Subscribe (PubSub) síncrono y asíncrono thread-safe para
desacoplar la lógica de orquestación (Agent Swarm) del renderizado visual y monitoreo.
"""

import time
import logging
import threading
import asyncio
import inspect
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
    
    # Eventos de Debate & Consenso (Agent Swarm Architecture v6.9.15)
    CODE_SUBMITTED = "CODE_SUBMITTED"
    CODE_REJECTED = "CODE_REJECTED"
    CODE_APPROVED = "CODE_APPROVED"
    DEBATE_CYCLE_STARTED = "DEBATE_CYCLE_STARTED"
    CIRCUIT_BREAKER_TRIPPED = "CIRCUIT_BREAKER_TRIPPED"
    
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
    """Bus de eventos global thread-safe y async-safe para orquestación reactiva del enjambre."""

    def __init__(self):
        self._listeners: Dict[str, List[Callable[[Event], Any]]] = {}
        self._global_listeners: List[Callable[[Event], Any]] = []
        self._async_queues: Dict[str, List[asyncio.Queue]] = {}
        self._lock = threading.Lock()

    def subscribe(self, event_type: str, handler: Callable[[Event], Any]) -> None:
        """Registra un suscriptor (síncrono o coroutine) para un tipo de evento."""
        with self._lock:
            if event_type not in self._listeners:
                self._listeners[event_type] = []
            if handler not in self._listeners[event_type]:
                self._listeners[event_type].append(handler)

    def subscribe_all(self, handler: Callable[[Event], Any]) -> None:
        """Registra un suscriptor global que escucha TODOS los eventos."""
        with self._lock:
            if handler not in self._global_listeners:
                self._global_listeners.append(handler)

    def subscribe_queue(self, event_type: str) -> asyncio.Queue:
        """Crea y retorna una cola asíncrona (asyncio.Queue) para consumir eventos reactivamente."""
        with self._lock:
            if event_type not in self._async_queues:
                self._async_queues[event_type] = []
            q = asyncio.Queue()
            self._async_queues[event_type].append(q)
            return q

    def unsubscribe_queue(self, event_type: str, q: asyncio.Queue) -> None:
        """Remueve una cola asíncrona de suscriptores."""
        with self._lock:
            if event_type in self._async_queues and q in self._async_queues[event_type]:
                self._async_queues[event_type].remove(q)

    def unsubscribe(self, event_type: str, handler: Callable[[Event], Any]) -> None:
        """Remueve un suscriptor de un tipo de evento."""
        with self._lock:
            if event_type in self._listeners and handler in self._listeners[event_type]:
                self._listeners[event_type].remove(handler)
            if handler in self._global_listeners:
                self._global_listeners.remove(handler)

    def publish(self, event_type: str, payload: Dict[str, Any] = None, **kwargs) -> Event:
        """Publica un evento a todos sus suscriptores registrados (llamable de modo síncrono)."""
        if payload is None:
            payload = {}
        if kwargs:
            payload.update(kwargs)

        event = Event(type=event_type, payload=payload)

        with self._lock:
            specific_handlers = list(self._listeners.get(event_type, []))
            global_handlers = list(self._global_listeners)
            queues = list(self._async_queues.get(event_type, []))

        for handler in specific_handlers + global_handlers:
            try:
                if inspect.iscoroutinefunction(handler):
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(handler(event))
                    except RuntimeError:
                        asyncio.run(handler(event))
                else:
                    handler(event)
            except Exception as e:
                logger.error("Error en suscriptor de evento %s: %s", event_type, e, exc_info=True)

        for q in queues:
            try:
                q.put_nowait(event)
            except Exception as e:
                logger.error("Error encolando evento asíncrono en cola para %s: %s", event_type, e)

        return event

    async def apublish(self, event_type: str, payload: Dict[str, Any] = None, **kwargs) -> Event:
        """Publica un evento de forma asíncrona esperando la resolución de corrutinas."""
        if payload is None:
            payload = {}
        if kwargs:
            payload.update(kwargs)

        event = Event(type=event_type, payload=payload)

        with self._lock:
            specific_handlers = list(self._listeners.get(event_type, []))
            global_handlers = list(self._global_listeners)
            queues = list(self._async_queues.get(event_type, []))

        for handler in specific_handlers + global_handlers:
            try:
                if inspect.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as e:
                logger.error("Error en suscriptor asíncrono para %s: %s", event_type, e, exc_info=True)

        for q in queues:
            await q.put(event)

        return event

    def clear(self) -> None:
        """Limpia todos los suscriptores y colas registradas."""
        with self._lock:
            self._listeners.clear()
            self._global_listeners.clear()
            self._async_queues.clear()


# Instancia global singleton del EventBus
event_bus = EventBus()
