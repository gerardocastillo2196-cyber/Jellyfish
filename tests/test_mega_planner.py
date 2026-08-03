"""tests/test_mega_planner.py — Pruebas unitarias para la fase de planificación MegaPlanner."""

import os
import json
import tempfile
from unittest.mock import patch, MagicMock
import pytest

from core.orchestration.mega_planner import MegaPlannerPhase

class DummyOrchestrator:
    def __init__(self, project_path):
        self.project_path = project_path
        self.board_filename = "SPRINT_BOARD.md"
        self.metrics = []
        self.generated_files = []
        self.state = MagicMock()
        self.state.active_project = project_path
        self.state.provider = "ollama"
        self.state.model = "qwen"
        self.state.active_agency = "default"

    def _load_agent_prompt(self, agent_name):
        return f"Prompt para @{agent_name}"

    def _write_project_file(self, filename: str, content: str) -> None:
        filepath = os.path.join(self.project_path, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        self.generated_files.append(filename)

    def _read_project_file(self, filename: str) -> str:
        filepath = os.path.join(self.project_path, filename)
        if os.path.isfile(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                return f.read()
        return ""

def test_mega_planner_successful_generation():
    """Verifica que MegaPlannerPhase genere y escriba todos los artefactos correctamente."""
    with tempfile.TemporaryDirectory() as temp_dir:
        orchestrator = DummyOrchestrator(temp_dir)
        phase = MegaPlannerPhase(orchestrator)

        mock_master_json = {
            "intent_analysis": {
                "clasificacion": "NEW_PROJECT",
                "dominio": "E-Commerce",
                "stack_recomendado": "FastAPI + React",
                "equipo_requerido": ["backend_dev", "frontend_dev"]
            },
            "architecture": {
                "resumen": "Clean architecture description",
                "stack": {
                    "backend": "FastAPI",
                    "frontend": "React",
                    "infra": "Docker"
                },
                "decisiones": ["Use FastAPI"],
                "patrones": ["Repository Pattern"]
            },
            "backlog": {
                "proyecto": "ShopApp",
                "vision": "A great online shop",
                "user_stories": [
                    {
                        "id": "US-000",
                        "titulo": "Sprint 0: Infraestructura, Gestor de Dependencias y Entorno Base",
                        "como": "DevOps Engineer",
                        "quiero": "configurar el gestor",
                        "para": "garantizar un andamiaje",
                        "prioridad": "Must-have",
                        "estimacion": "S",
                        "criterios_aceptacion": ["CA1"],
                        "contexto_rag_necesario": ["Dockerfile"],
                        "definition_of_done": ["Syntax Check"]
                    },
                    {
                        "id": "US-001",
                        "titulo": "Crear catálogo",
                        "como": "Usuario",
                        "quiero": "ver el catálogo",
                        "para": "comprar productos",
                        "prioridad": "Must-have",
                        "estimacion": "M",
                        "criterios_aceptacion": ["CA2"],
                        "contexto_rag_necesario": [],
                        "definition_of_done": ["Linter check"]
                    }
                ]
            },
            "sprint_board": {
                "tareas": [
                    {
                        "id": "T-001",
                        "us_id": "US-000",
                        "task": "Configurar Dockerfile",
                        "agent": "devops_engineer",
                        "estimacion": "S",
                        "output_file": "Dockerfile",
                        "dependencias": []
                    },
                    {
                        "id": "T-002",
                        "us_id": "US-001",
                        "task": "Implementar catálogo",
                        "agent": "backend_dev",
                        "estimacion": "M",
                        "output_file": "src/catalog.py",
                        "dependencias": ["T-001"]
                    }
                ]
            }
        }

        # Mockear _call_llm_silent para:
        # 1. Clarification check -> READY
        # 2. Master JSON Generation -> mock_master_json
        with patch("core.orchestration.mega_planner._call_llm_silent") as mock_call_llm, \
             patch("builtins.input", return_value="y"):
            mock_call_llm.side_effect = ["READY", json.dumps(mock_master_json)]
            
            res = phase.run("Crear app E-Commerce")
            assert res is True
            
        # Verificar que se crearon los archivos esperados
        assert os.path.exists(os.path.join(temp_dir, "BACKLOG.json"))
        assert os.path.exists(os.path.join(temp_dir, "BACKLOG.md"))
        assert os.path.exists(os.path.join(temp_dir, "ARCHITECTURE.md"))
        assert os.path.exists(os.path.join(temp_dir, "SPRINT_BOARD.md"))
        assert os.path.exists(os.path.join(temp_dir, "SPRINT_BOARD.json"))

def test_mega_planner_json_extraction_resilience():
    """Verifica que el extractor de JSON tolere envoltorios Markdown y comas sobrantes."""
    orchestrator = DummyOrchestrator("")
    phase = MegaPlannerPhase(orchestrator)

    malformed_json_str = """
    ```json
    {
        "key": "value",
    }
    ```
    """
    parsed = phase._extract_json(malformed_json_str)
    assert parsed == {"key": "value"}

def test_mega_planner_clarification_loop():
    """Verifica que MegaPlannerPhase maneje la aclaración y solicite input del usuario."""
    with tempfile.TemporaryDirectory() as temp_dir:
        orchestrator = DummyOrchestrator(temp_dir)
        phase = MegaPlannerPhase(orchestrator)

        mock_master_json = {
            "intent_analysis": {},
            "architecture": {},
            "backlog": {
                "proyecto": "MobileApp",
                "user_stories": []
            },
            "sprint_board": {"tareas": []}
        }

        # Mockear _call_llm_silent para:
        # 1. Clarification check -> Pregunta del planificador
        # 2. Master JSON Generation -> mock_master_json
        with patch("core.orchestration.mega_planner._call_llm_silent") as mock_call_llm, \
             patch("builtins.input", side_effect=["React Native", "y"]) as mock_input:
            mock_call_llm.side_effect = ["¿Qué framework móvil quieres usar?", json.dumps(mock_master_json)]
            
            res = phase.run("Crear app móvil")
            assert res is True
            assert mock_input.call_count == 2
