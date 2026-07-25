import unittest
from core.state import JellyfishState


class TestDefaultAgentSystemState(unittest.TestCase):

    def test_default_agent_system_state_injection(self):
        state = JellyfishState()
        state.load_agent("default")
        
        system_prompt = state.system_prompt
        
        # 1. Verificar título del System State
        self.assertIn("SYSTEM STATE & REALTIME ARCHITECTURE", system_prompt)
        self.assertIn("GOD MODE", system_prompt)
        
        # 2. Verificar catálogo real de agentes registrados
        self.assertIn("CATÁLOGO REAL DE AGENTES REGISTRADOS EN CORE", system_prompt)
        self.assertIn("@product_owner", system_prompt)
        self.assertIn("@backend_dev", system_prompt)
        self.assertIn("@qa_engineer", system_prompt)
        
        # 3. Verificar arquitectura real de /auto (MoSCoW, DoR, EventBus)
        self.assertIn("ARQUITECTURA AUTÓNOMA DE PIPELINE (/auto)", system_prompt)
        self.assertIn("MoSCoW", system_prompt)
        self.assertIn("Definition of Ready (DoR)", system_prompt)
        self.assertIn("EventBus", system_prompt)
        
        # 4. Verificar aislamiento de rol y reglas anti-alucinación
        self.assertIn("AISLAMIENTO DE ROL & DIRECTIVAS DE RESPUESTA", system_prompt)
        self.assertIn("NUNCA asumas roles de ejecución técnica", system_prompt)


if __name__ == "__main__":
    unittest.main()
