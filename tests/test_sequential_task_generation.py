import os
import json
import pytest
from unittest.mock import patch, MagicMock
from core.state import JellyfishState
from core.orchestration.task_runner import TaskRunnerPhase
from core.project_orchestrator import ProjectOrchestrator


def test_sequential_generation_multiple_files(tmp_path):
    """Verifica que si una tarea requiere múltiples archivos separados por comas, se generen secuencialmente."""
    state = JellyfishState()
    project_dir = tmp_path / "test_project"
    project_dir.mkdir()
    state.active_project = str(project_dir)
    state.provider = "ollama"
    state.model = "qwen"
    
    # Crear un SPRINT_BOARD.json de prueba
    board_json_path = project_dir / "SPRINT_BOARD.json"
    board_md_path = project_dir / "SPRINT_BOARD.md"
    
    tasks = [
        {
            "id": "T-001",
            "task": "Crear file1.py y file2.py",
            "agent": "developer",
            "status": "TODO",
            "state": "TODO",
            "output_file": "file1.py, file2.py",
            "dependencies": []
        }
    ]
    
    with open(board_json_path, "w", encoding="utf-8") as f:
        json.dump(tasks, f)
        
    orchestrator = ProjectOrchestrator(state)
    runner = TaskRunnerPhase(orchestrator)
    
    call_args_files = []
    
    def mock_call_silent(state_arg, messages, agent_name=None, **kwargs):
        user_content = messages[1]["content"]
        
        if agent_name == "qa_engineer":
            return "[APPROVED]\nConsenso alcanzado."
        elif "Genera el contenido completo de file1.py" in user_content:
            call_args_files.append("file1.py")
            return "[WRITE_FILE: file1.py]\n```python\n# code file 1\n```\n[TAREA_COMPLETADA]"
        elif "Genera el contenido completo de file2.py" in user_content:
            call_args_files.append("file2.py")
            return "[WRITE_FILE: file2.py]\n```python\n# code file 2\n```\n[TAREA_COMPLETADA]"
        return ""
        
    with patch("core.orchestration.task_runner._call_llm_silent", side_effect=mock_call_silent), \
         patch("core.project_orchestrator.ProjectOrchestrator._run_dod_validation", return_value=(True, "Aprobado")):
        
        runner.run("Crear file1.py y file2.py")
        
    # Verificar orden e invocaciones
    assert call_args_files == ["file1.py", "file2.py"]
    
    # Verificar persistencia en disco
    assert os.path.exists(project_dir / "file1.py")
    assert os.path.exists(project_dir / "file2.py")


def test_reconcile_missing_docker_context_files(tmp_path):
    """Verifica que si se genera un Dockerfile con instrucciones COPY/ADD de archivos que no existen, se auto-creen placeholders."""
    state = JellyfishState()
    project_dir = tmp_path / "test_project"
    project_dir.mkdir()
    state.active_project = str(project_dir)
    
    # Crear un Dockerfile que copia archivos inexistentes
    backend_dir = project_dir / "backend"
    backend_dir.mkdir()
    
    dockerfile_path = backend_dir / "Dockerfile"
    dockerfile_content = """
    FROM python:3.9-slim
    WORKDIR /app
    COPY requirements.txt .
    COPY package.json ./
    COPY custom_file.py /app/custom_file.py
    COPY --from=builder /app/build /app/dist
    """
    with open(dockerfile_path, "w", encoding="utf-8") as f:
        f.write(dockerfile_content)
        
    orchestrator = ProjectOrchestrator(state)
    runner = TaskRunnerPhase(orchestrator)
    
    # Ejecutar reconciliación
    runner._reconcile_missing_docker_context_files(["backend/Dockerfile"])
    
    # Verificar que se crearon los archivos en backend/
    assert os.path.exists(backend_dir / "requirements.txt")
    assert os.path.exists(backend_dir / "package.json")
    assert os.path.exists(backend_dir / "custom_file.py")
    
    # Verificar que no se creó nada para --from=builder
    assert not os.path.exists(backend_dir / "builder")
    assert not os.path.exists(backend_dir / "dist")
    
    # Verificar contenido de package.json
    with open(backend_dir / "package.json", "r", encoding="utf-8") as pf:
        pkg_content = pf.read()
    assert "placeholder" in pkg_content

