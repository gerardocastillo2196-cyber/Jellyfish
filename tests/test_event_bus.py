"""tests/test_event_bus.py — Pruebas unitarias del motor EventBus y suscriptores."""

import os
import sys
import pytest

# Aseguramos que el proyecto esté en el path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core.event_bus import EventBus, EventType, Event, event_bus
from core.ui_subscriber import CLIEventSubscriber, register_cli_subscriber
from core.state import JellyfishState


def test_event_serialization():
    """Verifica que un Event se serialice correctamente a un diccionario estructurado."""
    evt = Event(type=EventType.TASK_STARTED, payload={"task_id": "US-001", "agent_name": "developer"})
    d = evt.to_dict()
    assert d["type"] == EventType.TASK_STARTED
    assert d["payload"]["task_id"] == "US-001"
    assert d["payload"]["agent_name"] == "developer"
    assert "timestamp" in d


def test_event_bus_publish_subscribe():
    """Verifica que los suscriptores reciban eventos del tipo suscrito."""
    bus = EventBus()
    received = []

    def handler(evt: Event):
        received.append(evt)

    bus.subscribe(EventType.TASK_COMPLETED, handler)
    bus.publish(EventType.TASK_STARTED, {"task_id": "US-001"})
    assert len(received) == 0  # No suscrito a TASK_STARTED

    bus.publish(EventType.TASK_COMPLETED, {"task_id": "US-001", "reason": "DoD Approved"})
    assert len(received) == 1
    assert received[0].payload["reason"] == "DoD Approved"


def test_event_bus_subscribe_all():
    """Verifica que los suscriptores globales escuchen todos los eventos."""
    bus = EventBus()
    received = []

    bus.subscribe_all(lambda evt: received.append(evt.type))

    bus.publish(EventType.SYSTEM_BOOT)
    bus.publish(EventType.AGENT_STATUS_CHANGE)
    bus.publish(EventType.TASK_BLOCKED)

    assert received == [EventType.SYSTEM_BOOT, EventType.AGENT_STATUS_CHANGE, EventType.TASK_BLOCKED]


def test_cli_subscriber_handles_events(capsys):
    """Verifica que CLIEventSubscriber procese múltiples eventos sin lanzar excepciones."""
    state = JellyfishState()
    subscriber = CLIEventSubscriber(state)
    subscriber.register()

    try:
        # Publicar eventos variados
        event_bus.publish(EventType.TASK_STARTED, {
            "task_num": 1, "total_tasks": 3, "task_id": "US-001",
            "task_retries": 0, "max_retries": 3, "task_desc": "Prueba de tarea",
            "agent_name": "developer", "output_file": "app.py"
        })

        event_bus.publish(EventType.TASK_COMPLETED, {
            "task_id": "US-001", "reason": "DoD Aprobado", "agent_name": "developer"
        })

        event_bus.publish(EventType.TASK_BLOCKED, {
            "task_id": "US-002", "missing_dep": "US-001", "agent_name": "developer"
        })

        event_bus.publish(EventType.AGENT_STATUS_CHANGE, {
            "agent": "developer", "status": "Ejecutando"
        })

        assert state.agent_statuses["developer"] == "Ejecutando"
    finally:
        subscriber.unregister()
