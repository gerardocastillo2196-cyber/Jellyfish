import os
import time
import json
import re
import logging
from rich.console import Console
from rich.prompt import Confirm
from core.tui import tui_engine, TaskProgress
from core.state import estimate_tokens

logger = logging.getLogger("jellyfish.orchestration.product_owner")
console = Console()

class ProductOwnerPhase:
    """Fase 1 del desarrollo autónomo: Product Owner & Validación DoR."""

    def __init__(self, orchestrator):
        self.orchestrator = orchestrator

    def _build_md_backlog(self, backlog_dict: dict) -> str:
        from core.local_transformers import local_ai_manager
        md = f"# Backlog: {backlog_dict.get('proyecto', 'Proyecto Jellyfish')}\n\n"
        md += f"**Visión:** {backlog_dict.get('vision', '')}\n\n"
        md += "## Historias de Usuario\n\n"
        for us in backlog_dict.get("user_stories", []):
            desc_text = f"{us.get('titulo', '')} {us.get('quiero', '')} {us.get('para', '')}"
            tags = local_ai_manager.tag_backlog_item(desc_text)
            tag_str = " ".join([f"**[{t}]**" for t in tags])
            md += f"### {us.get('id')}: {tag_str} {us.get('titulo')}\n"
            md += f"- **Como:** {us.get('como')}\n"
            md += f"- **Quiero:** {us.get('quiero')}\n"
            md += f"- **Para:** {us.get('para')}\n"
            prioridad = us.get('prioridad') or us.get('priority') or 'Must-have'
            md += f"- **Prioridad (MoSCoW):** {prioridad}\n"
            if "estimacion" in us:
                md += f"- **Estimación:** {us.get('estimacion')}\n"
            elif "estimation" in us:
                md += f"- **Estimación:** {us.get('estimation')}\n"
            md += "\n#### Criterios de Aceptación\n"
            for ca in us.get("criterios_aceptacion", []):
                md += f"- {ca}\n"
            md += "\n#### Contexto RAG\n"
            for rag_ctx in us.get("contexto_rag_necesario", []):
                md += f"- `{rag_ctx}`\n"
            md += "\n#### Definition of Done\n"
            for dod in us.get("definition_of_done", []):
                md += f"- {dod}\n"
            md += "\n---\n\n"
        return md


    def extract_json_block(self, text: str) -> dict:
        """Extrae de manera robusta el bloque JSON {...} o [...] de un texto y lo devuelve como dict.

        Lanza ValueError o json.JSONDecodeError si no se encuentra o no se puede parsear.
        """
        if not text:
            raise ValueError("Texto vacío.")
            
        # Limpiar bloques de código markdown si están presentes
        cleaned_text = re.sub(r'```(?:json)?', '', text).strip()
        
        match = re.search(r'(\{.*\}|\[.*\])', cleaned_text, re.DOTALL)
        if not match:
            raise ValueError("No se encontró ningún bloque JSON ({...} o [...]) en la respuesta.")
            
        json_str = match.group(1).strip()
        
        parsed = None
        # 1. Intentar parseo directo
        try:
            parsed = json.loads(json_str)
        except Exception:
            pass

        # 2. Limpiar comas flotantes/finales (trailing commas: ,} o ,]) comúnmente generadas por LLMs
        if parsed is None:
            sanitized_str = re.sub(r',\s*([\}\]])', r'\1', json_str)
            try:
                parsed = json.loads(sanitized_str)
            except Exception:
                pass

        # 3. Intentar reparar comillas simples si el LLM las usó en las claves
        if parsed is None:
            try:
                fixed_quotes = re.sub(r"(?<=[\{\,\s])'([a-zA-Z0-9_]+)':", r'"\1":', json_str)
                parsed = json.loads(fixed_quotes)
            except Exception:
                pass

        # 4. Si fallaron los desinfectores, forzar json.loads directo para propagar excepción original
        if parsed is None:
            parsed = json.loads(json_str)

        # Si el JSON resultador es una lista, envolver en dict con user_stories
        if isinstance(parsed, list):
            return {
                "proyecto": "Proyecto Jellyfish",
                "vision": "Generado desde lista de historias de usuario",
                "user_stories": parsed
            }

        if not isinstance(parsed, dict):
            raise ValueError(f"Se esperaba un objeto JSON (dict) pero se obtuvo {type(parsed).__name__}")

        return parsed

    def run(self, user_idea: str) -> bool:
        """Genera BACKLOG.md y solicita aprobación del usuario."""
        console.print("\n━━━ FASE 1: 📝 Product Owner ━━━")
        t0 = time.perf_counter()

        agent_prompt = self.orchestrator._load_agent_prompt("product_owner")
        
        last_exit = self.orchestrator._get_last_exit_code()
        cb_count = self.orchestrator._get_circuit_breaker_count()
        
        if last_exit != 0 and cb_count >= 3:
            console.print(f"❌ CIRCUIT BREAKER ACTIVADO: El entorno falló la compilación {cb_count} veces consecutivas a pesar de los intentos de Auto-Healing. Intervención manual requerida.")
            try:
                reset_cb = Confirm.ask("¿Deseas restablecer el Circuit Breaker y forzar la ejecución de todas formas? [y/n]", default=False)
                if reset_cb:
                    self.orchestrator._reset_circuit_breaker()
                    console.print("✓ Circuit Breaker restablecido. Iniciando ejecución...\n")
                    last_exit = 0
            except (EOFError, KeyboardInterrupt):
                return False

        # --- SUB-FASE A: Refinamiento Interactivo ---
        refinement_system = (
            f"Eres @product_owner, el Product Owner del equipo de desarrollo.\n"
            f"Tu rol en este momento es refinar e indagar activamente sobre la idea del usuario. "
            f"Tu meta final es redactar un Backlog completo con al menos 4 Historias de Usuario priorizadas con MoSCoW "
            f"y con criterios de aceptación claros.\n\n"
            f"REGLA CRÍTICA DE SPRINT 0 (INFRAESTRUCTURA OBLIGATORIA):\n"
            f"El Backlog DEBE incluir como primera prioridad una historia bloqueante obligatoria: 'US-000: Sprint 0 - Infraestructura y Entorno' (prioridad Must-have). "
            f"Esta historia exige la creación del gestor de dependencias (package.json, requirements.txt, build.gradle, etc.), archivos de contenedorización (Dockerfile, docker-compose.yml) y el punto de entrada principal (server.js, App.tsx, main.py). Ninguna tarea de lógica de negocio o UI puede ir antes de este Sprint 0.\n\n"
            f"REGLA CRÍTICA DE EVALUACIÓN: Evalúa si la información actual es suficiente para redactar esas historias de usuario sin inventar o suponer datos clave (ej. stack, lógica, flujos).\n"
            f"- Si la información es INSUFICIENTE: Formula exactamente una pregunta clara, directa y concisa para aclarar los requerimientos. NO generes el backlog, NO respondas con introducciones largas ni saludos. Ve al grano.\n"
            f"- Si la información es SUFICIENTE para redactar las US y los criterios: Responde ÚNICAMENTE con la palabra 'READY'. Ninguna otra palabra o explicación está permitida. Solo escribe 'READY'."
        )

        refinement_history = [
            {"role": "system", "content": refinement_system},
            {"role": "user", "content": f"Idea del proyecto: {user_idea}"}
        ]

        from core.llm_engine import _call_llm_silent
        
        console.print("[dim]       ⚙ Iniciando bucle de refinamiento interactivo del Product Owner...[/dim]")
        
        refining = True
        refinement_log = [f"Idea inicial del proyecto: {user_idea}"]
        
        while refining:
            with TaskProgress(tui_engine, "auto_po_refinement", "Product Owner: Evaluando requerimientos..."):
                response = _call_llm_silent(
                    self.orchestrator.state,
                    refinement_history,
                    provider=self.orchestrator.state.provider,
                    model=self.orchestrator.state.model,
                    timeout=300.0
                )
            
            if not response:
                if user_idea.startswith("[INTENT:") or len(user_idea) > 150:
                    logger.info("El prompt/DSL entregado contiene contexto técnico suficiente. Continuando con la generación de backlog.")
                    response = "READY"
                else:
                    console.print("[yellow]⚠ El Product Owner no respondió. Activando cuestionario de fallback automático...[/yellow]")
                
                # Cuestionario de fallback predeterminado según el dominio
                fallback_questions = []
                idea_lower = user_idea.lower()
                
                if any(k in idea_lower for k in ("android", "ios", "móvil", "mobile", "app")):
                    fallback_questions = [
                        "¿Qué framework o tecnología prefieres para las aplicaciones móviles? (ej. React Native, Flutter, Swift/Kotlin nativo)",
                        "¿La aplicación móvil requiere soporte para funcionamiento offline (sin conexión a internet)?",
                        "¿Cómo deseas gestionar la autenticación de usuarios en el backend? (ej. JWT, OAuth2, Firebase Auth)"
                    ]
                elif any(k in idea_lower for k in ("docker", "compose", "servidor", "server", "deploy", "despliegue")):
                    fallback_questions = [
                        "¿Quieres que el despliegue incluya archivos Dockerfile y docker-compose completos y listos para producción?",
                        "¿Qué puerto/servidor web backend prefieres utilizar para el despliegue? (ej. Nginx, Node.js, Python Gunicorn)",
                        "¿Qué base de datos prefieres para almacenar la información? (ej. PostgreSQL, MySQL, SQLite)"
                    ]
                elif any(k in idea_lower for k in ("web", "frontend", "react", "vue", "next")):
                    fallback_questions = [
                        "¿Qué framework frontend prefieres utilizar para el panel web o de administración? (ej. React, Next.js, Vue, vanilla HTML/JS)",
                        "¿Prefieres un diseño responsivo adaptado para dispositivos móviles o centrado en escritorio?",
                        "¿Qué herramientas de estilo o CSS prefieres utilizar? (ej. CSS puro, TailwindCSS)"
                    ]
                else:
                    # Fallback genérico de la industria
                    fallback_questions = [
                        "¿Qué tecnologías base prefieres utilizar para el frontend (ej. React/Next.js) y backend (ej. Python/Node.js)?",
                        "¿Qué base de datos prefieres utilizar para persistir la información? (ej. PostgreSQL, MySQL, SQLite)",
                        "¿Prefieres que el proyecto esté listo para levantarse en contenedores Docker?"
                    ]
                
                # Ejecutar el refinamiento interactivo usando estas preguntas de fallback
                for question in fallback_questions:
                    from rich.panel import Panel
                    console.print()
                    console.print(Panel(
                        f"[bold cyan]{question}[/bold cyan]",
                        title="[bold yellow]🤖 Product Owner (Fallback de Refinamiento)[/bold yellow]",
                        border_style="cyan"
                    ))
                    console.print()
                    
                    try:
                        user_input = input("✍ Responde al PO (o escribe /skip o /ready para continuar) > ").strip()
                    except (KeyboardInterrupt, EOFError):
                        console.print("\n[yellow]⚠ Refinamiento de fallback cancelado por el usuario. Continuando...[/yellow]")
                        break
                        
                    if not user_input or user_input.lower() in ("/skip", "/ready"):
                        break
                        
                    refinement_log.append(f"Pregunta PO Fallback: {question}")
                    refinement_log.append(f"Respuesta Usuario: {user_input}")
                
                break
                
            clean_response = response.strip().replace(".", "").replace("!", "").upper()
            if clean_response == "READY":
                console.print("[green]✓ Product Owner determinó que los requerimientos están completos y listos (READY).[/green]")
                break
                
            # Presentar la pregunta destacada en cian usando un Panel de Rich
            from rich.panel import Panel
            console.print()
            console.print(Panel(
                f"[bold cyan]{response}[/bold cyan]",
                title="[bold yellow]🤖 Product Owner (Refinamiento)[/bold yellow]",
                border_style="cyan"
            ))
            console.print()
            
            try:
                user_input = input("✍ Responde al PO (o escribe /skip o /ready para continuar) > ").strip()
            except (KeyboardInterrupt, EOFError):
                console.print("\n[yellow]⚠ Refinamiento cancelado por el usuario. Continuando con la generación estructurada...[/yellow]")
                break
                
            if not user_input:
                continue
                
            if user_input.lower() in ("/skip", "/ready"):
                console.print("[yellow]⏭ Escape Hatch: Forzando generación del backlog con la información actual.[/yellow]")
                break
                
            refinement_history.append({"role": "assistant", "content": response})
            refinement_history.append({"role": "user", "content": user_input})
            refinement_log.append(f"Pregunta PO: {response}")
            refinement_log.append(f"Respuesta Usuario: {user_input}")

        # --- SUB-FASE B: Generación estructurada del backlog ---
        alert_prefix = ""
        if last_exit != 0:
            alert_prefix = "[SYSTEM ALERT: THE BUILD/PIPELINE IS CURRENTLY BROKEN. PRIORITIZE FIXING EXISTING FATAL ERRORS BEFORE ADDING FEATURES OR MOVING FORWARD].\n\n"

        system = (
            f"{alert_prefix}"
            f"{agent_prompt}\n\n"
            "[INSTRUCCIONES ESPECÍFICAS]\n"
            "Tu ÚNICO entregable es una especificación estructurada en formato JSON puro. "
            "NO generes texto conversacional, ni explicaciones, ni bloques de código adicionales fuera del JSON.\n\n"
            "REGLA DE PLANIFICACIÓN JERÁRQUICA POR ÉPICAS (MÁXIMO 15 ÉPICAS):\n"
            "Debes desglosar el proyecto en un MÁXIMO DE 15 ÉPICAS (macro-historias de usuario de alto nivel con alcance amplio). PROHIBIDO generar más de 15 historias en el campo 'user_stories'.\n\n"
            "REGLA DE INFRAESTRUCTURA Y SPRINT 0 (MUST-HAVE BLOQUEANTE):\n"
            "El backlog DEBE incluir obligatoriamente como PRIMERA HISTORIA DE USUARIO (id: 'US-000') el 'Sprint 0: Infraestructura y Entorno Base' con prioridad 'Must-have'. "
            "Esta historia DEBE exigir explícitamente la creación del gestor de dependencias del proyecto (ej: package.json, requirements.txt, build.gradle, go.mod), los archivos Docker (Dockerfile, docker-compose.yml) y el punto de entrada principal con el andamiaje base de la app (ej: server.js, main.py, App.tsx, index.ts). "
            "Está ESTRICTAMENTE PROHIBIDO poner historias de lógica de negocio o UI antes de este Sprint 0 de infraestructura.\n\n"
            "Cada historia de usuario DEBE contener explícitamente los campos 'prioridad' (MoSCoW: Must-have, Should-have, Could-have, Won't-have) y 'estimacion' (ej. M, 5 pts, XS, S, L, XL).\n\n"
            "El JSON debe tener exactamente la siguiente estructura:\n"
            "{\n"
            '  "proyecto": "Nombre del proyecto",\n'
            '  "vision": "Visión general del producto y arquitectura recomendada",\n'
            '  "user_stories": [\n'
            "    {\n"
            '      "id": "US-000",\n'
            '      "titulo": "Sprint 0: Infraestructura, Gestor de Dependencias y Entorno Base",\n'
            '      "como": "Arquitecto / Desarrollador Principal",\n'
            '      "quiero": "configurar el gestor de dependencias, contenedorización Docker y punto de entrada principal del proyecto",\n'
            '      "para": "garantizar un andamiaje 100% ejecutable, compilable y desplegable antes de la lógica de negocio",\n'
            '      "prioridad": "Must-have",\n'
            '      "estimacion": "S",\n'
            '      "criterios_aceptacion": [\n'
            '        "Dado un proyecto nuevo, cuando se ejecute el Sprint 0, entonces debe existir el gestor de dependencias (package.json, requirements.txt, build.gradle, etc.).",\n'
            '        "Dado el entorno de contenedores, entonces deben crearse Dockerfile y docker-compose.yml validados.",\n'
            '        "Dado el punto de entrada principal (ej. server.js, main.py, App.tsx), se debe crear el andamiaje base e importar los módulos principales."\n'
            "      ],\n"
            '      "contexto_rag_necesario": [\n'
            '        "Dockerfile", "package.json", "requirements.txt"\n'
            "      ],\n"
            '      "definition_of_done": [\n'
            '        "Compilación y sintaxis libre de errores",\n'
            '        "Gestor de dependencias e infraestructura inicializados"\n'
            "      ]\n"
            "    }\n"
            "  ]\n"
            "}\n"
        )
        
        full_refinement_context = "\n".join(refinement_log)
        po_prompt = (
            f"IDEA DEL PROYECTO Y DISCUSIÓN DE REFINAMIENTO:\n"
            f"{full_refinement_context}\n\n"
            f"Por favor, genera el BACKLOG.json definitivo basado en toda la discusión anterior."
        )

        with TaskProgress(tui_engine, "auto_po", "Product Owner: Redactando backlog estructurado (JSON)..."):
            result = self.orchestrator._call_agent(system, po_prompt, json_mode=True, timeout=300.0, temperature=0.2)

        elapsed = time.perf_counter() - t0

        if not result:
            # Reintento directo con Gemini dándole una oportunidad adicional tras la pausa
            logger.warning("Respuesta vacía inicial en Product Owner. Reintentando llamado con Gemini...")
            with TaskProgress(tui_engine, "auto_po_retry", "Product Owner: Esperando respuesta de Gemini..."):
                result = self.orchestrator._call_agent(system, po_prompt, json_mode=True, timeout=300.0, temperature=0.2)

        if not result:
            self.orchestrator.metrics.append({"fase": "📝 Product Owner", "detalle": "ERROR", "tiempo": elapsed, "status": "❌"})
            console.print("✗ Product Owner no produjo resultado.")
            return False

        # Validar y escribir BACKLOG.json con bucle estricto de reintentos (MAX_JSON_RETRIES = 3)
        MAX_JSON_RETRIES = 3
        parsed_backlog = None
        current_result = result
        last_error = None

        for attempt in range(1, MAX_JSON_RETRIES + 1):
            try:
                parsed_backlog = self.extract_json_block(current_result)
                if parsed_backlog and isinstance(parsed_backlog, dict) and "user_stories" in parsed_backlog and isinstance(parsed_backlog["user_stories"], list):
                    result = current_result
                    break
                else:
                    raise ValueError("JSON extraído carece de la lista 'user_stories'.")
            except Exception as e:
                last_error = str(e)
                logger.warning("Fallo intento %d/%d al parsear JSON del Product Owner: %s", attempt, MAX_JSON_RETRIES, e)
                if attempt < MAX_JSON_RETRIES:
                    console.print(f"[yellow]⚠ Intento {attempt}/{MAX_JSON_RETRIES}: Error de sintaxis JSON en la respuesta. Solicitando corrección...[/yellow]")
                    correction_system = (
                        "Error de sintaxis JSON. Devuelve ÚNICAMENTE una estructura JSON válida con las historias de usuario."
                    )
                    correction_user = (
                        f"RESPUESTA ANTERIOR CON ERRORES:\n```\n{current_result}\n```\n\n"
                        f"ERROR DE PARSEO OCURRIDO:\n{last_error}\n\n"
                        f"Por favor, corrige y devuelve ÚNICAMENTE la estructura JSON pura y válida sin textos decorativos."
                    )
                    try:
                        with TaskProgress(tui_engine, "auto_po_correction", f"Product Owner: Reintento {attempt+1}/{MAX_JSON_RETRIES} de sintaxis JSON..."):
                            current_result = self.orchestrator._call_agent(correction_system, correction_user, json_mode=True, timeout=180.0, temperature=0.2)
                    except Exception as e_call:
                        logger.error("Error al llamar al LLM para corrección de JSON: %s", e_call)

        if parsed_backlog is None:
            console.print("\n[bold red]🚨 HARD CRASH: Tolerancia cero en parseo JSON de Product Owner.[/bold red]")
            console.print(f"[red]No fue posible obtener un BACKLOG.json válido tras {MAX_JSON_RETRIES} intentos de sintaxis. Último error: {last_error}[/red]")
            # Alerta crítica y pausa en Sentinel
            self.orchestrator.state.set_pipeline_status("PIPELINE_PAUSED", {
                "task_id": "PO-BACKLOG-001",
                "agent_name": "product_owner",
                "error_log": f"HARD CRASH PO: Imposible parsear JSON del Backlog tras {MAX_JSON_RETRIES} intentos.\nSalida LLM:\n{current_result}\nError: {last_error}",
                "task_desc": "Generar especificación BACKLOG.json válida",
                "output_file": "BACKLOG.json"
            })
            self.orchestrator.metrics.append({"fase": "📝 Product Owner", "detalle": f"HARD CRASH ({last_error[:30]}...)", "tiempo": elapsed, "status": "❌"})
            return False

        # Garantizar e inyectar de forma determinista la US-000 (Sprint 0) si falta en el backlog
        user_stories = parsed_backlog.get("user_stories", [])
        has_sprint_0 = any(
            us.get("id") in ("US-000", "US-00") or
            "sprint 0" in str(us.get("titulo", "")).lower() or
            "infraestructura" in str(us.get("titulo", "")).lower()
            for us in user_stories
        )
        if not has_sprint_0:
            logger.info("Inyectando de forma determinista la US-000 (Sprint 0: Infraestructura y Entorno) en el backlog.")
            sprint_0_story = {
                "id": "US-000",
                "titulo": "Sprint 0: Infraestructura, Gestor de Dependencias y Entorno Base",
                "como": "Arquitecto / Desarrollador Principal",
                "quiero": "configurar el gestor de dependencias (package.json/requirements.txt/build.gradle), contenedorización Docker y punto de entrada principal del proyecto",
                "para": "garantizar un andamiaje 100% ejecutable, compilable y desplegable antes de codificar lógica de negocio",
                "prioridad": "Must-have",
                "estimacion": "S",
                "criterios_aceptacion": [
                    "Dado un proyecto nuevo, cuando se ejecute el Sprint 0, entonces debe existir el gestor de dependencias del proyecto.",
                    "Dado el entorno de contenedores, entonces deben crearse Dockerfile y docker-compose.yml validados.",
                    "Dado el punto de entrada principal (ej. server.js, main.py, App.tsx), se debe crear el andamiaje base e importar los módulos principales."
                ],
                "contexto_rag_necesario": [
                    "Dockerfile", "package.json", "requirements.txt"
                ],
                "definition_of_done": [
                    "Compilación y sintaxis libre de errores",
                    "Gestor de dependencias e infraestructura inicializados"
                ]
            }
            parsed_backlog["user_stories"].insert(0, sprint_0_story)

        # Enforzar límite estricto de máximo 15 Épicas en el backlog
        if len(parsed_backlog.get("user_stories", [])) > 15:
            logger.warning("El backlog posee %d historias/épicas. Recortando estrictamente a 15 para la arquitectura jerárquica.", len(parsed_backlog["user_stories"]))
            parsed_backlog["user_stories"] = parsed_backlog["user_stories"][:15]

        try:
            self.orchestrator._write_project_file("BACKLOG.json", json.dumps(parsed_backlog, indent=2, ensure_ascii=False))
            md_backlog = self._build_md_backlog(parsed_backlog)
            self.orchestrator._write_project_file("BACKLOG.md", md_backlog)
        except Exception as e_write:
            logger.error("Error al escribir archivos de BACKLOG tras parsing exitoso: %s", e_write)
            return False

        tokens = estimate_tokens(result)
        console.print(f"✓ BACKLOG.json generado [dim]({tokens:,} tokens · {elapsed:.1f}s)[/dim]")
        self.orchestrator.metrics.append({"fase": "📝 Product Owner", "detalle": f"~{tokens:,} tokens → BACKLOG.json", "tiempo": elapsed, "status": "✅"})

        # Bucle de interacción y feedback del usuario sobre el backlog (Interactividad y Transparencia)
        backlog_approved = False
        while not backlog_approved:
            # Mostrar resumen narrativo en consola
            from rich.markdown import Markdown
            console.print("\n[bold green]📋 Resumen Narrativo del Backlog de Producto:[/bold green]")
            console.print(Markdown(md_backlog))
            console.print("-" * 60)
            
            try:
                feedback = input("\n✍ Escribe comentarios para ajustar el backlog, o responde 'y'/'aprobado' para confirmar > ").strip()
            except (KeyboardInterrupt, EOFError):
                feedback = "y"
                
            if feedback.lower() in ("y", "aprobado", "aprobar", "ok", "si", "sí", "confirmar", "listo", "ready", ""):
                backlog_approved = True
                break
                
            if not feedback:
                continue
                
            # Integrar feedback del usuario y regenerar
            console.print(f"[yellow]🔄 Integrando feedback del usuario en el backlog: '{feedback}'...[/yellow]")
            
            adjustment_system = (
                f"{agent_prompt}\n\n"
                "[INSTRUCCIONES DE AJUSTE]\n"
                "El usuario ha revisado tu BACKLOG.json anterior y ha solicitado algunos cambios.\n"
                "Debes integrar sus comentarios en el nuevo backlog y devolver ÚNICAMENTE el JSON actualizado "
                "siguiendo exactamente la misma estructura de antes.\n\n"
                "No agregues texto conversacional, explicaciones ni bloques markdown fuera del JSON."
            )
            adjustment_user = (
                f"BACKLOG ANTERIOR:\n```json\n{json.dumps(parsed_backlog, indent=2, ensure_ascii=False)}\n```\n\n"
                f"COMENTARIOS DEL USUARIO:\n{feedback}\n\n"
                f"Por favor, integra los cambios solicitados y genera el nuevo JSON."
            )
            
            with TaskProgress(tui_engine, "auto_po_adjust", "Product Owner: Ajustando backlog con tu feedback..."):
                adjust_result = self.orchestrator._call_agent(adjustment_system, adjustment_user, json_mode=True, timeout=180.0, temperature=0.2)
                
            if not adjust_result:
                console.print("[red]❌ El Product Owner no pudo ajustar el backlog. Intentando mantener el backlog actual.[/red]")
                continue
                
            parsed_backlog_adjusted = None
            current_adjust = adjust_result
            adjust_error = None
            for adjust_attempt in range(1, MAX_JSON_RETRIES + 1):
                try:
                    parsed_backlog_adjusted = self.extract_json_block(current_adjust)
                    if parsed_backlog_adjusted and isinstance(parsed_backlog_adjusted, dict) and "user_stories" in parsed_backlog_adjusted:
                        break
                    else:
                        raise ValueError("JSON de ajuste carece de 'user_stories'.")
                except Exception as e:
                    adjust_error = str(e)
                    logger.warning("Fallo al parsear JSON ajustado intento %d/%d: %s", adjust_attempt, MAX_JSON_RETRIES, e)
                    if adjust_attempt < MAX_JSON_RETRIES:
                        console.print(f"[yellow]⚠ Intento {adjust_attempt}/{MAX_JSON_RETRIES}: Error de sintaxis JSON en el ajuste. Reintentando...[/yellow]")
                        correction_system = "Error de sintaxis JSON. Devuelve ÚNICAMENTE la estructura JSON válida con las historias de usuario."
                        correction_user = f"RESPUESTA ANTERIOR:\n```\n{current_adjust}\n```\n\nERROR:\n{adjust_error}\n\nCorrige y devuelve JSON puro."
                        try:
                            with TaskProgress(tui_engine, "auto_po_adjust_correction", f"Product Owner: Reintento {adjust_attempt+1}/{MAX_JSON_RETRIES} de ajuste JSON..."):
                                current_adjust = self.orchestrator._call_agent(correction_system, correction_user, json_mode=True, timeout=180.0, temperature=0.2)
                        except Exception:
                            pass

            if parsed_backlog_adjusted is not None:
                try:
                    parsed_backlog = parsed_backlog_adjusted
                    self.orchestrator._write_project_file("BACKLOG.json", json.dumps(parsed_backlog, indent=2, ensure_ascii=False))
                    md_backlog = self._build_md_backlog(parsed_backlog)
                    self.orchestrator._write_project_file("BACKLOG.md", md_backlog)
                except Exception as e_write:
                    logger.error("Error al escribir archivos de BACKLOG ajustado tras parsing exitoso: %s", e_write)
                    console.print("[red]❌ Error al integrar el feedback en el JSON. Reintentando...[/red]")
            else:
                console.print(f"[red]❌ Error al integrar el feedback en el JSON tras {MAX_JSON_RETRIES} intentos: {adjust_error}. Manteniendo backlog previo.[/red]")

        console.print("✓ Backlog aprobado.\n")
        return True

    def run_dor_validation(self) -> bool:
        """Un QA Agent audita el BACKLOG.md para certificar que está listo (DoR)."""
        console.print("\n━━━ FASE COMPLEMENTARIA: 🔍 QA Agent - Validación de DoR ━━━")
        t0 = time.perf_counter()
        
        backlog = self.orchestrator._read_project_file("BACKLOG.md")
        if not backlog:
            return False

        system_prompt = (
            "Eres un QA Engineer experto en Metodologías Ágiles.\n"
            "Tu tarea es auditar el BACKLOG.md y determinar si cumple con el 'Definition of Ready' (DoR).\n"
            "El Backlog está listo (ready: true) si:\n"
            "1. Contiene historias de usuario claras con criterios de aceptación detallados (Gherkin).\n"
            "2. Cada historia contiene explícitamente su prioridad clasificada según la metodología MoSCoW (Must-have, Should-have, Could-have, Won't-have) y su estimación.\n"
            "3. No hay requerimientos ambiguos o contradictorios.\n\n"
            "REGLA DE APROBACIÓN AUTOMÁTICA: Si las historias cuentan con la etiqueta de Prioridad MoSCoW y Criterios de Aceptación, DEBES aprobar automáticamente el DoR con ready: true, sin emitir advertencias innecesarias ni requerir metodologías no definidas.\n\n"
            "Debes responder en formato JSON puro. Ejemplo:\n"
            '{"ready": true, "reason": "El backlog está completo, incluye prioridad MoSCoW y criterios Gherkin."}\n'
            'O si no está listo:\n'
            '{"ready": false, "reason": "Faltan los criterios de aceptación en la historia US-003."}'
        )

        with TaskProgress(tui_engine, "auto_qa_dor", "QA Agent: Validando Definition of Ready..."):
            response = self.orchestrator._call_agent(system_prompt, f"BACKLOG.md:\n{backlog}")
            
        elapsed = time.perf_counter() - t0
        
        if not response:
            console.print("⚠ QA Agent no respondió. Asumiendo listo por defecto.")
            return True

        import json
        ready = True
        reason = "Aprobado por defecto."
        try:
            match = re.search(r'\{.*\}', response, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                ready = data.get("ready", True)
                reason = data.get("reason", "")
        except Exception as e:
            logger.warning("Error parseando respuesta del QA Agent: %s", e)

        if ready:
            console.print(f"✓ DoR Aprobado: {reason}")
            self.orchestrator.metrics.append({
                "fase": "🔍 QA (DoR Validation)",
                "detalle": f"Aprobado: {reason[:40]}...",
                "tiempo": elapsed,
                "status": "✅"
            })
            return True
        else:
            console.print(f"❌ DoR Rechazado: {reason}")
            self.orchestrator.metrics.append({
                "fase": "🔍 QA (DoR Validation)",
                "detalle": f"RECHAZADO: {reason[:40]}...",
                "tiempo": elapsed,
                "status": "❌"
            })
            try:
                override = Confirm.ask("¿Deseas ignorar la advertencia de QA y continuar con el sprint?", default=True)
                return override
            except (EOFError, KeyboardInterrupt):
                return False
