import os
import tempfile
import pytest
from core.state import JellyfishState


@pytest.fixture
def mock_project_env():
    with tempfile.TemporaryDirectory() as tmpdir:
        files = {
            "SPRINT_BOARD.md": "# SPRINT BOARD\n- [ ] Tarea 1: Login API\n- [x] Tarea 2: Setup DB\n" * 5,
            "DAILY.md": "# DAILY LOG\nAyer hicimos setup. Hoy hacemos API.\n" * 5,
            "DESIGN_TOKENS.md": "# DESIGN TOKENS\nColors: #000000, #FFFFFF\nTypography: Inter\n" * 5,
            "SECURITY.md": "# SECURITY MANIFEST\nJWT token secrets must be stored in vault.\n" * 5,
            "DATA_SCHEMA.md": "# DATA SCHEMA\nUsers table: id, username, password_hash\n" * 5,
        }
        for fname, content in files.items():
            with open(os.path.join(tmpdir, fname), "w", encoding="utf-8") as f:
                f.write(content)
        yield tmpdir


def test_lazy_loading_greeting_minimal_tokens(mock_project_env):
    """Verifica que un simple saludo ('hola') NO inyecte el contenido pesado de los archivos, solo el Índice TOC."""
    state = JellyfishState()
    state.active_project = mock_project_env
    state.history = [{"role": "user", "content": "hola"}]
    
    state.refresh_static_context()
    
    combined_content = " ".join(m.get("content", "") for m in state.static_history)
    
    # Debe contener el Índice Rápido (TOC)
    assert "ARCHIVOS TÉCNICOS Y DE GESTIÓN DISPONIBLES" in combined_content
    assert "SPRINT_BOARD.md" in combined_content
    assert "SECURITY.md" in combined_content
    
    # NO debe contener los cuerpos pesados de los archivos en sí
    assert "Tarea 1: Login API" not in combined_content
    assert "JWT token secrets must be stored in vault" not in combined_content
    assert "Colors: #000000" not in combined_content
    assert "Users table: id, username" not in combined_content
    assert "<internal_doc name=\"SPRINT_BOARD.md\"" not in combined_content


def test_lazy_loading_sprint_query_selective(mock_project_env):
    """Verifica que una consulta sobre tareas/sprint inyecte el tablero pero NO archivos ajenos como seguridad o diseño."""
    state = JellyfishState()
    state.active_project = mock_project_env
    state.history = [{"role": "user", "content": "¿cómo va el avance de las tareas del sprint?"}]
    
    state.refresh_static_context()
    
    combined_content = " ".join(m.get("content", "") for m in state.static_history)
    
    # Debe inyectar el SPRINT_BOARD
    assert "Tarea 1: Login API" in combined_content
    assert "<internal_doc name=\"SPRINT_BOARD.md\"" in combined_content
    
    # NO debe inyectar seguridad ni diseño
    assert "JWT token secrets must be stored in vault" not in combined_content
    assert "Colors: #000000" not in combined_content


def test_lazy_loading_security_query_selective(mock_project_env):
    """Verifica que una consulta sobre seguridad inyecte el manifiesto de seguridad."""
    state = JellyfishState()
    state.active_project = mock_project_env
    state.history = [{"role": "user", "content": "revisemos las políticas de seguridad y auth de la plataforma"}]
    
    state.refresh_static_context()
    
    combined_content = " ".join(m.get("content", "") for m in state.static_history)
    
    # Debe inyectar SECURITY
    assert "JWT token secrets must be stored in vault" in combined_content
    assert "<internal_doc name=\"SECURITY.md\"" in combined_content
    
    # NO debe inyectar el tablero sprint
    assert "Tarea 1: Login API" not in combined_content


def test_non_default_agent_loads_all(mock_project_env):
    """Verifica que los agentes especializados de pipeline (/auto) carguen todo el contexto sin filtrado."""
    state = JellyfishState()
    state.active_project = mock_project_env
    state.active_agent = "product_owner"
    state.history = [{"role": "user", "content": "iniciando refinamiento"}]
    
    state.refresh_static_context()
    
    combined_content = " ".join(m.get("content", "") for m in state.static_history)
    
    # En modo no-default debe inyectar todo para flujos automatizados
    assert "Tarea 1: Login API" in combined_content
    assert "JWT token secrets must be stored in vault" in combined_content
    assert "Colors: #000000" in combined_content
    assert "Users table: id, username" in combined_content
