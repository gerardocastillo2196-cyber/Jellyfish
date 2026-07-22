import os
import json
import logging
import re
from core.llm_engine import _call_llm_silent
from core.ui import console

logger = logging.getLogger("jellyfish.translator")

class IntentTranslator:
    """Agente @translator: Traduce lenguaje natural a tokens de intención compactos."""

    def __init__(self, state):
        self.state = state
        self.project_path = state.active_project
        self.map_path = os.path.join(self.project_path, "intent_map.json") if self.project_path else "intent_map.json"
        self._load_map()

    def _load_map(self):
        if os.path.exists(self.map_path):
            try:
                with open(self.map_path, "r", encoding="utf-8") as f:
                    self.intent_map = json.load(f)
            except Exception as e:
                logger.warning("Error leyendo intent_map.json: %s", e)
                self.intent_map = {}
        else:
            self.intent_map = {}

    def _save_map(self):
        try:
            with open(self.map_path, "w", encoding="utf-8") as f:
                json.dump(self.intent_map, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning("Error guardando intent_map.json: %s", e)

    def translate(self, natural_input: str) -> str:
        """Traduce un input de lenguaje natural a un token de intención compacto."""
        if not natural_input:
            return ""

        cleaned_input = natural_input.strip()

        # Si ya es un token compacto, devolverlo directamente
        if cleaned_input.startswith("[") and cleaned_input.endswith("]"):
            return cleaned_input

        # 1. Compara contra el diccionario persistente
        for nat, comp in self.intent_map.items():
            if nat.lower().strip() == cleaned_input.lower():
                console.print(f"[green]✓ Coincidencia encontrada en diccionario: '{nat}' -> '{comp}'[/green]")
                return comp

        # 2. Si no hay coincidencia, llamar a @translator para sintetizar una intención compacta
        system_prompt = (
            "Eres @translator, un agente especializado en traducir lenguaje natural a tokens de intención densos y compactos.\n"
            "Formato de token: [CATEGORÍA:ACCIÓN] (en mayúsculas, ej: [DB:CONFIG], [INV:MANAGE_PRODUCTS]).\n\n"
            "Reglas de traducción:\n"
            "1. Si la instrucción del usuario es clara y específica, tradúcela a un token compacto único de la forma [CATEGORÍA:ACCIÓN] (máximo 30 caracteres). No agregues texto extra.\n"
            "2. Si la instrucción es vaga, ambigua, o carece de información suficiente (ej. 'hacer que compile' sin stack, 'agregar algo'), debes responder exactamente con la palabra 'AMBIGUOUS'.\n\n"
            "Devuelve únicamente el token o 'AMBIGUOUS'. Nada más."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Instrucción original: {cleaned_input}"}
        ]

        from core.tui import TaskProgress, tui_engine
        with TaskProgress(tui_engine, "auto_translator", "Translator: Traduciendo intención del usuario..."):
            response = _call_llm_silent(
                self.state,
                messages,
                provider=self.state.provider,
                model=self.state.model
            )

        if not response:
            token = f"[CMD:{cleaned_input.replace(' ', '_').upper()[:20]}]"
            self._register_new_intent(cleaned_input, token)
            return token

        token_clean = response.strip()
        if "AMBIGUOUS" in token_clean.upper():
            console.print("\n[yellow]⚠ El traductor detectó ambigüedad en la instrucción. Iniciando bucle de refinamiento interactivo...[/yellow]")
            refined_idea = self._run_refinement_loop(cleaned_input)
            return self.translate(refined_idea)

        # Validar y limpiar formato del token
        if not re.match(r"^\[[A-Z_]+:[A-Z_]+\]$", token_clean):
            match = re.search(r"\[[A-Z_]+:[A-Z_]+\]", token_clean.upper())
            if match:
                token_clean = match.group(0)
            else:
                token_clean = f"[CMD:{re.sub(r'[^A-Z_]', '', token_clean.upper())[:20]}]"

        self._register_new_intent(cleaned_input, token_clean)
        return token_clean

    def _register_new_intent(self, natural: str, compact: str):
        self.intent_map[natural] = compact
        self._save_map()
        
        if not hasattr(self.state, "new_intents"):
            self.state.new_intents = {}
        self.state.new_intents[natural] = compact

    def _run_refinement_loop(self, initial_input: str) -> str:
        refinement_system = (
            "Eres un consultor de requerimientos experto.\n"
            "El usuario ha dado una instrucción vaga o ambigua.\n"
            "Haz una pregunta corta y específica para aclarar qué desea lograr y qué tecnologías o componentes se verán involucrados.\n"
            "Sé muy conciso y directo."
        )
        
        refinement_history = [
            {"role": "system", "content": refinement_system},
            {"role": "user", "content": f"Instrucción ambigua: {initial_input}"}
        ]
        
        refining = True
        accumulated_responses = [initial_input]
        
        from core.tui import TaskProgress, tui_engine
        
        while refining:
            with TaskProgress(tui_engine, "auto_translator_refinement", "Translator: Evaluando ambigüedad..."):
                response = _call_llm_silent(
                    self.state,
                    refinement_history,
                    provider=self.state.provider,
                    model=self.state.model
                )
                
            if not response:
                break
                
            from rich.panel import Panel
            console.print()
            console.print(Panel(
                f"[bold cyan]{response}[/bold cyan]",
                title="[bold yellow]🤖 Translator (Refinamiento)[/bold yellow]",
                border_style="cyan"
            ))
            console.print()
            
            try:
                user_input = input("✍ Aclara tu instrucción (o escribe /skip o /ready para continuar) > ").strip()
            except (KeyboardInterrupt, EOFError):
                break
                
            if not user_input:
                continue
                
            if user_input.lower() in ("/skip", "/ready"):
                break
                
            refinement_history.append({"role": "assistant", "content": response})
            refinement_history.append({"role": "user", "content": user_input})
            accumulated_responses.append(user_input)
            
            check_messages = [
                {"role": "system", "content": "Determina si la información es suficiente para entender la intención del usuario. Responde exactamente con 'READY' o 'MORE'."},
                {"role": "user", "content": "Historial:\n" + "\n".join(accumulated_responses[-3:])}
            ]
            check_resp = _call_llm_silent(
                self.state,
                check_messages,
                provider=self.state.provider,
                model=self.state.model
            )
            if check_resp and "READY" in check_resp.upper():
                break
                
        return " - ".join(accumulated_responses)
