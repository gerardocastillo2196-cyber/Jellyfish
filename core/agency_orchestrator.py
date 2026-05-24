"""core/agency_orchestrator.py - Orquestador de Agencias (CEO) para Jellyfish OS v6

Clasifica los prompts de usuario y los redirige a la agencia correspondiente,
configurando el estado global antes de delegar la ejecución a ProjectOrchestrator.
"""

import logging
from core.state import JellyfishState
from core.llm_engine import _call_llm_silent

logger = logging.getLogger("jellyfish.agency_orchestrator")

class AgencyOrchestrator:
    """El CEO invisible del sistema. Clasifica intenciones y delega a la agencia correcta."""
    
    def __init__(self, state: JellyfishState):
        self.state = state

    def classify_agency(self, user_prompt: str) -> str:
        """Determina cuál es la mejor agencia para resolver el requerimiento (forzando JSON)."""
        import json
        # Obtener las agencias disponibles en el catálogo
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
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Idea del usuario: {user_prompt}"}
        ]
        
        try:
            response = _call_llm_silent(
                self.state, messages,
                provider=self.state.provider,
                model=self.state.model
            )
            
            if not response:
                return "development"

            # Parsear JSON de forma robusta
            import re
            json_match = re.search(r"\{.*\}", response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(0))
                classified = data.get("agency", "development").lower().strip()
                if classified in agencies:
                    return classified
                # Fallback de coincidencia parcial
                for agency in agencies:
                    if agency in classified:
                        return agency
        except Exception as e:
            logger.error("Error al clasificar agencia con JSON: %s", e)
        
        # Fallback por defecto si algo falla
        return "development"

    def route_and_execute(self, user_prompt: str) -> str:
        """Clasifica el prompt, cambia la agencia activa y ejecuta el orquestador."""
        from core.tui import TaskProgress, tui_engine
        
        with TaskProgress(tui_engine, "auto_ceo", "CEO: Analizando requerimientos y seleccionando agencia idónea..."):
            agency = self.classify_agency(user_prompt)
            
        self.state.active_agency = agency
        
        # Retrocompatibilidad absoluta: delegamos al ProjectOrchestrator,
        # el cual usará el tablero y los agentes específicos de la agencia clasificada.
        from core.project_orchestrator import ProjectOrchestrator
        orchestrator = ProjectOrchestrator(self.state)
        return orchestrator.run(user_prompt)
