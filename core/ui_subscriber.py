"""core/ui_subscriber.py — Suscriptor visual CLI para el EventBus de Jellyfish OS.

Escucha eventos del EventBus y los renderiza en la terminal nativa Linux
usando Rich Console / TUI, manteniendo la compatibilidad 100% con la interfaz previa.
"""

import logging
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

from core.event_bus import event_bus, EventType, Event

logger = logging.getLogger("jellyfish.ui_subscriber")
console = Console()


class CLIEventSubscriber:
    """Suscriptor oficial de la interfaz CLI que reacciona a eventos del EventBus."""

    def __init__(self, state=None):
        self.state = state
        self.registered = False

    def register(self) -> None:
        """Registra los handlers visuales en el EventBus global."""
        if self.registered:
            return
        event_bus.subscribe_all(self._handle_event)
        self.registered = True
        logger.info("CLIEventSubscriber registrado exitosamente en el EventBus.")

    def unregister(self) -> None:
        """Remueve los handlers visuales del EventBus."""
        if not self.registered:
            return
        event_bus.unsubscribe(EventType.SYSTEM_BOOT, self._handle_event)
        self.registered = False

    def _handle_event(self, event: Event) -> None:
        """Despacha cada evento hacia el renderizador visual correspondiente."""
        p = event.payload
        et = event.type

        if et == EventType.TASK_STARTED:
            task_num = p.get("task_num", "?")
            total_tasks = p.get("total_tasks", "?")
            task_id = p.get("task_id", "")
            task_retries = p.get("task_retries", 0)
            max_retries = p.get("max_retries", 3)
            task_desc = p.get("task_desc", "")
            agent_name = p.get("agent_name", "")
            output_file = p.get("output_file", "")

            console.print(
                f"[bold white]  [{task_num}/{total_tasks}] {task_id} (Intento {task_retries + 1}/{max_retries}):[/bold white] "
                f"{task_desc[:60]}{'...' if len(task_desc) > 60 else ''}"
            )
            console.print(f"[dim]       → @{agent_name} → {output_file}[/dim]")

        elif et == EventType.TASK_COMPLETED:
            task_id = p.get("task_id", "")
            reason = p.get("reason", "Aprobado por DoD")
            console.print(f"       ✓ DoD Aprobado ({task_id}): {reason}")

        elif et == EventType.TASK_BLOCKED:
            task_id = p.get("task_id", "")
            missing_dep = p.get("missing_dep", "")
            console.print(
                f"       ⚠️ [TAREA BLOQUEADA] {task_id}: Bloqueada esperando a dependencia '{missing_dep}'. "
                f"Notificando al Scrum Master."
            )

        elif et == EventType.TASK_FAILED:
            task_id = p.get("task_id", "")
            max_retries = p.get("max_retries", 3)
            error_log = p.get("error_log", "")
            console.print(f"\n❌ [BLOQUEADO] La tarea {task_id} ha fallado {max_retries} veces consecutivas.")
            console.print(f"       Último error registrado: {error_log[:150]}...")

        elif et == EventType.SENTINEL_ALERT:
            task_id = p.get("task_id", "Desconocido")
            agent_name = p.get("agent_name", "Desconocido")
            task_desc = p.get("task_desc", "Sin descripción.")
            output_file = p.get("output_file", "")
            error_log = p.get("error_log", "")

            console.print("\n" + "=" * 80)
            console.print(Panel(
                Markdown(
                    f"### 🛡️ @Sentinel — Alerta de Interrupción del Pipeline (SIP)\n\n"
                    f"**Agente Asignado:** @{agent_name}\n"
                    f"**ID Tarea:** {task_id}\n"
                    f"**Descripción:** {task_desc}\n"
                    f"**Entregable:** `{output_file}`\n\n"
                    f"---"
                    f"#### 🔍 LOG CORTO DEL ERROR (Los 3 intentos fallaron):\n"
                    f"```\n{error_log[:1500] if len(error_log) > 1500 else error_log}\n```"
                ),
                title="[bold red]🚨 SENTINEL INTERACTIVE PAUSE 🚨[/bold red]",
                border_style="red"
            ))

        elif et == EventType.ENVIRONMENT_BLOCKING:
            missing = p.get("missing_tools", [])
            req_msg = p.get("message", "")
            console.print(Panel(
                Markdown(
                    f"### 🛑 [IMPEDIMENTO CRÍTICO DE ENTORNO]\n\n"
                    f"El proyecto requiere las siguientes herramientas en el sistema host que **NO** están disponibles:\n\n"
                    + "\n".join(f"- ❌ `{tool}`" for tool in missing) + "\n\n"
                    f"**Detalle:** {req_msg}\n\n"
                    f"Por favor, instala los binarios faltantes en el sistema y vuelve a ejecutar."
                ),
                title="[bold red]PAUSA DE PLANIFICACIÓN[/bold red]",
                border_style="red"
            ))

        elif et == EventType.AGENT_STATUS_CHANGE:
            agent = p.get("agent", "")
            status = p.get("status", "")
            if self.state and hasattr(self.state, "agent_statuses") and agent in self.state.agent_statuses:
                self.state.agent_statuses[agent] = status

        elif et == EventType.ERROR_CRITICAL:
            msg = p.get("message", "Error no especificado")
            console.print(f"[red]❌ Error Crítico: {msg}[/red]")


# Instancia global del suscriptor CLI
_cli_subscriber = CLIEventSubscriber()


def register_cli_subscriber(state=None) -> CLIEventSubscriber:
    """Registra el suscriptor CLI en el EventBus pasándole la instancia de estado."""
    if state:
        _cli_subscriber.state = state
    _cli_subscriber.register()
    return _cli_subscriber
