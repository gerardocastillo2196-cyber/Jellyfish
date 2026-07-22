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
                else:
                    return False
            except (EOFError, KeyboardInterrupt):
                return False

        # --- SUB-FASE A: Refinamiento Interactivo ---
        refinement_system = (
            f"Eres @product_owner, el Product Owner del equipo de desarrollo.\n"
            f"Tu rol en este momento es refinar e indagar activamente sobre la idea del usuario. "
            f"Tu meta final es redactar un Backlog completo con al menos 4 Historias de Usuario priorizadas con MoSCoW "
            f"y con criterios de aceptación claros.\n\n"
            f"REGLA CRÍTICA: Evalúa si la información actual es suficiente para redactar esas 4 Historias de Usuario sin inventar o suponer datos clave (ej. stack, lógica, flujos).\n"
            f"- Si la información es INSUFICIENTE: Formula exactamente una pregunta clara, directa y concisa para aclarar los requerimientos. NO generes el backlog, NO respondas con introducciones largas ni saludos. Ve al grano.\n"
            f"- Si la información es SUFICIENTE para redactar las 4 US y los criterios: Responde ÚNICAMENTE con la palabra 'READY'. Ninguna otra palabra o explicación está permitida. Solo escribe 'READY'."
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
                    model=self.orchestrator.state.model
                )
            
            if not response:
                console.print("[yellow]⚠ El Product Owner no respondió. Saltando refinamiento.[/yellow]")
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
            "El JSON debe tener exactamente la siguiente estructura:\n"
            "{\n"
            '  "proyecto": "Nombre del proyecto",\n'
            '  "vision": "Visión general del producto y arquitectura recomendada",\n'
            '  "user_stories": [\n'
            "    {\n"
            '      "id": "US-001",\n'
            '      "titulo": "Título de la Historia",\n'
            '      "como": "Rol del usuario",\n'
            '      "quiero": "Acción deseada",\n'
            '      "para": "Beneficio esperado",\n'
            '      "criterios_aceptacion": [\n'
            '        "Dado que..., cuando..., entonces..."\n'
            "      ],\n"
            '      "contexto_rag_necesario": [\n'
            '        "Ruta sugerida de archivo o componente de referencia"\n'
            "      ],\n"
            '      "definition_of_done": [\n'
            '        "Criterio de DoD 1 (ej: compila con éxito)",\n'
            '        "Criterio de DoD 2 (ej: cumple guardrails de seguridad)"\n'
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
            result = self.orchestrator._call_agent(system, po_prompt)

        elapsed = time.perf_counter() - t0

        if not result:
            self.orchestrator.metrics.append({"fase": "📝 Product Owner", "detalle": "ERROR", "tiempo": elapsed, "status": "❌"})
            console.print("✗ Product Owner no produjo resultado.")
            return False

        # Extraer JSON del bloque de código si está envuelto en ```json ... ```
        json_clean = result.strip()
        match = re.search(r'\{.*\}', json_clean, re.DOTALL)
        if match:
            json_clean = match.group(0)

        # Validar y escribir BACKLOG.json
        # Validar y escribir BACKLOG.json
        try:
            parsed_backlog = json.loads(json_clean)
            self.orchestrator._write_project_file("BACKLOG.json", json.dumps(parsed_backlog, indent=2, ensure_ascii=False))
            # Crear un BACKLOG.md legible para compatibilidad visual con humanos
            def _build_md_backlog(backlog_dict: dict) -> str:
                md = f"# Backlog: {backlog_dict.get('proyecto', 'Proyecto Jellyfish')}\n\n"
                md += f"**Visión:** {backlog_dict.get('vision', '')}\n\n"
                md += "## Historias de Usuario\n\n"
                for us in backlog_dict.get("user_stories", []):
                    md += f"### {us.get('id')}: {us.get('titulo')}\n"
                    md += f"- **Como:** {us.get('como')}\n"
                    md += f"- **Quiero:** {us.get('quiero')}\n"
                    md += f"- **Para:** {us.get('para')}\n"
                    if "prioridad" in us:
                        md += f"- **Prioridad (MoSCoW):** {us.get('prioridad')}\n"
                    elif "priority" in us:
                        md += f"- **Prioridad (MoSCoW):** {us.get('priority')}\n"
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
            
            md_backlog = _build_md_backlog(parsed_backlog)
            self.orchestrator._write_project_file("BACKLOG.md", md_backlog)
        except Exception as e:
            logger.error("Error al parsear el JSON de BACKLOG: %s. Contenido: %s", e, result)
            console.print("❌ Error al parsear backlog JSON generado por el PO. Guardando salida cruda.")
            self.orchestrator._write_project_file("BACKLOG.json", json.dumps({"error": "Falló el parsing del LLM", "raw_output": result}))
            self.orchestrator._write_project_file("BACKLOG.md", result)
            parsed_backlog = {"error": "Falló el parsing del LLM", "raw_output": result, "user_stories": []}
            md_backlog = result

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
                
            if feedback.lower() in ("y", "aprobado"):
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
                adjust_result = self.orchestrator._call_agent(adjustment_system, adjustment_user)
                
            if not adjust_result:
                console.print("[red]❌ El Product Owner no pudo ajustar el backlog. Intentando mantener el backlog actual.[/red]")
                continue
                
            json_clean = adjust_result.strip()
            match = re.search(r'\{.*\}', json_clean, re.DOTALL)
            if match:
                json_clean = match.group(0)
                
            try:
                parsed_backlog = json.loads(json_clean)
                self.orchestrator._write_project_file("BACKLOG.json", json.dumps(parsed_backlog, indent=2, ensure_ascii=False))
                md_backlog = _build_md_backlog(parsed_backlog)
                self.orchestrator._write_project_file("BACKLOG.md", md_backlog)
            except Exception as e:
                logger.error("Error al parsear el JSON de BACKLOG ajustado: %s", e)
                console.print("[red]❌ Error al integrar el feedback en el JSON. Reintentando...[/red]")

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
            "El Backlog está listo si:\n"
            "1. Contiene al menos 4 historias de usuario claras o especificaciones suficientes.\n"
            "2. Cada historia contiene criterios de aceptación detallados y prioritarios (MoSCoW).\n"
            "3. No hay requerimientos ambiguos o contradictorios.\n\n"
            "Debes responder en formato JSON puro. Ejemplo:\n"
            '{"ready": true, "reason": "El backlog está completo e incluye criterios Gherkin."}\n'
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
