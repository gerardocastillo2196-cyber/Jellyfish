import unittest
from unittest.mock import MagicMock
from core.orchestration.product_owner import ProductOwnerPhase
from agents.product_owner import ProductOwnerAgent
from agents.qa_engineer import QAEngineerAgent
from core.commands.project import _SCRUM_METHODOLOGY_TEMPLATE, _BACKLOG_TEMPLATE


class TestMoSCoWDORAlignment(unittest.TestCase):

    def test_product_owner_agent_directives_and_rules(self):
        agent = ProductOwnerAgent()
        directives_str = " ".join([d[0] if isinstance(d, tuple) else d for d in agent.directives])
        rules_str = " ".join([r[0] if isinstance(r, tuple) else r for r in agent.rules])
        
        self.assertIn("MoSCoW", directives_str)
        self.assertIn("estimacion", directives_str)
        self.assertIn("MoSCoW", rules_str)

    def test_qa_engineer_agent_directives_and_rules(self):
        agent = QAEngineerAgent()
        directives_str = " ".join([d[0] if isinstance(d, tuple) else d for d in agent.directives])
        rules_str = " ".join([r[0] if isinstance(r, tuple) else r for r in agent.rules])
        
        self.assertIn("Definition of Ready", directives_str)
        self.assertIn("MoSCoW", directives_str)
        self.assertIn("MoSCoW", rules_str)

    def test_build_md_backlog_includes_moscow_and_estimation(self):
        orchestrator = MagicMock()
        po_phase = ProductOwnerPhase(orchestrator)
        
        backlog_dict = {
            "proyecto": "Test Project",
            "vision": "Test Vision",
            "user_stories": [
                {
                    "id": "US-001",
                    "titulo": "Autenticación de Usuario",
                    "como": "Usuario",
                    "quiero": "Iniciar sesión",
                    "para": "Acceder al sistema",
                    "prioridad": "Must-have",
                    "estimacion": "S (3 pts)",
                    "criterios_aceptacion": ["Dado un correo válido, cuando ingresa credenciales, entonces entra"],
                    "contexto_rag_necesario": ["auth.py"],
                    "definition_of_done": ["Tests pasados"]
                }
            ]
        }
        
        md = po_phase._build_md_backlog(backlog_dict)
        self.assertIn("- **Prioridad (MoSCoW):** Must-have", md)
        self.assertIn("- **Estimación:** S (3 pts)", md)

    def test_scrum_templates_contain_moscow(self):
        self.assertIn("Priorización Oficial (Metodología MoSCoW)", _SCRUM_METHODOLOGY_TEMPLATE)
        self.assertIn("Definition of Ready (DoR)", _SCRUM_METHODOLOGY_TEMPLATE)
        self.assertIn("Prioridad MoSCoW:", _BACKLOG_TEMPLATE)


if __name__ == "__main__":
    unittest.main()
