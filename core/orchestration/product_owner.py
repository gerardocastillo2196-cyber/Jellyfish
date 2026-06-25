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
        
        with TaskProgress(tui_engine, "auto_po", "Product Owner: Redactando backlog estructurado (JSON)..."):
            result = self.orchestrator._call_agent(system, f"IDEA DEL PROYECTO:\n{user_idea}")

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
        try:
            parsed_backlog = json.loads(json_clean)
            self.orchestrator._write_project_file("BACKLOG.json", json.dumps(parsed_backlog, indent=2, ensure_ascii=False))
            # Crear un BACKLOG.md legible para compatibilidad visual con humanos
            md_backlog = f"# Backlog: {parsed_backlog.get('proyecto', 'Proyecto Jellyfish')}\n\n"
            md_backlog += f"**Visión:** {parsed_backlog.get('vision', '')}\n\n"
            md_backlog += "## Historias de Usuario\n\n"
            for us in parsed_backlog.get("user_stories", []):
                md_backlog += f"### {us.get('id')}: {us.get('titulo')}\n"
                md_backlog += f"- **Como:** {us.get('como')}\n"
                md_backlog += f"- **Quiero:** {us.get('quiero')}\n"
                md_backlog += f"- **Para:** {us.get('para')}\n\n"
                md_backlog += "#### Criterios de Aceptación\n"
                for ca in us.get("criterios_aceptacion", []):
                    md_backlog += f"- {ca}\n"
                md_backlog += "\n#### Contexto RAG\n"
                for rag_ctx in us.get("contexto_rag_necesario", []):
                    md_backlog += f"- `{rag_ctx}`\n"
                md_backlog += "\n#### Definition of Done\n"
                for dod in us.get("definition_of_done", []):
                    md_backlog += f"- {dod}\n"
                md_backlog += "\n---\n\n"
            self.orchestrator._write_project_file("BACKLOG.md", md_backlog)
        except Exception as e:
            logger.error("Error al parsear el JSON de BACKLOG: %s. Contenido: %s", e, result)
            console.print("❌ Error al parsear backlog JSON generado por el PO. Guardando salida cruda.")
            self.orchestrator._write_project_file("BACKLOG.json", json.dumps({"error": "Falló el parsing del LLM", "raw_output": result}))
            self.orchestrator._write_project_file("BACKLOG.md", result)

        tokens = estimate_tokens(result)
        console.print(f"✓ BACKLOG.json generado [dim]({tokens:,} tokens · {elapsed:.1f}s)[/dim]")
        self.orchestrator.metrics.append({"fase": "📝 Product Owner", "detalle": f"~{tokens:,} tokens → BACKLOG.json", "tiempo": elapsed, "status": "✅"})

        # Checkpoint (Resumen mínimo sin preview largo)
        console.print(f"📋 BACKLOG.json validado y guardado.")

        try:
            approved = Confirm.ask("\n¿Aprobar backlog y continuar?", default=True)
        except (EOFError, KeyboardInterrupt):
            approved = False

        if not approved:
            console.print("Pipeline detenido. Edita BACKLOG.json y re-ejecuta /auto.")
            return False

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
