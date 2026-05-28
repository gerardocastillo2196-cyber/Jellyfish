import unittest
import os
from core.state import JellyfishState
from core.project_orchestrator import ProjectOrchestrator
from plugins.integration.skill_loader import load_skills
from core.plugin_manager import PluginManager

class TestAgentCapabilities(unittest.TestCase):

    def setUp(self):
        """Inicializa el estado simulado antes de cada prueba."""
        self.state = JellyfishState()
        self.state.agency_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        self.orchestrator = ProjectOrchestrator(self.state)

    def test_skills_injection_in_prompt(self):
        """
        Verifica que las habilidades (skills) se estén leyendo correctamente 
        desde el disco y se inyecten en el contexto del agente.
        """
        agent_name = "backend_dev"
        
        # Simulamos la carga del prompt del agente
        agent_prompt = self.orchestrator._load_agent_prompt(agent_name)
        
        # Validamos que el prompt base exista
        self.assertIsNotNone(agent_prompt, f"No se pudo cargar el prompt base para {agent_name}")

        # Simulamos la carga de skills
        skills_context = load_skills(agent_name, self.state.agency_dir)
        
        # El contexto de skills debe contener texto y no estar vacío
        self.assertTrue(len(skills_context) > 0, "El SkillLoader no devolvió ninguna habilidad.")
        
        # Opcional: Verificar que una skill específica esté presente para el backend
        self.assertIn("Clean Architecture", skills_context, "El agente no tiene cargada la skill de Clean Architecture")

    def test_plugins_are_loaded_and_active(self):
        """
        Verifica que el PluginManager reconozca y active los plugins
        necesarios para la interacción con el entorno.
        """
        plugins_dir = os.path.join(self.state.agency_dir, "plugins")
        plugin_manager = PluginManager(plugins_dir)
        plugin_manager.load_all_plugins()
        loaded_plugins = list(plugin_manager._plugin_files.keys())
        
        self.assertGreater(len(loaded_plugins), 0, "No se detectó ningún plugin en el sistema.")
        
        # Verificar que plugins críticos estén en la lista
        has_automation = any(name.startswith("automation/") for name in loaded_plugins)
        has_integration = any(name.startswith("integration/") for name in loaded_plugins)
        
        self.assertTrue(has_automation, "El plugin de automatización no está cargado.")
        self.assertTrue(has_integration, "El plugin de integración no está cargado.")

    def test_agent_context_includes_capabilities(self):
        """
        Asegura que el ensamblaje final del sistema envíe las capacidades 
        del entorno (env_capabilities.json) al agente.
        """
        cap_path = os.path.join(self.state.agency_dir, "env_capabilities.json")
        
        # Verificamos que el archivo exista tras el escaneo
        self.assertTrue(os.path.exists(cap_path), "No se encontró el archivo env_capabilities.json")
        
        with open(cap_path, "r") as f:
            content = f.read()
            self.assertIn("python", content.lower(), "Las capacidades del entorno no detectan lenguajes clave.")

if __name__ == '__main__':
    unittest.main(verbosity=2)
