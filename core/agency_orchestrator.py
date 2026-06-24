"""core/agency_orchestrator.py - Orquestador de Agencias (CEO) para Jellyfish OS v6

Clasifica los prompts de usuario y los redirige a la agencia correspondiente,
configurando el estado global antes de delegar la ejecución a ProjectOrchestrator.
Refactored to inherit from BaseOrchestrator.
"""

import logging
from core.state import JellyfishState
from core.orchestration import BaseOrchestrator

logger = logging.getLogger("jellyfish.agency_orchestrator")

class AgencyOrchestrator(BaseOrchestrator):
    """El CEO invisible del sistema. Clasifica intenciones y delega a la agencia correcta."""
    
    def __init__(self, state: JellyfishState):
        super().__init__(state)

    def classify_agency(self, user_prompt: str) -> str:
        """Determina cuál es la mejor agencia para resolver el requerimiento (forzando JSON)."""
        import json
        agencies = list(self.state.agency_catalog.keys())
        if not agencies:
            agencies = ["default", "development", "marketing", "research"]
        
        system_prompt = (
            "Eres el CEO de Jellyfish OS. Tu trabajo es clasificar la idea del usuario "
            "y asignarla a la agencia más calificada para realizar el proyecto.\n"
            f"Agencias disponibles: {', '.join(agencies)}\n\n"
            "Reglas de clasificación:\n"
            "- 'development': Para construir software, programar, resolver bugs, desarrollo web, scripts, etc.\n"
            "- 'marketing': Para estrategias de venta, redacción publicitaria, SEO, campañas, copy, etc.\n"
            "- 'research': Para investigación profunda, análisis científico, reportes, ciencia de datos, etc.\n"
            "- 'management': Para planificar proyectos abstractos o puramente metodológicos.\n"
            "- 'default': Cualquier tema genérico que no encaje en las anteriores.\n\n"
            "CRÍTICO: Debes responder ÚNICAMENTE con un objeto JSON puro, sin bloques markdown. "
            'Ejemplo: {"agency": "development"}'
        )
        
        try:
            response = self._generate_silent(
                system_prompt,
                f"Idea del usuario: {user_prompt}",
                provider=self.state.provider,
                model=self.state.model
            )
            
            if not response:
                return "development"

            import re
            json_match = re.search(r"\{.*\}", response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(0))
                classified = data.get("agency", "development").lower().strip()
                if classified in agencies:
                    return classified
                for agency in agencies:
                    if agency in classified:
                        return agency
        except Exception as e:
            logger.error("Error al clasificar agencia con JSON: %s", e)
        
        return "development"

    def route_and_execute(self, user_prompt: str) -> str:
        """Clasifica el prompt, cambia la agencia activa y ejecuta el orquestador."""
        from core.tui import TaskProgress, tui_engine
        
        try:
            with TaskProgress(tui_engine, "auto_ceo", "CEO: Analizando requerimientos y seleccionando agencia idónea..."):
                agency = self.classify_agency(user_prompt)
        except Exception as e:
            logger.error("Error al clasificar agencia en CEO: %s", e)
            agency = "development"
            
        self.state.active_agency = agency
        
        try:
            from core.project_orchestrator import ProjectOrchestrator
            orchestrator = ProjectOrchestrator(self.state)
            return orchestrator.run(user_prompt)
        except Exception as e:
            logger.error("Error crítico durante la ejecución de la agencia %s: %s", agency, e, exc_info=True)
            from core.ui import console
            console.print(f"\n[bold red]❌ Error Crítico en Orquestador de Agencia ({agency}):[/bold red] {e}")
            return f"Error de orquestación en la agencia '{agency}': {e}"
