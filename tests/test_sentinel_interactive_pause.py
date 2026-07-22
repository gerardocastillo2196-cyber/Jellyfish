import os
import json
import pytest
from core.state import JellyfishState
from core.agency_orchestrator import AgencyOrchestrator


def test_sentinel_pipeline_paused_state(tmp_path):
    """Verifica que el estado de pausa del pipeline se grabe y recupere correctamente."""
    state = JellyfishState()
    # Simular un proyecto activo
    project_dir = tmp_path / "test_project"
    project_dir.mkdir()
    state.active_project = str(project_dir)

    # El pipeline no debería estar pausado por defecto
    assert not state.is_pipeline_paused()

    # Pausar el pipeline con contexto
    context = {
        "task_id": "T-001",
        "agent_name": "developer",
        "error_log": "SyntaxError: invalid syntax",
        "task_desc": "Implement login",
        "output_file": "login.py"
    }
    state.set_pipeline_status("PIPELINE_PAUSED", context)

    # Debería estar pausado
    assert state.is_pipeline_paused()

    # El contexto recuperado debe coincidir
    retrieved_ctx = state.get_paused_context()
    assert retrieved_ctx["task_id"] == "T-001"
    assert retrieved_ctx["agent_name"] == "developer"
    assert retrieved_ctx["error_log"] == "SyntaxError: invalid syntax"

    # Despausar el pipeline
    state.set_pipeline_status("OK")
    assert not state.is_pipeline_paused()
    assert state.get_paused_context() == {}


def test_update_task_in_board(tmp_path):
    """Verifica que update_task_in_board actualice correctamente la descripción y el estado de la tarea."""
    state = JellyfishState()
    project_dir = tmp_path / "test_project"
    project_dir.mkdir()
    state.active_project = str(project_dir)

    # Crear SPRINT_BOARD.json simulado
    board_json_path = project_dir / "SPRINT_BOARD.json"
    board_md_path = project_dir / "SPRINT_BOARD.md"

    initial_tasks = [
        {
            "id": "T-001",
            "task": "Original task description",
            "agent": "developer",
            "status": "TODO",
            "state": "TODO",
            "dependencies": []
        }
    ]
    with open(board_json_path, "w", encoding="utf-8") as f:
        json.dump(initial_tasks, f)
    with open(board_md_path, "w", encoding="utf-8") as f:
        f.write("# SPRINT_BOARD\n## 📋 POR HACER (TODO)\n| ID | Tarea | Asignado | Estado |\n| T-001 | Original task description | @developer | TODO |\n")

    ceo = AgencyOrchestrator(state)
    
    # Actualizar descripción y estado de la tarea
    new_desc = "Updated description"
    ceo.update_task_in_board("T-001", new_desc=new_desc, new_status="FAILED")

    # Leer JSON y validar
    with open(board_json_path, "r", encoding="utf-8") as f:
        updated_tasks = json.load(f)

    assert updated_tasks[0]["task"] == new_desc
    assert updated_tasks[0]["status"] == "FAILED"
