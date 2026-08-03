"""tests/test_state_proxy.py — Pruebas unitarias para la vista de solo lectura StateProxy."""

import os
import tempfile
import pytest
from core.state_proxy import StateProxy

class DummyState:
    def __init__(self, active_project=""):
        self.active_project = active_project
        self.active_agent = "default"
        self.active_agency = "default"
        self.agency_catalog = {"default": ["default"]}
        self.provider = "ollama"
        self.model = "qwen2.5-coder"
        self.project_methodology = "scrum"
        self.history = []
        self.context_files = set()
        self.session_tokens = 100

def test_path_traversal_blocking():
    """Verifica que StateProxy prevenga path traversal al intentar leer archivos fuera del proyecto."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Crear un archivo fuera del directorio del proyecto
        secret_file = os.path.join(temp_dir, "secret.txt")
        with open(secret_file, "w", encoding="utf-8") as f:
            f.write("SECRET_KEY_123")

        project_dir = os.path.join(temp_dir, "project")
        os.makedirs(project_dir, exist_ok=True)

        state = DummyState(active_project=project_dir)
        proxy = StateProxy(state)

        # Intentar path traversal hacia secret.txt
        content = proxy.read_project_file("../secret.txt")
        assert content == ""

def test_invalid_role_blocking():
    """Verifica que StateProxy no permita añadir mensajes al historial con roles no válidos."""
    state = DummyState()
    proxy = StateProxy(state)

    proxy.append_to_history("hacker_role", "Inyección de prompt")
    assert len(state.history) == 0

    proxy.append_to_history("user", "Mensaje válido")
    assert len(state.history) == 1
    assert state.history[0]["role"] == "user"

def test_content_truncation():
    """Verifica que StateProxy trunque contenidos de mensajes que excedan 5000 caracteres."""
    state = DummyState()
    proxy = StateProxy(state)

    huge_payload = "A" * 10000
    proxy.append_to_history("user", huge_payload)
    assert len(state.history) == 1
    assert len(state.history[0]["content"]) == 5000

def test_read_valid_project_file():
    """Verifica que StateProxy lea archivos legítimos dentro del proyecto activo."""
    with tempfile.TemporaryDirectory() as temp_dir:
        state = DummyState(active_project=temp_dir)
        proxy = StateProxy(state)

        test_file = os.path.join(temp_dir, "README.md")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("# Mi Proyecto")

        content = proxy.read_project_file("README.md")
        assert content == "# Mi Proyecto"

def test_empty_active_project():
    """Verifica el comportamiento cuando no hay un proyecto activo asignado."""
    state = DummyState(active_project="")
    proxy = StateProxy(state)

    assert proxy.get_active_project() == ""
    assert proxy.read_project_file("anything.txt") == ""

def test_provider_info_sanitization():
    """Verifica que get_provider_info retorne proveedor y modelo sin exponer llaves."""
    state = DummyState()
    proxy = StateProxy(state)

    info = proxy.get_provider_info()
    assert info == {"provider": "ollama", "model": "qwen2.5-coder"}
    assert "api_key" not in info
