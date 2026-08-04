import os
import json
import pytest
from unittest.mock import patch, MagicMock
from core.state import JellyfishState
from core.orchestration.task_runner import TaskRunnerPhase
from core.project_orchestrator import ProjectOrchestrator


def test_sentinel_auto_healing_autofix(tmp_path):
    """Verifica que si la validación DoD falla en el primer intento, Sentinel interviene con AUTO_FIX y cura la tarea."""
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
            "task": "Crear main.py",
            "agent": "developer",
            "status": "TODO",
            "state": "TODO",
            "output_file": "main.py",
            "dependencies": []
        }
    ]
    
    with open(board_json_path, "w", encoding="utf-8") as f:
        json.dump(tasks, f)
        
    orchestrator = ProjectOrchestrator(state)
    runner = TaskRunnerPhase(orchestrator)
    
    call_count = 0
    
    def mock_call_silent(state_arg, messages, agent_name=None, **kwargs):
        nonlocal call_count
        call_count += 1
        
        # Primera llamada: El desarrollador genera un main.py erróneo
        if agent_name == "developer":
            return "[WRITE_FILE: main.py]\n```python\n# Codigo con error\nprint('Hello world'\n```\n[TAREA_COMPLETADA]"
            
        # Segunda llamada: Sentinel Healer entra en acción
        if agent_name == "sentinel":
            # Sentinel devuelve un AUTO_FIX con el código corregido
            return '[AUTO_FIX]\nCorregí el paréntesis faltante en el print.\n<write_file path="main.py">\nprint(\'Hello world\')\n</write_file>'

        # Tercera llamada: QA Engineer aprueba en el debate de enjambre
        if agent_name == "qa_engineer":
            return "[APPROVED]\nConsenso alcanzado tras curación de Sentinel."
            
        # Cuarta llamada: Resumen semántico
        return "Creó main.py y lo corrigió."
        
    # Mockear las validaciones DoD para que pasen si el código ya tiene los paréntesis corregidos
    def mock_dod_validation(task_id, agent_name, task_desc, output_file, file_content):
        if "print('Hello world')" in file_content:
            return True, "Aprobado"
        return False, "Sintaxis incorrecta (paréntesis faltante)"
        
    with patch("core.llm_engine._call_llm_silent", side_effect=mock_call_silent), \
         patch("core.orchestration.task_runner._call_llm_silent", side_effect=mock_call_silent), \
         patch("core.project_orchestrator._call_llm_silent", side_effect=mock_call_silent), \
         patch("core.project_orchestrator.ProjectOrchestrator._run_dod_validation", side_effect=mock_dod_validation):
         
         runner.run("Crear main.py")
         
    # El flujo debe completarse en 1 intento con debate del enjambre:
    # 1. Developer (genera con error)
    # 2. Sentinel (aplica AUTO_FIX)
    # 3. QA Engineer (valida y aprueba en debate del enjambre)
    # 4. Resumen semántico del log
    assert call_count == 4
    
    # Verificar que el archivo main.py corregido se guardó correctamente en disco
    assert os.path.exists(project_dir / "main.py")
    with open(project_dir / "main.py", "r", encoding="utf-8") as f:
        content = f.read()
    assert "print('Hello world')" in content
    
    # Verificar que se registró en DEVELOPMENT_LOG.md
    assert os.path.exists(project_dir / "DEVELOPMENT_LOG.md")
    with open(project_dir / "DEVELOPMENT_LOG.md", "r", encoding="utf-8") as f:
        log_content = f.read()
    assert "@Sentinel (Auto-Healing)" in log_content


def test_ollama_404_model_fallback():
    """Verifica que si Ollama devuelve 404 (modelo no encontrado), _call_llm_silent realiza fallback dinámico a otro modelo de Ollama instalado."""
    from core.llm_engine import _call_llm_silent
    
    state = JellyfishState()
    state.provider = "ollama"
    state.model = "qwen:latest"  # Nuestro modelo base
    state.executor_model = "qwen2.5-coder:latest"  # El que dará 404
    
    # Mockear _get_available_ollama_models para que devuelva que el único disponible es qwen:latest
    available_mock = ["qwen:latest"]
    
    # Mockear httpx client stream
    mock_response_404 = MagicMock()
    mock_response_404.status_code = 404
    mock_response_404.__enter__.return_value = mock_response_404
    mock_response_404.read.return_value = b'{"error":"model \'qwen2.5-coder:latest\' not found"}'
    
    mock_response_200 = MagicMock()
    mock_response_200.status_code = 200
    mock_response_200.__enter__.return_value = mock_response_200
    mock_response_200.iter_lines.return_value = [
        '{"message": {"content": "Correcto desde fallback qwen:latest"}}'
    ]
    
    def mock_stream_send(method, url, **kwargs):
        payload = kwargs.get("json", {})
        model = payload.get("model")
        if model == "qwen2.5-coder:latest":
            return mock_response_404
        else:
            return mock_response_200
            
    # Mockear _get_available_ollama_models y httpx.Client
    with patch("core.llm_engine._get_available_ollama_models", return_value=available_mock), \
         patch("httpx.Client.stream", side_effect=mock_stream_send):
         
         res = _call_llm_silent(state, [{"role": "user", "content": "test"}], agent_name="developer")
         
    # Comprobar que se llamó recursivamente y devolvió el resultado del fallback (qwen:latest)
    assert res == "Correcto desde fallback qwen:latest"


def test_docker_compose_dynamic_service_build(tmp_path):
    """Verifica que _detect_build_command retorne comandos docker compose dirigidos solo a servicios con Dockerfiles existentes."""
    from core.project_orchestrator import ProjectOrchestrator
    from core.state import JellyfishState
    
    state = JellyfishState()
    state.active_project = str(tmp_path)
    
    # Crear un docker-compose.yml de prueba con dos servicios
    docker_yml_content = """
version: '3.8'
services:
  backend:
    build: ./backend
  admin_panel:
    build:
      context: ./admin_panel
      dockerfile: Dockerfile.prod
"""
    with open(tmp_path / "docker-compose.yml", "w", encoding="utf-8") as f:
        f.write(docker_yml_content)
        
    orchestrator = ProjectOrchestrator(state)
    
    # Caso 1: Ningún Dockerfile existe. Debe retornar "docker compose config".
    assert orchestrator._detect_compile_command() == "docker compose config"
    
    # Caso 2: Solo backend tiene Dockerfile. Debe retornar "docker compose build backend".
    backend_dir = tmp_path / "backend"
    backend_dir.mkdir()
    with open(backend_dir / "Dockerfile", "w", encoding="utf-8") as f:
        f.write("FROM python:3.11\n")
    assert orchestrator._detect_compile_command() == "docker compose build backend"
    
    # Caso 3: Ambos servicios tienen Dockerfiles. Debe retornar "docker compose build" con ambos (orden no estricto)
    admin_dir = tmp_path / "admin_panel"
    admin_dir.mkdir()
    with open(admin_dir / "Dockerfile.prod", "w", encoding="utf-8") as f:
        f.write("FROM node:18\n")
        
    build_cmd = orchestrator._detect_compile_command()
    assert "docker compose build" in build_cmd
    assert "backend" in build_cmd
    assert "admin_panel" in build_cmd


