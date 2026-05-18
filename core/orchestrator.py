import os
import json
import re
import time
import logging
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.status import Status
from rich.table import Table
from rich.text import Text

from core.state import JellyfishState
from core.rag_coder import CodeKnowledgeBase, _FRAG_OPEN
from core.llm_engine import _call_llm_silent, _stream_request

# Sprint 2.4 — Regex dinámico que usa el prefijo UUID blindado de rag_coder
_FRAG_PREFIX = re.escape(_FRAG_OPEN.split(" ")[0])  # e.g. "<FRAG_A1B2C3D4E5F6"
_SOURCE_RE = re.compile(rf'{_FRAG_PREFIX}\s+source="([^"]+)"')

logger = logging.getLogger("jellyfish.orchestrator")
console = Console()


def _parse_plan_safe(text: str) -> list[dict]:
    """Parseo robusto y multi-formato del plan JSON generado por el LLM.

    Sprint 1.1 — Soporta 4 variantes de respuesta comunes del modelo:
      - Array plano: [{"query": "..."}]
      - Objeto envolvente: {"steps": [...]}
      - Array dentro de markdown: ```json\n[...]\n```
      - Falla total: retorna lista vacía para que el orquestador use fallback.
    """
    md_match = re.search(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL)
    candidate = md_match.group(1).strip() if md_match else text.strip()

    for attempt in [candidate, text.strip()]:
        try:
            data = json.loads(attempt)
            if isinstance(data, list):
                return [s for s in data if isinstance(s, dict) and "query" in s]
            if isinstance(data, dict):
                for key in ("steps", "plan", "queries", "tasks", "searches"):
                    if key in data and isinstance(data[key], list):
                        return [s for s in data[key] if isinstance(s, dict) and "query" in s]
        except (json.JSONDecodeError, ValueError):
            pass

    array_match = re.search(r"\[[\s\S]*?\]", candidate)
    if array_match:
        try:
            data = json.loads(array_match.group(0))
            if isinstance(data, list):
                return [s for s in data if isinstance(s, dict) and "query" in s]
        except (json.JSONDecodeError, ValueError):
            pass

    logger.warning("No se pudo parsear el plan del orquestador. Texto: %.200s", text)
    return []


class ResearchOrchestrator:
    """Orquestador Multi-Agente para Jellyfish OS — Sprint 3 Edition.

    Sprints acumulados:
    - 1.1: Parseo JSON robusto multi-formato.
    - 1.2: Subagentes en modo silencioso.
    - 1.3: Árbol de progreso via rich.Status.
    - 1.5: Limpieza automática del plan temporal.
    - 2.4: Extracción de fuentes con UUID blindado.
    - 3.2: Status tree enriquecido con tiempos por fase.
    - 3.4: Tabla de resumen al final del pipeline.
    """

    def __init__(self, state: JellyfishState, rag: CodeKnowledgeBase):
        self.state = state
        self.rag = rag
        self.memory_dir = os.path.join(self.state.agency_dir, "memory")
        os.makedirs(self.memory_dir, exist_ok=True)
        self._plan_file = os.path.join(self.memory_dir, "current_plan.json")

    def _generate_silent(self, system_prompt: str, user_prompt: str) -> str:
        """Llama al LLM sin streaming visible (subagentes internos)."""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        response = _call_llm_silent(self.state, messages)
        return response if response else ""

    def _generate_visible(self, system_prompt: str, user_prompt: str, label: str) -> str:
        """Llama al LLM CON streaming visible — solo para el reporte final."""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        response = _stream_request(self.state, messages, label)
        return response if response else ""

    def execute_task(self, user_query: str) -> str:
        """Ejecuta el flujo multi-agente completo con UI de progreso y tabla de resumen.

        Sprint 3.2 — Muestra tiempo de cada fase en el Status.
        Sprint 3.4 — Imprime una rich.Table al terminar con métricas del pipeline.
        """
        console.print(
            "\n[bold purple]🧠 Jellyfish — Orquestador de Investigación[/bold purple]"
        )

        # Registro de métricas por fase (Sprint 3.4)
        metrics: list[dict] = []
        total_start = time.perf_counter()

        # --- FASE 1: Planificación ---
        t0 = time.perf_counter()
        with Status("[bold blue]🗺  Lead Agent: Diseñando plan...[/bold blue]", console=console):
            plan_system = (
                "Eres el Lead Agent de investigación de código. "
                "Desglosa la consulta en 1 a 3 pasos de búsqueda. "
                "Responde ÚNICAMENTE con JSON válido, sin texto adicional. "
                'Formato exacto: [{"query": "descripción del paso"}]'
            )
            plan_text = self._generate_silent(plan_system, user_query)

        steps = _parse_plan_safe(plan_text)
        if not steps:
            console.print("[dim]⚠ Plan no parseable, usando consulta original como paso único.[/dim]")
            steps = [{"query": user_query}]

        phase1_time = time.perf_counter() - t0
        metrics.append({
            "fase": "🗺  Lead Planner",
            "detalle": f"{len(steps)} paso(s) planificados",
            "tiempo": phase1_time,
        })

        try:
            with open(self._plan_file, "w", encoding="utf-8") as f:
                json.dump({"query": user_query, "steps": steps}, f, indent=2)
        except OSError as e:
            logger.warning("No se pudo guardar el plan en disco: %s", e)

        console.print(f"[dim]   Plan: {len(steps)} paso(s) identificados.[/dim]")

        # --- FASE 2: Subagentes de Búsqueda ---
        findings: list[str] = []
        rag_sources_used: set[str] = set()

        for i, step in enumerate(steps):
            query = step.get("query", user_query)
            label_q = query[:55] + "..." if len(query) > 55 else query
            t0 = time.perf_counter()

            with Status(
                f"[bold blue]🔍 Search Subagent {i+1}/{len(steps)}: {label_q}[/bold blue]",
                console=console,
            ):
                rag_context = self.rag.query_code(query) if self.rag.is_active else ""

                if not rag_context:
                    findings.append(f"[{i+1}] '{query}': No se encontró código relevante en RAG.")
                    sub_result = "(sin resultados RAG)"
                else:
                    sources = _SOURCE_RE.findall(rag_context)
                    rag_sources_used.update(sources)

                    search_system = (
                        "Eres un Search Subagent de análisis de código. "
                        "Resume en 2-4 líneas cómo el contexto RAG responde a la consulta. "
                        "Sé técnico y preciso. No repitas el código completo."
                    )
                    sub_result = self._generate_silent(
                        search_system,
                        f"Consulta: '{query}'\n\nContexto RAG:\n{rag_context[:4000]}"
                    )
                    findings.append(f"[{i+1}] Hallazgos sobre '{query}':\n{sub_result}")

            sub_time = time.perf_counter() - t0
            # Sprint 3.2 — Calcular longitud de hallazgos para la tabla
            tokens_est = len(sub_result) // 4
            metrics.append({
                "fase": f"🔍 Search Agent {i+1}",
                "detalle": f"~{tokens_est} tokens · {len(rag_sources_used)} fuentes",
                "tiempo": sub_time,
            })

        # --- FASE 3: Síntesis Final ---
        t0 = time.perf_counter()
        console.print("\n[bold blue]✍  Lead Agent: Redactando reporte final...[/bold blue]")
        synth_system = (
            "Eres el Lead Agent. Recibiste los hallazgos de tus subagentes de búsqueda. "
            "Redacta un reporte final cohesivo y profesional. "
            "Fundamenta cada afirmación en los hallazgos. No inventes código nuevo."
        )
        draft_report = self._generate_visible(
            synth_system,
            f"Consulta Original: {user_query}\n\n" + "\n\n".join(findings),
            "synthesizer",
        )
        phase3_time = time.perf_counter() - t0
        metrics.append({
            "fase": "✍  Lead Synthesizer",
            "detalle": f"~{len(draft_report) // 4} tokens generados",
            "tiempo": phase3_time,
        })

        # --- FASE 4: Citaciones ---
        t0 = time.perf_counter()
        with Status("[bold blue]📚 Citation Agent: Validando fuentes...[/bold blue]", console=console):
            final_report = self._apply_heuristic_citations(draft_report, rag_sources_used)
        phase4_time = time.perf_counter() - t0
        metrics.append({
            "fase": "📚 Citation Agent",
            "detalle": f"{len(rag_sources_used)} fuentes analizadas",
            "tiempo": phase4_time,
        })

        # Sprint 1.5: Limpiar plan temporal
        try:
            if os.path.exists(self._plan_file):
                os.remove(self._plan_file)
        except OSError as e:
            logger.warning("No se pudo eliminar el plan temporal: %s", e)

        # Sprint 3.4 — Tabla de resumen del pipeline
        total_time = time.perf_counter() - total_start
        self._print_summary_table(metrics, total_time)

        return final_report

    def _print_summary_table(self, metrics: list[dict], total_time: float) -> None:
        """Imprime una tabla rich con las métricas de cada fase del pipeline.

        Sprint 3.4 — Feedback visual claro de cuánto tardó cada agente y cuántos tokens generó.
        """
        table = Table(
            title="📊 Resumen del Pipeline de Investigación",
            show_header=True,
            header_style="bold cyan",
            border_style="bright_black",
            show_footer=True,
        )
        table.add_column("Agente / Fase", style="bold", min_width=22)
        table.add_column("Detalle", style="dim", min_width=28)
        table.add_column("Duración", justify="right", min_width=10, footer=f"{total_time:.1f}s total")

        for m in metrics:
            secs = m["tiempo"]
            # Colorear según duración
            if secs < 5:
                dur_str = f"[green]{secs:.1f}s[/green]"
            elif secs < 30:
                dur_str = f"[yellow]{secs:.1f}s[/yellow]"
            else:
                dur_str = f"[red]{secs:.1f}s[/red]"

            table.add_row(m["fase"], m["detalle"], Text.from_markup(dur_str))

        console.print()
        console.print(table)
        console.print()

    def _apply_heuristic_citations(self, text: str, sources: set[str]) -> str:
        """Añade un bloque de fuentes verificadas al pie del reporte."""
        if not sources or not text:
            return text

        actual_citations: set[str] = set()
        for source in sources:
            basename = os.path.basename(source)
            if basename in text or source in text:
                actual_citations.add(source)

        if not actual_citations:
            return text

        citation_block = "\n\n---\n**📚 Fuentes Verificadas (RAG):**\n"
        for src in sorted(actual_citations):
            abs_path = os.path.abspath(src)
            citation_block += f"- [{src}](file://{abs_path})\n"

        return text + citation_block
