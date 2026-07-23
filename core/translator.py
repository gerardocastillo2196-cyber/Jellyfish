import os
import json
import logging
import re
from core.llm_engine import _call_llm_silent
from core.ui import console

logger = logging.getLogger("jellyfish.translator")

MAX_TRANSLATOR_TURNS = 3

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
                    raw_map = json.load(f)
                    # Purgar acrónimos legacy tipo [CMD:...] que destruyen el contexto del usuario
                    self.intent_map = {
                        k: v for k, v in raw_map.items()
                        if isinstance(v, str) and not v.startswith("[CMD:")
                    }
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

    def translate(self, natural_input: str, turn_count: int = 1) -> str:
        """Traduce un input de lenguaje natural a un token de intención compacto."""
        if not natural_input:
            return ""

        cleaned_input = natural_input.strip()
        # Si ya es un token compacto o bloque DSL, devolverlo directamente
        if cleaned_input.startswith("[INTENT:") or (cleaned_input.startswith("[") and cleaned_input.endswith("]")):
            return cleaned_input

        # 1. Compara contra el diccionario persistente (ignorando acrónimos legacy)
        for nat, comp in self.intent_map.items():
            if nat.lower().strip() == cleaned_input.lower() and not comp.startswith("[CMD:"):
                console.print(f"[green]✓ Coincidencia encontrada en diccionario: '{nat[:40]}…' -> DSL[/green]")
                return comp

        # 2. Si no hay coincidencia, llamar a @translator para sintetizar una intención compacta
        if turn_count >= MAX_TRANSLATOR_TURNS:
            system_prompt = (
                "Eres @translator, un agente especializado en actuar como un Sintetizador Técnico (DSL Generator).\n"
                "Tu objetivo es convertir la prosa o requerimiento del usuario en un bloque de especificaciones técnicas ultra-condensado.\n\n"
                "REGLA DE FORMATO ESTRICTA:\n"
                "Debes devolver ÚNICAMENTE el bloque con la siguiente estructura de clave-valor:\n"
                "[INTENT: <Intención, ej: NEW_PROJECT, ADD_FEATURE, FIX_BUG, etc.>]\n"
                "SCOPE: <Nombre corto o descripción compacta del alcance>\n"
                "ARCH: <Arquitectura o stack tecnológico recomendado, ej: Next.js + PostgreSQL, React Native, FastAPI, etc.>\n"
                "MODULES: [<Módulo 1>, <Módulo 2>, <Módulo 3>]\n"
                "CONSTRAINTS: [<Restricción 1>, <Restricción 2>, ...]\n\n"
                "REGLAS CRÍTICAS:\n"
                "1. NO generes acrónimos basados en las primeras palabras del prompt.\n"
                "2. NUNCA respondas con 'AMBIGUOUS' en esta fase. Si la instrucción es vaga o ambigua, asume automáticamente las tecnologías estándar más adecuadas de la industria (ej. React Native/Flutter para móviles, PostgreSQL/Docker para backend, Next.js para web, pytest para testing).\n"
                "3. NO agregues introducciones, explicaciones, bloques de markdown ni textos conversacionales fuera del bloque de especificaciones. Tu salida debe empezar directamente con '[INTENT:'."
            )
        else:
            system_prompt = (
                "Eres @translator, un agente especializado en actuar como un Sintetizador Técnico (DSL Generator).\n"
                "Tu objetivo es convertir la prosa o requerimiento del usuario en un bloque de especificaciones técnicas ultra-condensado.\n\n"
                "REGLAS CRÍTICAS:\n"
                "1. Si la instrucción es sumamente vaga o ambigua, y no permite entender el alcance básico o arquitectura (ej. 'hacer algo', 'mejorar', 'agregar'), debes responder exactamente con la palabra 'AMBIGUOUS'.\n"
                "2. Si la instrucción es clara o contiene suficiente contexto, conviértela en un bloque de especificaciones técnicas ultra-condensado con el siguiente formato clave-valor:\n"
                "[INTENT: <Intención, ej: NEW_PROJECT, ADD_FEATURE, FIX_BUG, etc.>]\n"
                "SCOPE: <Nombre corto o descripción compacta del alcance>\n"
                "ARCH: <Arquitectura o stack tecnológico recomendado, ej: Next.js + PostgreSQL, React Native, FastAPI, etc.>\n"
                "MODULES: [<Módulo 1>, <Módulo 2>, <Módulo 3>]\n"
                "CONSTRAINTS: [<Restricción 1>, <Restricción 2>, ...]\n\n"
                "3. NO generes acrónimos basados en las primeras palabras del prompt.\n"
                "4. Si el usuario solicita 'tecnologías en tendencia' o da respuestas abiertas, asume automáticamente las tecnologías estándar de la industria (ej. React Native/Flutter para móvil, PostgreSQL/Docker para backend) y genera el bloque clave-valor técnico inmediatamente sin responder 'AMBIGUOUS'.\n"
                "5. Si decides generar el bloque, NO agregues introducciones, explicaciones, bloques de markdown ni textos conversacionales fuera de él. Tu salida debe empezar directamente con '[INTENT:'."
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
            token = (
                f"[INTENT: CMD]\n"
                f"SCOPE: {cleaned_input[:50]}\n"
                f"ARCH: None\n"
                f"MODULES: []\n"
                f"CONSTRAINTS: []"
            )
            self._register_new_intent(cleaned_input, token)
            return token

        token_clean = response.strip()
        if "AMBIGUOUS" in token_clean.upper():
            if turn_count < MAX_TRANSLATOR_TURNS:
                console.print("\n[yellow]⚠ El traductor detectó ambigüedad en la instrucción. Iniciando bucle de refinamiento interactivo...[/yellow]")
                refined_idea, updated_turns = self._run_refinement_loop(cleaned_input, turn_count)
                return self.translate(refined_idea, turn_count=updated_turns)
            else:
                token_clean = (
                    f"[INTENT: CMD]\n"
                    f"SCOPE: {cleaned_input[:50]}\n"
                    f"ARCH: None\n"
                    f"MODULES: []\n"
                    f"CONSTRAINTS: []"
                )

        # Validar y limpiar formato del bloque DSL o token
        if not (token_clean.startswith("[INTENT:") or re.match(r"^\[[A-Z_]+:[A-Z_]+\]$", token_clean)):
            # Si no empieza con [INTENT:, pero tiene uno adentro, extraerlo
            match_intent = re.search(r"(\[INTENT:\s*[A-Z_]+\].*)", token_clean, re.DOTALL | re.IGNORECASE)
            if match_intent:
                token_clean = match_intent.group(1).strip()
            else:
                match_token = re.search(r"\[[A-Z_]+:[A-Z_]+\]", token_clean.upper())
                if match_token:
                    token_clean = match_token.group(0)
                else:
                    token_clean = (
                        f"[INTENT: CMD]\n"
                        f"SCOPE: {cleaned_input[:50]}\n"
                        f"ARCH: None\n"
                        f"MODULES: []\n"
                        f"CONSTRAINTS: []"
                    )

        self._register_new_intent(cleaned_input, token_clean)
        return token_clean

    def _register_new_intent(self, natural: str, compact: str):
        if compact.startswith("[CMD:"):
            return
        self.intent_map[natural] = compact
        self._save_map()
        
        if not hasattr(self.state, "new_intents"):
            self.state.new_intents = {}
        self.state.new_intents[natural] = compact

    def _run_refinement_loop(self, initial_input: str, turn_count: int = 1) -> tuple[str, int]:
        refinement_system = (
            "Eres un consultor de requerimientos experto.\n"
            "El usuario ha dado una instrucción vaga o ambigua.\n"
            "Haz una pregunta corta y específica para aclarar qué desea lograr y qué tecnologías o componentes se verán involucrados.\n"
            "Si el usuario solicita 'tecnologías en tendencia' o da respuestas abiertas tras 2 preguntas, NUNCA te cicles. Asume automáticamente las tecnologías estándar de la industria (ej. React Native/Flutter para móvil, PostgreSQL/Docker para backend) y genera el token de intención inmediatamente.\n"
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
            if turn_count >= MAX_TRANSLATOR_TURNS:
                break

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
            
            turn_count += 1
            if turn_count >= MAX_TRANSLATOR_TURNS:
                break
                
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
                
        return " - ".join(accumulated_responses), turn_count
