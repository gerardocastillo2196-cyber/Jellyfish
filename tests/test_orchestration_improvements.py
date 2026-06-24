import unittest
import os
import tempfile
from core.agents.base import BaseAgent
from core.agents.registry import AgentRegistry
from core.orchestration.code_analyzer import analyze_file, format_analysis_for_log

class TestOrchestrationImprovements(unittest.TestCase):

    def setUp(self):
        # Escanear agentes antes de las pruebas
        agents_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "agents"))
        AgentRegistry.scan(agents_dir)

    def test_base_agent_instantiation(self):
        """Verifica que BaseAgent se comporta como un modelo de Pydantic."""
        agent = BaseAgent(
            name="test_agent",
            agency="testing",
            role="Testing Agent",
            expertise=["pytest", "unit test"],
            directives=["Test code daily."]
        )
        self.assertEqual(agent.name, "test_agent")
        self.assertEqual(agent.agency, "testing")
        self.assertIn("pytest", agent.expertise)
        self.assertIn("Test code daily.", agent.directives)

    def test_matches_task_scoring(self):
        """Verifica que el algoritmo de coincidencia de tareas funciona correctamente."""
        # Frontend agent
        frontend = AgentRegistry.get("frontend_dev")
        self.assertIsNotNone(frontend)

        # Backend agent
        backend = AgentRegistry.get("backend_dev")
        self.assertIsNotNone(backend)

        frontend_task = "Diseñar componentes React con CSS responsive y transiciones"
        backend_task = "Implementar API REST con base de datos relacional y docker"

        score_fe_on_fe = frontend.matches_task(frontend_task)
        score_be_on_fe = backend.matches_task(frontend_task)
        self.assertGreater(score_fe_on_fe, score_be_on_fe, "El agente frontend debería emparejar mejor con la tarea frontend")

        score_be_on_be = backend.matches_task(backend_task)
        score_fe_on_be = frontend.matches_task(backend_task)
        self.assertGreater(score_be_on_be, score_fe_on_be, "El agente backend debería emparejar mejor con la tarea backend")

    def test_registry_best_agent_for_task(self):
        """Verifica que el registro devuelve el mejor agente y filtra por agencia."""
        task = "Configurar pipeline CI/CD con Docker y Kubernetes"
        best = AgentRegistry.best_agent_for_task(task)
        self.assertIsNotNone(best)
        self.assertEqual(best.name, "devops_engineer")

        # Probar filtro por agencia
        best_marketing = AgentRegistry.best_agent_for_task(task, agency="marketing")
        self.assertIsNotNone(best_marketing)
        self.assertEqual(best_marketing.agency, "marketing")
        self.assertNotEqual(best_marketing.name, "devops_engineer")

    def test_code_analyzer_python(self):
        """Verifica el analizador programático sobre código Python."""
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as tmp:
            tmp.write(
                "import json\n"
                "from typing import List\n\n"
                "class UserSession:\n"
                "    pass\n\n"
                "def authenticate_user(username: str) -> bool:\n"
                "    return True\n"
            )
            tmp_path = tmp.name

        try:
            analysis = analyze_file(tmp_path)
            self.assertEqual(analysis["language"], "python")
            self.assertIn("UserSession", analysis["classes"])
            self.assertIn("authenticate_user", analysis["functions"])
            self.assertIn("json", analysis["imports"])
            self.assertIn("typing", analysis["imports"])
        finally:
            os.remove(tmp_path)

    def test_code_analyzer_javascript(self):
        """Verifica el analizador programático sobre código JS/TS."""
        with tempfile.NamedTemporaryFile(suffix=".js", mode="w", delete=False) as tmp:
            tmp.write(
                "import { config } from './config';\n"
                "const express = require('express');\n\n"
                "class DatabaseConnector {}\n\n"
                "const handleRequest = (req, res) => {};\n\n"
                "function initializeApp() {}\n\n"
                "app.post('/api/users', handleRequest);\n"
            )
            tmp_path = tmp.name

        try:
            analysis = analyze_file(tmp_path)
            self.assertEqual(analysis["language"], "javascript")
            self.assertIn("DatabaseConnector", analysis["classes"])
            self.assertIn("handleRequest", analysis["functions"])
            self.assertIn("initializeApp", analysis["functions"])
            self.assertIn("express", analysis["imports"])
            self.assertIn("POST /api/users", analysis["endpoints"])
        finally:
            os.remove(tmp_path)

if __name__ == "__main__":
    unittest.main()
