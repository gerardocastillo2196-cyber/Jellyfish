import os
import re
import sys
import threading
import logging
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.prompt import Confirm
from rich.table import Table
from rich.spinner import Spinner
from rich.live import Live
from prompt_toolkit import PromptSession

from core.state import (
    AGENCY_DIR,
    PROVIDER_CONFIGS,
    PROVIDER_ALIASES,
    supported_provider_names,
)
from core.terminal import run_terminal_command
from core.ui import interactive_picker, file_browser, print_panel, print_code, console as ui_console
from core.tui import tui_engine, TaskProgress

logger = logging.getLogger("jellyfish.crud")
console = Console()
_PROJECT_GUIDE_SHOWN = False

# Caracteres peligrosos para sanitización de nombres de archivos
_UNSAFE_FILENAME_RE = re.compile(r'[^\w\s\-.]', re.UNICODE)


def _sanitize_name(name: str) -> str:
    """Sanitiza un nombre para uso seguro como nombre de archivo.

    Elimina caracteres especiales que podrían causar problemas
    en el sistema de archivos o inyección en Markdown.
    """
    clean = _UNSAFE_FILENAME_RE.sub('', name).strip()
    # Reemplazar espacios por guiones bajos
    clean = clean.replace(' ', '_')
    return clean.lower() if clean else ""


def detailed_interview(type_key: str) -> str | None:
    """Entrevista guiada para crear un agente o habilidad.

    Args:
        type_key: "agents" o "skills".

    Returns:
        Nombre del elemento creado, o None si se canceló.
    """
    session = PromptSession()

    if type_key == "agents":
        console.print(Panel("🎭 FORJA AVANZADA DE AGENTE", border_style="green"))
        raw_name = session.prompt("1. Alias (ej. arquitecto_software): ").strip()
        name = _sanitize_name(raw_name)
        if not name:
            console.print("[yellow]⚠ Nombre inválido o vacío.[/yellow]")
            return None
        rol = session.prompt("2. Rol Principal: ").strip()
        contexto = session.prompt("3. Contexto Operativo: ").strip()
        tono = session.prompt("4. Tono: ").strip()
        conocimiento = session.prompt("5. Expertise: ").strip()
        regla = session.prompt("6. Regla Inquebrantable: ").strip()
        ejemplo = session.prompt("7. Ejemplo de Interacción [Opcional]: ").strip()

        content = (
            f"# AGENTE: @{name.upper()}\n"
            f"**ROL:** {rol}\n"
            f"**CONTEXTO:** {contexto}\n"
            f"**TONO:** {tono}\n"
            f"**EXPERTISE:** {conocimiento}\n"
            f"**REGLA:** {regla}\n"
        )
        if ejemplo:
            content += f"\n**EJEMPLO:**\n{ejemplo}\n"
    else:
        console.print(Panel("🛠️ FORJA AVANZADA DE HABILIDAD", border_style="cyan"))
        raw_name = session.prompt("1. Nombre: ").strip()
        name = _sanitize_name(raw_name)
        if not name:
            console.print("[yellow]⚠ Nombre inválido o vacío.[/yellow]")
            return None
        obj = session.prompt("2. Propósito: ").strip()
        trigger = session.prompt("3. Activación (Trigger): ").strip()
        deps = session.prompt("4. Dependencias Linux: ").strip()
        comando = session.prompt("5. Comando(s) Bash: ").strip()
        errores = session.prompt("6. Manejo de Errores: ").strip()

        content = (
            f"# HABILIDAD: @{name.upper()}\n"
            f"**OBJETIVO:** {obj}\n"
            f"**TRIGGER:** {trigger}\n"
            f"**DEPENDENCIAS:** {deps}\n"
            f"**INSTRUCCIÓN:** Genera este bloque:\n\n"
            f"```bash\n{comando}\n```\n\n"
            f"**ERRORES:** {errores}\n"
        )

    path = os.path.join(AGENCY_DIR, type_key, f"{name}.md")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        console.print(f"[green]✓ @{name} forjado profesionalmente.[/green]")
        return name
    except (OSError, IOError) as e:
        console.print(f"[red]Error guardando: {e}[/red]")
        return None


def handle_crud(entity_type: str, state, display_header_func=None) -> None:
    """Menú CRUD para gestionar agentes o habilidades.

    Args:
        entity_type: "agents" o "skills".
        state: Instancia de JellyfishState.
        display_header_func: Función para refrescar el header.
    """
    plural = "AGENTES" if entity_type == "agents" else "HABILIDADES"
    base_dir = os.path.join(AGENCY_DIR, entity_type)
    os.makedirs(base_dir, exist_ok=True)

    while True:
        action = interactive_picker(
            f"GESTIÓN DE {plural}",
            ["cargar", "añadir", "editar", "ver", "eliminar"]
        )
        if not action:
            break

        items = [f[:-3] for f in os.listdir(base_dir) if f.endswith(".md")]

        if action == "cargar":
            if not items:
                console.print(f"[yellow]No hay {plural.lower()} disponibles.[/yellow]")
                continue
            name = interactive_picker("SELECCIONAR", items)
            if name:
                if entity_type == "agents":
                    state.load_agent(name)
                else:
                    state.active_skills.add(os.path.join(base_dir, f"{name}.md"))
                    state.refresh_static_context()
                break

        elif action == "añadir":
            detailed_interview(entity_type)

        elif action == "editar":
            if not items:
                console.print(f"[yellow]No hay {plural.lower()} para editar.[/yellow]")
                continue
            name = interactive_picker("EDITAR", items)
            if name:
                path = os.path.join(base_dir, f"{name}.md")
                try:
                    with open(path, "r", encoding="utf-8", errors="ignore") as f:
                        old = f.read()
                    new = PromptSession().prompt(f"Editando @{name}: ", default=old)
                    if new.strip():
                        with open(path, "w", encoding="utf-8") as f:
                            f.write(new)
                        console.print(f"[green]✓ @{name} actualizado.[/green]")
                except (OSError, IOError) as e:
                    console.print(f"[red]Error editando: {e}[/red]")

        elif action == "ver":
            if not items:
                console.print(f"[yellow]No hay {plural.lower()} para ver.[/yellow]")
                continue
            name = interactive_picker("VER", items)
            if name:
                try:
                    filepath = os.path.join(base_dir, f"{name}.md")
                    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    # Usar resaltado de sintaxis para archivos de código
                    if entity_type == "skills" and "```" in content:
                        print_code(content, filename=f"{name}.md", language="markdown")
                    else:
                        print_panel(content, title=f"@{name}", border_style="cyan", is_markdown=True)
                except (OSError, IOError) as e:
                    console.print(f"[red]Error leyendo: {e}[/red]")

        elif action == "eliminar":
            if not items:
                console.print(f"[yellow]No hay {plural.lower()} para eliminar.[/yellow]")
                continue
            name = interactive_picker("BORRAR", items)
            if name and Confirm.ask(f"¿Borrar @{name}?"):
                try:
                    os.remove(os.path.join(base_dir, f"{name}.md"))
                    console.print(f"[green]✓ @{name} eliminado.[/green]")
                    if entity_type == "agents" and state.active_agent == name:
                        state.load_agent("default")
                    if entity_type == "skills":
                        state.active_skills.discard(os.path.join(base_dir, f"{name}.md"))
                        state.refresh_static_context()
                except (OSError, IOError) as e:
                    console.print(f"[red]Error eliminando: {e}[/red]")

    if display_header_func:
        display_header_func()


def handle_slash_command(cmd_input: str, state, rag, plugins, display_header_func) -> None:
    """Procesa todos los comandos slash del sistema.

    Soporta aliases cortos para los comandos más frecuentes:
        /a → /agent, /s → /skill, /c → /context, /r → /run, /h → /help

    Args:
        cmd_input: Input completo del usuario (ej: "/add path/to/file").
        state: Instancia de JellyfishState.
        rag: Instancia de CodeKnowledgeBase.
        plugins: Instancia de PluginManager.
        display_header_func: Función para refrescar el header.
    """
    parts = cmd_input.split(" ", 1)
    command = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""

    # --- Aliases ---
    aliases = {
        "/a": "/agent",
        "/s": "/skill",
        "/c": "/context",
        "/r": "/run",
        "/p": "/project",
        "/h": "/help",
    }
    command = aliases.get(command, command)

    if command == "/exit":
        console.print("[bold purple]🪼 Jellyfish desconectado. Hasta pronto.[/bold purple]")
        sys.exit(0)

    elif command == "/goff":
        state.show_guides = False
        state.save_config(show_guides="0")
        from core.tui import tui_engine
        if tui_engine._initialized:
            tui_engine.clear_scroll_region()
            if display_header_func:
                display_header_func()
        else:
            os.system("cls" if os.name == "nt" else "clear")
            tui_engine.print_welcome_logo()
            if display_header_func:
                display_header_func()
        console.print("[bold red]🪼 Guías del proyecto DESACTIVADAS.[/bold red] Escribe [bold green]/Gon[/bold green] para volver a activarlas.")
        return

    elif command == "/gon":
        state.show_guides = True
        state.save_config(show_guides="1")
        from core.tui import tui_engine
        if tui_engine._initialized:
            tui_engine.clear_scroll_region()
            if display_header_func:
                display_header_func()
        else:
            os.system("cls" if os.name == "nt" else "clear")
            tui_engine.print_welcome_logo()
            if display_header_func:
                display_header_func()
        show_project_guide_if_needed(state)
        return

    elif command == "/clear":
        state.reset_history()
        from core.tui import tui_engine
        if tui_engine._initialized:
            tui_engine.clear_scroll_region()
            if display_header_func:
                try:
                    display_header_func(force=True)
                except TypeError:
                    display_header_func()
            tui_engine.move_cursor_to_scroll_region()
            show_project_guide_if_needed(state)
        else:
            os.system("cls" if os.name == "nt" else "clear")
            tui_engine.print_welcome_logo()
            if display_header_func:
                try:
                    display_header_func(force=True)
                except TypeError:
                    display_header_func()
            show_project_guide_if_needed(state)

    elif command == "/help":
        _show_help(display_header_func)

    elif command == "/add":
        _handle_add(arg, state, rag, display_header_func)

    elif command == "/context":
        _handle_context(state, display_header_func)

    elif command in ("/purge", "/context-f.del"):
        _handle_purge(state, rag, display_header_func)

    elif command == "/rag":
        _handle_rag(arg, rag, display_header_func)

    elif command == "/run":
        if not arg:
            arg = PromptSession().prompt("Comando: ").strip()
        if arg:
            run_terminal_command(arg, state)

    elif command == "/plugin":
        _handle_plugin(arg, plugins, state)

    elif command == "/agent":
        handle_crud("agents", state, display_header_func)

    elif command == "/skill":
        handle_crud("skills", state, display_header_func)

    elif command == "/provider":
        _show_provider_info(state)

    elif command == "/config":
        _handle_config(arg, state, display_header_func)

    elif command == "/ignore":
        _handle_ignore(arg, state)

    elif command == "/project":
        _handle_project(arg, state, rag, display_header_func)

    elif command in ("/auto", "/build"):
        _handle_auto(arg, state, display_header_func)

    else:
        console.print(f"[yellow]Comando desconocido: {command}. Usa /help.[/yellow]")


def _handle_auto(arg: str, state, display_header_func) -> None:
    """Manejador del comando /auto — Agencia Autónoma de Desarrollo.

    Ejecuta un pipeline completo de agentes encadenados:
    Product Owner → Scrum Master → Arquitecto → Developer → QA

    Requiere un proyecto activo vinculado.
    """
    idea = arg.strip()

    # Validar que haya proyecto activo
    if not state.active_project:
        console.print(
            "[red]⚠ No hay un proyecto activo. "
            "Usa [bold]/project new <ruta>[/bold] primero para crear uno.[/red]"
        )
        return

    # Validar que se proporcionó una descripción
    if not idea:
        console.print(
            "[yellow]Uso: [bold]/auto <descripción de tu proyecto>[/bold][/yellow]\n"
            "[dim]Ejemplo: /auto Quiero una API REST con FastAPI para gestionar "
            "inventario con exportación a PDF[/dim]"
        )
        return

    from core.project_orchestrator import ProjectOrchestrator

    orchestrator = ProjectOrchestrator(state)
    final_report = orchestrator.run(idea)

    # Guardar en historial
    state.history.append({"role": "user", "content": f"/auto {idea}"})
    state.history.append({"role": "assistant", "content": final_report})

    if display_header_func:
        display_header_func()


def _show_help(display_header_func):
    """Muestra la guía de comandos y manual completo."""
    manual = """
# 🪼 Jellyfish OS v5.1 — Manual del Usuario

Jellyfish es un framework de agentes técnicos impulsados por IA. Combina modelos locales o en la nube (Ollama, OpenAI, DeepSeek, OpenRouter) con ejecución autónoma (Auto-ReAct), recuperación de código vectorial (RAG) y un **Orquestador Multi-Agente** para investigaciones complejas.

---

## 📚 1. CONCEPTOS FUNDAMENTALES

**A. Contexto Activo vs. Contexto RAG**
*   **Contexto Activo:** Archivos añadidos con `/add` se cargan COMPLETOS en la memoria de la IA. Ideal para 1-4 archivos donde necesitas precisión absoluta.
*   **Contexto RAG (Indexación Vectorial):** Al hacer `/add` sobre una *carpeta*, Jellyfish trocea el código y lo guarda en una base vectorial (ChromaDB) aislada por proyecto. Cada pregunta recupera solo los fragmentos más relevantes.
*   **Importante:** El RAG ahora crea una base de datos separada por cada proyecto indexado (basada en el hash del directorio), evitando que el código de proyectos distintos se mezcle.

**B. Bucle Auto-ReAct (Autonomía)**
Cuando el modelo sugiere comandos Bash, Jellyfish pide confirmación. Si la apruebas, ejecuta el comando e inyecta la salida al modelo (hasta 3 ciclos). Novedades de seguridad:
*   **Auto-rechazo:** Si no respondes en 60 segundos, el comando se rechaza automáticamente.
*   **Lista negra:** Comandos como `rm -rf`, `mkfs`, `dd of=/dev/*` o fork bombs son bloqueados de forma permanente, sin importar la confirmación.
*   **Ctrl+C grácil:** Interrumpir el stream conserva la respuesta parcial ya recibida sin matar Jellyfish.

**C. Orquestador Multi-Agente (`/research`)**
Un sistema de 4 fases para consultas complejas: **Planificación → Búsqueda en RAG → Síntesis → Citación**. Los subagentes trabajan en silencio y solo el reporte final se muestra en pantalla. Al terminar se imprime una tabla con el tiempo de cada fase.

---

## ⚙️ 2. CONFIGURACIÓN DEL SISTEMA

### `/config` — Panel de Configuración Hot-Reload
*   `/config` (o `/config menu`): Menú interactivo para ver/cambiar proveedor, modelo y API Keys.
*   `/config providers` — Lista proveedores, API keys enmascaradas y endpoints.
*   `/config provider [nombre]` — Opciones: `ollama`, `openai`, `deepseek`, `openrouter`, `gemini`, `qwen`, `kimi`, `zhipu`, `custom`.
*   `/config model [nombre]` — Cambia el modelo activo (ej. `gpt-4o`, `qwen2.5:32b`).
*   `/config key [proveedor] [valor]` — Guarda una API Key en `.env` con permisos `600` automáticos.
*   `/config endpoint [proveedor] [base_url]` — Cambia la URL base de cualquier proveedor OpenAI-compatible.
*   `/config subagent_model [modelo]` — Modelo ligero para los Search Agents del orquestador.
*   `/config subagent_provider [proveedor]` — Proveedor para los subagentes (puede ser distinto al Lead).
*   `/config context_limit [tokens]` — Ajusta el límite de contexto del modelo (por defecto: 8192).

> 🔒 Las API Keys se guardan con permisos `chmod 600` automáticamente para protegerlas.

### `/ignore` — Filtros RAG (.jellyfishignore)
*   `/ignore` (o `/ignore menu`): Taller interactivo de exclusiones.
*   `/ignore init`: Genera `.jellyfishignore` con patrones por defecto (venv, node_modules, dist…).
*   `/ignore add [patrón]`: Agrega un filtro (ej. `*.log`, `temp/`).
*   `/ignore remove [patrón]`: Elimina un filtro.
*   `/ignore show`: Lista los patrones activos.

---

## 🧠 3. GESTIÓN DEL RAG Y CONTEXTO

### `/add` — Ingesta de Código
*   `/add`: Abre un explorador de archivos interactivo.
    *   **Archivo individual:** Se carga completo al Contexto Activo.
    *   **Carpeta:** El RAG indexa todos sus archivos con un splitter inteligente. Para Python, el código se divide respetando los límites reales de funciones y clases (AST-aware), evitando que una función quede partida en dos fragmentos.

### `/context` (alias: `/c`) — Inspector de Contexto Activo
*   Muestra los archivos vinculados. Permite desvincularlos individualmente o limpiar todo.

### `/rag` — Panel de Control Vectorial
*   `/rag status`: Chunks e índice activo. El nombre de la DB indica el proyecto (hash SHA1).
*   `/rag reindex [ruta]`: Borra y reconstruye el índice desde cero.
*   `/rag remove [ruta]`: Eliminación granular de un archivo o carpeta del índice.
*   `/rag clear`: Limpia completamente la base RAG activa.

### `/purge` — Amnesia Total
*   Elimina el Contexto Activo completo y la base RAG en un solo paso.

---

## 🤖 4. ORQUESTADOR MULTI-AGENTE

### `/research <consulta>` — Investigación Autónoma Multi-Paso
Ideal para preguntas complejas sobre tu codebase. Ejecuta un pipeline de 4 fases:

1.  **🗺 Lead Planner:** Desglosa la consulta en 1-3 pasos de búsqueda (genera JSON internamente).
2.  **🔍 Search Agents:** Cada paso consulta el RAG en silencio y resume los hallazgos.
3.  **✍ Lead Synthesizer:** Redacta un reporte cohesivo fundamentado en los hallazgos (streaming visible).
4.  **📚 Citation Agent:** Verifica y añade enlaces `file://` a los archivos fuente mencionados.

Al finalizar se imprime una tabla con el tiempo de cada agente y los tokens estimados.

*   Ejemplo: `/research cómo funciona el sistema de plugins y qué archivos interactúan con él`
*   El reporte se guarda automáticamente en el historial para continuar la conversación.

### `/auto <descripción>` (alias: `/build`) — Agencia Autónoma de Desarrollo
Ejecuta un pipeline completo de desarrollo de software de forma **automática**, encadenando 5 agentes sin intervención manual:

1.  **📝 Product Owner:** Analiza tu idea y genera el `BACKLOG.md` con historias de usuario. **(✋ Checkpoint: te pide aprobación)**.
2.  **📋 Scrum Master:** Toma el backlog aprobado y genera el `SPRINT_BOARD.md` con la planificación del sprint.
3.  **🏗️ Arquitecto:** Diseña la arquitectura del sistema en `ARCHITECTURE.md`.
4.  **💻 Developer:** Genera el plan de implementación con código en `IMPLEMENTATION_PLAN.md`.
5.  **🧪 QA Engineer:** Crea el plan de pruebas en `TEST_PLAN.md`.

⚠️ **Requiere un proyecto activo** (`/project`). Todos los archivos se generan en la carpeta del proyecto.

*   Ejemplo: `/auto Quiero una API REST con FastAPI para gestionar inventario con exportación a PDF`

---

## 🛠️ 5. AGENTES Y HABILIDADES

### `/agent` (alias: `/a`) — Taller de Personalidades
Crea, carga, edita o elimina agentes (ej. `frontend_senior`, `experto_aws`). Cada agente tiene rol, tono, expertise y reglas inquebrantables definidas en un archivo `.md`.

### `@<nombre>` — Cambio Rápido de Agente
*   Escribe `@experto_aws` y presiona Enter para activar ese agente instantáneamente.
*   El autocompletado con Tab muestra la descripción de cada agente leída desde su archivo `.md`.
*   Usa `@exit` para volver a la personalidad neutral de Jellyfish.

### `/skill` (alias: `/s`) — Macros Inteligentes
Las Skills enseñan al agente comandos Bash pre-configurados con manejo de errores. Útil para flujos como `git_push`, `docker_deploy` o `run_tests`.

---

## 🚀 6. HERRAMIENTAS DE SISTEMA

### `/run` (alias: `/r`) — Terminal Integrada
*   `/run [comando]`: Ejecuta un comando sin salir de Jellyfish. La salida se inyecta al historial.
*   Timeout por defecto: 120s. Personalizable con `--timeout=N`.
*   La salida larga se trunca mostrando el **inicio y el final** (donde suelen estar los errores).
*   Comandos destructivos son bloqueados antes de ejecutarse, incluso si el LLM los sugiere.

### `/plugin` — Sistema Modular Python
*   Los plugins son archivos `.py` en `agencia/plugins/` con una función `execute(args) -> str`.
*   `/plugin`: Lista los plugins disponibles con su descripción.
*   `/plugin [nombre] [args]`: Ejecuta el plugin con timeout de 30s. Si `bubblewrap` está disponible, se usa aislamiento de filesystem/red; si no, se usa Python aislado con entorno sin claves.
    *   Si el plugin cuelga o usa demasiados recursos, se aborta automáticamente.
    *   Para desactivar el sandbox: `export JELLYFISH_PLUGIN_UNSAFE=1` (no recomendado).

### `/clear` — Limpiar Historial de Chat
*   Limpia los mensajes recientes. **No borra** el RAG ni el Contexto Activo.

### `/provider` — Inspector de Proveedor Activo
*   Muestra proveedor, modelo y si es local (Ollama) o en la nube.

---

## 🔑 7. VARIABLES DE ENTORNO AVANZADAS (`.env`)

| Variable | Default | Descripción |
|---|---|---|
| `JELLYFISH_PROVIDER` | `ollama` | Proveedor de IA principal (`ollama`, `openai`, `deepseek`, `openrouter`, `gemini`, `qwen`, `kimi`, `zhipu`, `custom`) |
| `JELLYFISH_MODEL` | `qwen2.5-agent:latest` | Modelo del Lead Agent |
| `JELLYFISH_SUBAGENT_MODEL` | *(hereda MODEL)* | Modelo para Search Agents |
| `JELLYFISH_SUBAGENT_PROVIDER` | *(hereda PROVIDER)* | Proveedor para subagentes |
| `JELLYFISH_CONTEXT_LIMIT` | `8192` | Tokens máximos del modelo |
| `JELLYFISH_RAG_THRESHOLD` | `1.2` | Umbral de relevancia RAG (L2) |
| `JELLYFISH_EMBED_MODEL` | `nomic-embed-text` | Modelo de embeddings Ollama |
| `JELLYFISH_PLUGIN_UNSAFE` | `0` | `1` desactiva el sandbox de plugins |

---

## ⚡ REFERENCIA RÁPIDA DE COMANDOS

| Comando | Alias | Función |
|---|---|---|
| `/research <consulta>` | — | Orquestador multi-agente |
| `/add [ruta]` | — | Añadir archivo o carpeta al contexto/RAG |
| `/context` | `/c` | Gestionar contexto activo |
| `/rag <status|reindex|remove|clear>` | — | Control del índice vectorial |
| `/purge` | — | Borrar todo contexto y RAG |
| `/agent` | `/a` | Gestionar agentes |
| `/skill` | `/s` | Gestionar habilidades |
| `/run <cmd>` | `/r` | Ejecutar comando en terminal |
| `/plugin [nombre]` | — | Ejecutar plugin en sandbox |
| `/config [opción]` | — | Configurar proveedor/modelo/keys |
| `/ignore [opción]` | — | Gestionar .jellyfishignore |
| `/provider` | — | Ver proveedor activo |
| `/clear` | — | Limpiar historial de chat |
| `/help` | `/h` | Este manual |
| `/exit` | — | Cerrar Jellyfish |

"""
    from core.tui import tui_engine
    if tui_engine._initialized:
        # Pausar temporalmente TUI para usar pager interactivo en pantalla completa
        tui_engine.restore_terminal()

        import pydoc
        from io import StringIO
        from core.state import get_term_width

        buf = StringIO()
        temp_console = Console(file=buf, force_terminal=True, width=min(120, get_term_width()))
        temp_console.print(Panel(Markdown(manual), border_style="cyan"))

        # Desplegar manual en el pager del sistema (ej: less)
        pydoc.pager(buf.getvalue())

        # Reactivar modo TUI y refrescar
        tui_engine.init_terminal()
        display_header_func()
        tui_engine.move_cursor_to_scroll_region()
    else:
        console.print(Panel(Markdown(manual), border_style="cyan"))


def _show_provider_info(state):
    """Muestra información del proveedor de IA activo."""
    provider_meta = PROVIDER_CONFIGS.get(state.provider, {})
    key_status = "No requiere API key" if state.provider == "ollama" else _mask_key(state.api_keys.get(state.provider, ""))
    base_url = state.base_urls.get(state.provider, state.ollama_base_url)
    console.print(Panel(
        f"[bold]Proveedor:[/bold] {state.provider.upper()} — {provider_meta.get('label', '')}\n"
        f"[bold]Modelo:[/bold] {state.model}\n"
        f"[bold]Tipo:[/bold] {'Nube / API' if state.provider != 'ollama' else 'Local (Ollama)'}\n"
        f"[bold]API Key:[/bold] {key_status}\n"
        f"[bold]Endpoint:[/bold] {base_url}",
        title="Proveedor de IA",
        border_style="blue"
    ))
    input("\nPresiona Enter para continuar...")


def _mask_key(key: str) -> str:
    """Enmascara una clave API para mostrarla con seguridad."""
    if not key:
        return "No configurada"
    if len(key) <= 8:
        return "****"
    return f"{key[:4]}...{key[-4:]}"


def _show_current_config(state):
    """Muestra la configuración actual de forma estilizada."""
    table = Table(title="CONFIGURACION JELLYFISH", border_style="cyan", show_lines=False)
    table.add_column("Activo", justify="center", width=7)
    table.add_column("Proveedor", style="bold")
    table.add_column("API Key")
    table.add_column("Base URL", overflow="fold")

    for name, meta in PROVIDER_CONFIGS.items():
        active = "*" if name == state.provider else ""
        key = "local" if name == "ollama" else _mask_key(state.api_keys.get(name, ""))
        base_url = state.base_urls.get(name, "")
        table.add_row(active, f"{name} — {meta['label']}", key, base_url or "(configurar)")

    console.print(table)
    console.print(Panel(
        f"[bold]Modelo activo:[/bold] {state.model}\n"
        f"[bold]Subagentes:[/bold] {state.subagent_provider}:{state.subagent_model}\n"
        f"[bold]RAG:[/bold] embeddings={state.embed_model} · umbral={state.relevance_threshold}",
        title="Runtime",
        border_style="bright_black",
    ))


def _resolve_provider_name(value: str) -> str:
    """Resuelve alias humanos a proveedores soportados."""
    key = (value or "").strip().lower()
    key = PROVIDER_ALIASES.get(key, key)
    return key if key in PROVIDER_CONFIGS else ""


def _provider_menu_options() -> list[str]:
    return [f"{name} — {PROVIDER_CONFIGS[name]['label']}" for name in supported_provider_names()]


def _provider_from_menu_option(option: str) -> str:
    return option.split(" ", 1)[0].strip() if option else ""


def _save_provider_key(state, provider: str, value: str) -> bool:
    if provider == "ollama":
        console.print("[yellow]Ollama local no requiere API key.[/yellow]")
        return False
    state.save_config(**{f"{provider}_key": value})
    return True


def _save_provider_base_url(state, provider: str, value: str) -> bool:
    if provider not in PROVIDER_CONFIGS:
        return False
    state.save_config(**{f"{provider}_base_url": value})
    return True


def _handle_config(arg: str, state, display_header_func):
    """Manejador del comando /config."""
    raw = arg.strip()
    subcmd = raw.split(maxsplit=1)[0].lower() if raw else ""

    if not raw or subcmd == "show":
        _show_current_config(state)
        input("\nPresiona Enter para continuar...")
        return

    # --- Comandos CLI directos ---
    # /config provider [name]
    if subcmd == "providers":
        _show_current_config(state)
        return

    if subcmd == "provider":
        parts = raw.split(maxsplit=1)
        prov = _resolve_provider_name(parts[1]) if len(parts) > 1 else ""
        if not prov:
            console.print(
                "[red]Proveedor inválido.[/red] Opciones: "
                + ", ".join(supported_provider_names())
            )
        else:
            state.save_config(provider=prov)
            console.print(f"[green]✓ Proveedor cambiado a: {prov}[/green]")
            display_header_func()
        return

    # /config model [name]
    elif subcmd == "model":
        parts = raw.split(" ", 1)
        mod = parts[1].strip() if len(parts) > 1 else ""
        if not mod:
            console.print("[red]Por favor especifica el nombre del modelo.[/red]")
        else:
            state.save_config(model=mod)
            console.print(f"[green]✓ Modelo cambiado a: {mod}[/green]")
            display_header_func()
        return

    # /config key [provider] [value]
    elif subcmd == "key":
        parts = raw.split(maxsplit=2)
        if len(parts) < 3:
            console.print(
                "[red]Uso: /config key <proveedor> <valor_clave>[/red]\n"
                f"[dim]Proveedores: {', '.join(supported_provider_names())}[/dim]"
            )
            return
        target_prov = _resolve_provider_name(parts[1])
        key_val = parts[2].strip()

        if not target_prov:
            console.print("[red]Proveedor de key desconocido.[/red]")
            return
        if _save_provider_key(state, target_prov, key_val):
            console.print(f"[green]✓ API Key de {target_prov} actualizada en .env.[/green]")
        return

    # /config endpoint [provider] [url]
    elif subcmd in ("endpoint", "base_url", "url"):
        parts = raw.split(maxsplit=2)
        if len(parts) < 3:
            console.print("[red]Uso: /config endpoint <proveedor> <base_url>[/red]")
            return
        target_prov = _resolve_provider_name(parts[1])
        base_url = parts[2].strip()
        if not target_prov:
            console.print("[red]Proveedor desconocido.[/red]")
            return
        _save_provider_base_url(state, target_prov, base_url)
        console.print(f"[green]✓ Endpoint de {target_prov} actualizado.[/green]")
        return

    elif subcmd == "subagent_model":
        parts = raw.split(" ", 1)
        mod = parts[1].strip() if len(parts) > 1 else ""
        if not mod:
            console.print("[red]Uso: /config subagent_model <modelo>[/red]")
        else:
            state.save_config(subagent_model=mod)
            console.print(f"[green]✓ Modelo de subagentes: {mod}[/green]")
        return

    elif subcmd == "subagent_provider":
        parts = raw.split(maxsplit=1)
        prov = _resolve_provider_name(parts[1]) if len(parts) > 1 else ""
        if not prov:
            console.print("[red]Uso: /config subagent_provider <proveedor>[/red]")
        else:
            state.save_config(subagent_provider=prov)
            console.print(f"[green]✓ Proveedor de subagentes: {prov}[/green]")
        return

    elif subcmd == "context_limit":
        parts = raw.split(maxsplit=1)
        value = parts[1].strip() if len(parts) > 1 else ""
        try:
            tokens = int(value)
            if tokens < 1024:
                raise ValueError
        except ValueError:
            console.print("[red]Uso: /config context_limit <tokens>, mínimo 1024[/red]")
            return
        state.save_config(context_limit=str(tokens))
        console.print(f"[green]✓ Límite de contexto configurado: {tokens} tokens[/green]")
        return

    # --- Menú Interactivo ---
    if subcmd in ("interactive", "menu", "wizard"):
        while True:
            action = interactive_picker(
                "CONFIGURACIÓN JELLYFISH",
                [
                    "Ver Configuración",
                    "Cambiar Proveedor",
                    "Cambiar Modelo",
                    "Configurar API Key",
                    "Configurar Endpoint",
                    "Configurar Subagentes",
                ]
            )
            if not action:
                break

            session = PromptSession()

            if action == "Ver Configuración":
                _show_current_config(state)
                input("\nPresiona Enter para continuar...")

            elif action == "Cambiar Proveedor":
                selected = interactive_picker("SELECCIONAR PROVEEDOR", _provider_menu_options())
                prov = _provider_from_menu_option(selected)
                if prov:
                    state.save_config(provider=prov)
                    console.print(f"[green]✓ Proveedor cambiado a: {prov}[/green]")
                    input("\nPresiona Enter para continuar...")

            elif action == "Cambiar Modelo":
                mod = session.prompt("Escribe el nombre del modelo: ", default=state.model).strip()
                if mod:
                    state.save_config(model=mod)
                    console.print(f"[green]✓ Modelo cambiado a: {mod}[/green]")
                    input("\nPresiona Enter para continuar...")

            elif action == "Configurar API Key":
                selected = interactive_picker("SELECCIONAR PROVEEDOR", _provider_menu_options())
                prov = _provider_from_menu_option(selected)
                if prov:
                    current = state.api_keys.get(prov, "")
                    val = session.prompt(f"API Key para {prov}: ", default=current).strip()
                    if _save_provider_key(state, prov, val):
                        console.print("[green]✓ API Key guardada exitosamente en .env.[/green]")
                    input("\nPresiona Enter para continuar...")

            elif action == "Configurar Endpoint":
                selected = interactive_picker("SELECCIONAR PROVEEDOR", _provider_menu_options())
                prov = _provider_from_menu_option(selected)
                if prov:
                    current = state.base_urls.get(prov, "")
                    val = session.prompt(f"Base URL para {prov}: ", default=current).strip()
                    if val:
                        _save_provider_base_url(state, prov, val)
                        console.print("[green]✓ Endpoint guardado exitosamente en .env.[/green]")
                    input("\nPresiona Enter para continuar...")

            elif action == "Configurar Subagentes":
                selected = interactive_picker("PROVEEDOR SUBAGENTES", _provider_menu_options())
                prov = _provider_from_menu_option(selected)
                if prov:
                    mod = session.prompt("Modelo de subagentes: ", default=state.subagent_model).strip()
                    state.save_config(subagent_provider=prov, subagent_model=mod or state.subagent_model)
                    console.print("[green]✓ Configuración de subagentes actualizada.[/green]")
                    input("\nPresiona Enter para continuar...")

        display_header_func()
        return

    console.print("[yellow]Subcomando /config desconocido. Usa /config show o /config menu.[/yellow]")


def _handle_ignore(arg: str, state):
    """Manejador del comando /ignore para gestionar .jellyfishignore."""
    sub = arg.strip()
    ignore_file_path = os.path.join(AGENCY_DIR, ".jellyfishignore")

    # Función helper para leer patrones
    def _read_patterns():
        if not os.path.exists(ignore_file_path):
            return []
        patterns = []
        with open(ignore_file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    patterns.append(line)
        return patterns

    # Función helper para guardar patrones
    def _write_patterns(patterns):
        with open(ignore_file_path, "w", encoding="utf-8") as f:
            f.write("# Patrones de exclusión para Jellyfish RAG\n")
            for p in patterns:
                f.write(f"{p}\n")

    # Si no hay argumentos, ir al menú interactivo
    if not sub:
        while True:
            action = interactive_picker(
                "GESTIÓN DE EXCLUSIONES (.jellyfishignore)",
                ["Ver Patrones", "Inicializar con Defaults", "Agregar Patrón", "Remover Patrón"]
            )
            if not action:
                break

            session = PromptSession()

            if action == "Ver Patrones":
                patterns = _read_patterns()
                if not patterns:
                    console.print("[yellow]No hay patrones definidos en .jellyfishignore.[/yellow]")
                else:
                    content = "\n".join([f"  • {p}" for p in patterns])
                    console.print(Panel(content, title=".jellyfishignore", border_style="cyan"))
                input("\nPresiona Enter para continuar...")

            elif action == "Inicializar con Defaults":
                defaults = [
                    "venv/", ".venv/", "env/", ".git/", "__pycache__/",
                    "node_modules/", "code_vector_db/", "code_vector_db*/", "code_vector_db*", "test_db/",
                    "dist/", "build/", ".next/", "*.png", "*.jpg", "*.jpeg",
                    "*.exe", "*.so", "*.dll", "*.zip", "*.tar.gz"
                ]
                _write_patterns(defaults)
                console.print("[green]✓ .jellyfishignore inicializado con patrones por defecto.[/green]")
                input("\nPresiona Enter para continuar...")

            elif action == "Agregar Patrón":
                pat = session.prompt("Escribe el patrón a excluir (ej. logs/ o *.log): ").strip()
                if pat:
                    patterns = _read_patterns()
                    if pat in patterns:
                        console.print("[yellow]El patrón ya existe.[/yellow]")
                    else:
                        patterns.append(pat)
                        _write_patterns(patterns)
                        console.print(f"[green]✓ Patrón '{pat}' agregado.[/green]")
                    input("\nPresiona Enter para continuar...")

            elif action == "Remover Patrón":
                patterns = _read_patterns()
                if not patterns:
                    console.print("[yellow]No hay patrones para remover.[/yellow]")
                    input("\nPresiona Enter para continuar...")
                    continue
                sel = interactive_picker("SELECCIONA PATRÓN A REMOVER", patterns)
                if sel:
                    patterns.remove(sel)
                    _write_patterns(patterns)
                    console.print(f"[green]✓ Patrón '{sel}' removido.[/green]")
                    input("\nPresiona Enter para continuar...")
        return

    # --- Comandos CLI directos ---
    parts = sub.split(" ", 1)
    subcmd = parts[0].lower()
    val = parts[1].strip() if len(parts) > 1 else ""

    if subcmd == "show":
        patterns = _read_patterns()
        if not patterns:
            console.print("[yellow]No hay patrones definidos en .jellyfishignore.[/yellow]")
        else:
            content = "\n".join([f"  • {p}" for p in patterns])
            console.print(Panel(content, title=".jellyfishignore", border_style="cyan"))

    elif subcmd == "init":
        defaults = [
            "venv/", ".venv/", "env/", ".git/", "__pycache__/",
            "node_modules/", "code_vector_db/", "code_vector_db*/", "code_vector_db*", "test_db/",
            "dist/", "build/", ".next/", "*.png", "*.jpg", "*.jpeg",
            "*.exe", "*.so", "*.dll", "*.zip", "*.tar.gz"
        ]
        _write_patterns(defaults)
        console.print("[green]✓ .jellyfishignore inicializado con patrones por defecto.[/green]")

    elif subcmd == "add":
        if not val:
            console.print("[red]Por favor especifica el patrón a agregar.[/red]")
        else:
            patterns = _read_patterns()
            if val in patterns:
                console.print("[yellow]El patrón ya existe.[/yellow]")
            else:
                patterns.append(val)
                _write_patterns(patterns)
                console.print(f"[green]✓ Patrón '{val}' agregado.[/green]")

    elif subcmd == "remove":
        if not val:
            console.print("[red]Por favor especifica el patrón a remover.[/red]")
        else:
            patterns = _read_patterns()
            if val in patterns:
                patterns.remove(val)
                _write_patterns(patterns)
                console.print(f"[green]✓ Patrón '{val}' removido.[/green]")
            else:
                console.print(f"[yellow]Patrón '{val}' no encontrado en .jellyfishignore.[/yellow]")


def _handle_add(arg: str, state, rag, display_header_func):
    """Procesa el comando /add con indexación RAG en hilo secundario."""
    if arg:
        candidate = os.path.abspath(os.path.expanduser(arg))
        if os.path.exists(candidate):
            path = candidate
        else:
            console.print(f"[red]Ruta no encontrada: {arg}[/red]")
            return
    else:
        path = file_browser(".")
    if not path:
        return

    if os.path.isdir(path):
        # Las carpetas viven en RAG. No se inyectan completas al contexto
        # estático para evitar prompts enormes e instrucciones no confiables.
        console.print()
        result = {"count": 0}

        def _index_worker():
            result["count"] = rag.index_codebase(path)

        thread = threading.Thread(target=_index_worker, daemon=True)
        thread.start()

        # Sprint 7.0 — Panel de progreso parpadeante (rojo → verde)
        with TaskProgress(tui_engine, "rag_index", "Indexando código con RAG..."):
            thread.join()
    else:
        state.add_context_file(path)

    state.refresh_static_context()
    console.print(f"[green]✓ Contexto actualizado: {len(state.context_files)} archivos.[/green]")
    input("\nPresiona Enter para continuar...")
    display_header_func()


def _handle_context(state, display_header_func):
    """Procesa el comando /context."""
    files = list(state.context_files)
    if not files:
        console.print("[yellow]⚠ El contexto está vacío. Usa /add para vincular archivos.[/yellow]")
        input("\nPresiona Enter para continuar...")
    else:
        while True:
            files = list(state.context_files)
            if not files:
                break
            sel = interactive_picker("CONTEXTO", ["Limpiar todo"] + files)
            if not sel:
                break
            if sel == "Limpiar todo":
                state.context_files.clear()
                state.refresh_static_context()
                console.print("[green]✓ Contexto limpiado.[/green]")
                break
            state.context_files.discard(sel)
            state.refresh_static_context()
    display_header_func()


def _handle_purge(state, rag, display_header_func):
    """Procesa el comando /purge (antes /context-f.del)."""
    if not state.context_files and not rag.is_active:
        console.print("[yellow]⚠ No hay nada que purgar.[/yellow]")
        input("\nPresiona Enter para continuar...")
    else:
        state.context_files.clear()
        state.refresh_static_context()
        rag.clear_index()
        console.print("[bold red]☢ Contexto y base RAG purgados por completo.[/bold red]")
        input("\nPresiona Enter para continuar...")
    display_header_func()


def _handle_rag(arg: str, rag, display_header_func):
    """Procesa el comando /rag con subcomandos extendidos."""
    arg = arg.strip()
    parts = arg.split(" ", 1)
    subcmd = parts[0].lower()
    val = parts[1].strip() if len(parts) > 1 else ""

    if subcmd == "clear":
        rag.clear_index()

    elif subcmd == "status":
        if rag.is_active:
            console.print(
                f"[green]RAG activo: {rag.indexed_chunk_count} chunks, "
                f"{rag.indexed_file_count} archivos.[/green]"
            )
        else:
            console.print("[yellow]RAG inactivo. Usa /add para indexar una carpeta.[/yellow]")

    elif subcmd == "reindex":
        if not val:
            console.print("[yellow]Uso: /rag reindex <ruta>[/yellow]")
        else:
            exp_val = os.path.expanduser(val)
            if os.path.isdir(exp_val):
                rag.clear_index()
                rag.index_codebase(exp_val)
            else:
                console.print(f"[red]Ruta no válida: {val}[/red]")

    elif subcmd == "remove":
        # Remoción granular: /rag remove <path>
        if not val:
            console.print("[yellow]Uso: /rag remove <ruta>[/yellow]")
        else:
            rag.remove_path(os.path.expanduser(val))

    elif subcmd == "preview":
        # Sprint 8.0 — Previsualización de fragmentos RAG que se enviarían al LLM
        if not val:
            console.print("[yellow]Uso: /rag preview <pregunta>[/yellow]")
        elif not rag.is_active:
            console.print("[yellow]⚠ No hay índice RAG activo. Usa /add para indexar una carpeta.[/yellow]")
        else:
            raw_context = rag.query_code(val)
            if not raw_context:
                console.print("[yellow]⚠ No se encontraron fragmentos relevantes para esa consulta.[/yellow]")
            else:
                # Parsear los fragmentos para mostrarlos con formato
                import re as _re
                from core.rag_coder import _FRAG_OPEN
                _frag_prefix = _re.escape(_FRAG_OPEN.split(" ")[0])
                frag_pattern = _re.compile(
                    rf'{_frag_prefix}\s+source="([^"]+)"\s+relevance="([^"]+)"\s+match="([^"]+)"[^>]*>\n(.*?)\n\s*<',
                    _re.DOTALL
                )
                matches = frag_pattern.findall(raw_context)
                if matches:
                    from rich.table import Table
                    table = Table(title="🔍 Previsualización RAG", border_style="cyan", show_lines=True)
                    table.add_column("#", justify="center", width=3)
                    table.add_column("Fuente", style="bold cyan", max_width=40)
                    table.add_column("Distancia L2", justify="center", width=12)
                    table.add_column("Match", justify="center", width=8)
                    table.add_column("Fragmento (primeras 120 chars)", max_width=50)
                    for i, (source, relevance, match, content) in enumerate(matches, 1):
                        preview = content.strip()[:120].replace('\n', ' ')
                        table.add_row(str(i), source, relevance, match, preview)
                    console.print(table)
                    console.print(f"[dim]Total chars del contexto RAG: {len(raw_context):,}[/dim]")
                else:
                    console.print(Panel(raw_context[:2000], title="RAG Preview (crudo)", border_style="cyan"))

    else:
        console.print(
            "[cyan]Uso:[/cyan]\n"
            "  /rag status           — Ver estado del índice\n"
            "  /rag clear            — Eliminar el índice completo\n"
            "  /rag reindex <path>   — Reindexar una ruta\n"
            "  /rag remove <path>    — Eliminar una ruta del índice\n"
            "  /rag preview <query>  — Previsualizar fragmentos que se enviarían al LLM"
        )

    input("\nPresiona Enter para continuar...")
    display_header_func()


def _handle_plugin(arg: str, plugins, state):
    """Procesa el comando /plugin."""
    if not arg:
        listing = plugins.list_plugins()
        console.print(Panel(listing, title="Plugins Disponibles", border_style="blue"))
        return

    p_parts = arg.split(" ", 1)
    p_name = p_parts[0]
    p_args = p_parts[1] if len(p_parts) > 1 else ""

    res = plugins.run_plugin(p_name, p_args)
    console.print(Panel(str(res), title=f"Plugin: {p_name}", border_style="blue"))
    state.history.append({
        "role": "system",
        "content": f"[PLUGIN {p_name}]\n{res}"
    })


# ---------------------------------------------------------------------------
# Sprint 6.0 — Gestión de Proyectos con Metodología Scrum Autoeditable
# ---------------------------------------------------------------------------

# Plantillas embebidas de metodología Scrum
_SCRUM_METHODOLOGY_TEMPLATE = """\
# 📘 Metodología Scrum — Jellyfish OS

## Roles
- **Scrum Master (@scrum_master):** Facilita el proceso, elimina impedimentos, actualiza los documentos de seguimiento.
- **Product Owner (Usuario):** Define las prioridades del backlog y acepta o rechaza entregables.
- **Development Team (Agentes):** Ejecutan las tareas del sprint activo.

## Artefactos
| Artefacto | Archivo | Propósito |
|---|---|---|
| Product Backlog | `BACKLOG.md` | Lista priorizada de todas las historias de usuario / requerimientos. |
| Sprint Board | `SPRINT_BOARD.md` | Tablero Kanban con el estado de las tareas del sprint activo. |
| Daily Log | `DAILY.md` | Bitácora de standups y comunicación entre agentes. |

## Eventos
1. **Sprint Planning:** Al inicio de cada sprint, el Scrum Master mueve tareas del Backlog al Sprint Board (columna TODO).
2. **Daily Standup:** Cada sesión de trabajo registra en `DAILY.md`: qué se hizo, qué se hará, qué impedimentos hay.
3. **Sprint Review:** Al final del sprint, se revisan las tareas DONE y se documentan aprendizajes.
4. **Sprint Retrospective:** Se evalúa el proceso y se proponen mejoras.

## Estimación
- Se usa la escala T-shirt: `XS`, `S`, `M`, `L`, `XL`.
- Cada historia en `BACKLOG.md` debe incluir su estimación.

## Definition of Done (DoD)
Una tarea se considera **DONE** cuando:
1. El código ha sido generado y/o ejecutado sin errores.
2. Se ha movido a la columna DONE del `SPRINT_BOARD.md`.
3. Se ha registrado una entrada en `DAILY.md` documentando la finalización.

## Protocolo de Comunicación entre Agentes
- Los agentes se comunican **exclusivamente** a través de los archivos Scrum del proyecto.
- El `DAILY.md` es el canal principal de comunicación asíncrona.
- Cada entrada debe incluir: `[FECHA] [AGENTE] — Mensaje`.
"""

_BACKLOG_TEMPLATE = """\
# 📋 Product Backlog

> Prioridad: 🔴 Alta | 🟡 Media | 🟢 Baja

## Historias de Usuario

| ID | Historia | Estimación | Prioridad | Estado |
|---|---|---|---|---|
| US-001 | Como usuario, quiero [describir funcionalidad] para [beneficio]. | M | 🔴 | Pendiente |

---

*Última actualización: {date}*
*Actualizado por: @scrum_master*
"""

_SPRINT_BOARD_TEMPLATE = """\
# 🗂️ Sprint Board — Sprint 1

> Sprint Goal: [Definir objetivo del sprint]
> Duración: [Fecha inicio] → [Fecha fin]

---

## 📋 POR HACER (TODO)

| ID | Tarea | Asignado | Estimación |
|---|---|---|---|
| — | — | — | — |

---

## ⏳ EN PROCESO (IN PROGRESS)

| ID | Tarea | Asignado | Estimación | Inicio |
|---|---|---|---|---|
| — | — | — | — | — |

---

## ✅ HECHO (DONE)

| ID | Tarea | Asignado | Completado |
|---|---|---|---|
| — | — | — | — |

---

*Última actualización: {date}*
*Actualizado por: @scrum_master*
"""

_DAILY_TEMPLATE = """\
# 📝 Daily Standup Log

> Registro de comunicación diaria entre agentes.
> Formato: `[FECHA] [@AGENTE] — Mensaje`

---

## {date}

### @scrum_master
- **Ayer:** Proyecto inicializado con metodología Scrum.
- **Hoy:** Listo para planificar el primer sprint.
- **Impedimentos:** Ninguno.

---

*Este archivo se actualiza automáticamente por los agentes del proyecto.*
"""



# Plantillas de metodología Cascada (Waterfall)
_WATERFALL_METHODOLOGY_TEMPLATE = """\
# 📘 Metodología de Cascada (Waterfall) — Jellyfish OS

La metodología de cascada sigue un enfoque secuencial y estructurado, donde cada fase debe completarse antes de pasar a la siguiente.

## Fases del Proyecto
1. **Requisitos (`REQUIREMENTS.md`):** Definición detallada de las necesidades y especificaciones técnicas.
2. **Diseño (`DESIGN.md`):** Planificación de la arquitectura de software, diagramas y modelado de datos.
3. **Implementación:** Fase de codificación basada en el diseño y los requisitos.
4. **Verificación (`TESTS_LOG.md`):** Pruebas de integración, validación de código y pruebas de sistema.
5. **Mantenimiento:** Soporte continuo y actualizaciones menores.

## Documentos de Seguimiento
| Documento | Archivo | Propósito |
|---|---|---|
| Especificación de Requisitos | `REQUIREMENTS.md` | Registro formal de todos los requisitos funcionales y no funcionales. |
| Documento de Diseño | `DESIGN.md` | Arquitectura del sistema, estructura de datos y especificación de APIs. |
| Cronograma del Proyecto | `GANTT.md` | Lista secuencial de tareas con fechas estimadas de inicio y fin. |
| Registro de Pruebas | `TESTS_LOG.md` | Bitácora de casos de prueba ejecutados y su estado (Aprobado/Fallido). |
"""

_REQUIREMENTS_TEMPLATE = """\
# 📋 Especificación de Requisitos

## 1. Requisitos Funcionales
| ID | Descripción | Prioridad | Estado | Aprobado Por |
|---|---|---|---|---|
| RF-001 | El sistema debe [describir funcionalidad]. | Alta | Pendiente | - |

## 2. Requisitos No Funcionales
| ID | Descripción | Categoría | Estado |
|---|---|---|---|
| RNF-001 | El tiempo de respuesta debe ser menor a 2 segundos. | Rendimiento | Pendiente |

---
*Última actualización: {date}*
"""

_DESIGN_TEMPLATE = """\
# 🎨 Documentación de Diseño y Arquitectura

## 1. Arquitectura del Sistema
[Describir el enfoque arquitectónico, por ejemplo: Monolito, Microservicios, Arquitectura Limpia]

## 2. Modelado de Datos
[Estructuras de bases de datos, colecciones o formatos de almacenamiento]

## 3. Especificaciones de Interfaz / APIs
[Endpoints de API, firmas de funciones clave o contratos de integración]

---
*Última actualización: {date}*
"""

_GANTT_TEMPLATE = """\
# 📅 Cronograma del Proyecto (Cascada)

> Estado de Fase: ⏳ Pendiente | ⚙️ En Desarrollo | ✅ Completada

## Secuencia de Fases

- [ ] **Fase 1: Requisitos** (Inicio: [Fecha] ➔ Fin: [Fecha]) — ⏳
- [ ] **Fase 2: Diseño** (Inicio: [Fecha] ➔ Fin: [Fecha]) — ⏳
- [ ] **Fase 3: Implementación** (Inicio: [Fecha] ➔ Fin: [Fecha]) — ⏳
- [ ] **Fase 4: Verificación** (Inicio: [Fecha] ➔ Fin: [Fecha]) — ⏳

---
*Última actualización: {date}*
"""

_TESTS_LOG_TEMPLATE = """\
# 🧪 Registro de Pruebas y Verificación

## Historial de Casos de Prueba

| ID Caso | Requisito Relacionado | Descripción de la Prueba | Resultado | Fecha |
|---|---|---|---|---|
| TC-001 | RF-001 | Verificar que [funcionalidad] funcione. | Pendiente | {date} |

---
*Última actualización: {date}*
"""


def show_project_guide_if_needed(state) -> None:
    """Muestra el panel de guía interactiva de construcción del proyecto.

    Esta guía ayuda al usuario en todas las fases de construcción (vinculación,
    redacción de backlog, codificación de lógica, ejecución de tests y bitácoras).
    Se muestra siempre que state.show_guides sea True.
    """
    # Si las guías están desactivadas explícitamente en el estado (por /Goff)
    if not getattr(state, "show_guides", True):
        return
        
    if os.getenv("JELLYFISH_HIDE_PROJECT_GUIDE", "0") == "1":
        return

    # Info de proyecto activo para la guía
    active_path = getattr(state, "active_project", None)
    methodology = getattr(state, "project_methodology", "scrum").upper()
    
    if active_path:
        project_status = f"[bold green]VINCULADO[/bold green] ({active_path})"
    else:
        project_status = "[bold yellow]NO VINCULADO[/bold yellow] (Escribe [bold green]/project[/bold green] para crear o abrir uno)"

    guide_text = (
        f"ℹ️  [bold yellow]ESTADO DEL PROYECTO:[/bold yellow] {project_status} · Metodología: [bold cyan]{methodology}[/bold cyan]\n"
        f"──────────────────────────────────────────────────────────────────────────────\n"
        f"[bold cyan]👥 ORQUESTACIÓN DE AGENTES (Escribe su rol para activarlos):[/bold cyan]\n"
        f"  • [bold green]@product_owner[/bold green]   - Recopila tus requerimientos y redacta las historias en el BACKLOG.md.\n"
        f"  • [bold green]@scrum_master[/bold green]    - Toma el backlog, planifica sprints y supervisa el SPRINT_BOARD.md.\n"
        f"  • [bold green]@arquitecto_software[/bold green] - Diseña diagramas, estructuras de archivos y flujos de datos.\n"
        f"  • [bold green]@default[/bold green]         - Tu desarrollador principal para codificar, debugear y refactorizar.\n"
        f"  [dim]Ejemplo: Escribe [bold]@product_owner[/bold] en la consola y presiona Enter para cambiar de agente.[/dim]\n\n"
        f"[bold cyan]⚙️ ¿CÓMO HACER FUNCIONAR LA METODOLOGÍA?:[/bold cyan]\n"
        f"  [bold magenta]🚀 MODO AUTOMÁTICO (RECOMENDADO):[/bold magenta]\n"
        f"  Escribe [bold green]/auto <tu idea>[/bold green] y la agencia completa trabaja sola:\n"
        f"  PO → Scrum Master → Arquitecto → Developer → QA\n"
        f"  Solo necesitas aprobar el backlog. El resto es automático.\n\n"
        f"  [bold cyan]🔧 MODO MANUAL (Paso a paso):[/bold cyan]\n"
        f"  1. Activa al [bold green]@product_owner[/bold green] y cuéntale tus ideas para que redacte tu [bold]BACKLOG.md[/bold].\n"
        f"  2. Pasa al [bold green]@scrum_master[/bold green] para que tome historias del backlog y planifique el [bold]SPRINT_BOARD.md[/bold].\n"
        f"  3. Pasa al desarrollador ([bold green]@default[/bold green]) para que tome las tareas planificadas e inicie la codificación.\n\n"
        f"[bold cyan]🔍 CÓMO USAR EL CONTEXTO Y RAG EN TU PROYECTO:[/bold cyan]\n"
        f"  • [bold]Vincular archivos al contexto:[/bold] Usa [bold green]/add <ruta_archivo>[/bold green] para que el agente lea el código directamente.\n"
        f"  • [bold]Indexar en RAG (Base de datos vectorial):[/bold] Usa [bold green]/rag index <ruta>[/bold green] para procesar directorios extensos.\n"
        f"  • [bold]Activar/Desactivar RAG en el prompt:[/bold] Escribe [bold green]/rag[/bold green] para alternar entre RAG[ON] y RAG[OFF].\n\n"
        f"[bold cyan]💡 PROMPT DE EJEMPLO PERFECTO PARA ARRANCAR:[/bold cyan]\n"
        f"  [bold green]/auto Quiero una API REST con FastAPI para gestionar inventario con exportación a PDF[/bold green]\n\n"
        f"[bold cyan]✍️ ¿DÓNDE INGRESAR TUS INSTRUCCIONES PARA CONSTRUIR EL PROYECTO?:[/bold cyan]\n"
        f"  • Escribe todas tus ideas, requerimientos o comandos a ejecutar directamente en el prompt principal:\n"
        f"    [bold green]@{state.active_agent}:{state.provider} > [/bold green][bold white]Aquí escribes tus instrucciones...[/bold white]\n"
        f"  • Si necesitas vincular un archivo para que el agente lo lea, escribe: [bold green]/add <archivo>[/bold green]\n"
        f"  • Si deseas correr un script o test local de tu proyecto, escribe: [bold green]/run <comando>[/bold green]\n"
        f"  [dim]Jellyfish actualizará automáticamente los entregables del código y el daily log (DAILY.md).[/dim]\n"
        f"──────────────────────────────────────────────────────────────────────────────\n"
        f"👉 [bold yellow]¿Quieres ocultar esta guía?[/bold yellow] Escribe [bold red]/Goff[/bold red] en la consola para desactivarla.\n"
        f"   (Puedes volver a activarla escribiendo [bold green]/Gon[/bold green])."
    )
    console.print(Panel(guide_text, title="🪼 GUÍA DE ORQUESTACIÓN Y CONSTRUCCIÓN DE PROYECTOS", border_style="yellow"))


def _handle_project(arg: str, state, rag, display_header_func) -> None:
    """Manejador del comando /project para gestión de proyectos Scrum y Cascada.

    Subcomandos:
        /project            — Menú interactivo (crear/ver/desvincular/eliminar).
        /project new <ruta> — Crear proyecto en la ruta especificada.
        /project info       — Mostrar proyecto activo.
        /project unlink     — Desvincular proyecto activo.
        /project delete     — Eliminar físicamente un proyecto del disco.
    """
    from datetime import datetime

    sub = arg.strip()

    # --- Subcomandos CLI directos ---
    if sub.startswith("new "):
        raw_path = sub[4:].strip()
        if raw_path:
            _project_create(raw_path, state, rag, display_header_func)
            if display_header_func:
                display_header_func()
            return
        console.print("[red]Uso: /project new <ruta_del_proyecto>[/red]")
        return

    if sub == "info":
        _project_info(state)
        if display_header_func:
            display_header_func()
        return

    if sub == "unlink":
        _project_unlink(state, display_header_func)
        if display_header_func:
            display_header_func()
        return

    if sub in ("delete", "remove"):
        _project_delete(state, display_header_func)
        if display_header_func:
            display_header_func()
        return

    # --- Menú interactivo ---
    while True:
        action = interactive_picker(
            "GESTIÓN DE PROYECTOS",
            ["Crear / Abrir Proyecto", "Ver Proyecto Activo", "Desvincular Proyecto", "Eliminar Proyecto"]
        )
        if not action:
            break

        if action == "Crear / Abrir Proyecto":
            session = PromptSession()
            raw_path = session.prompt(
                "Ruta del proyecto (absoluta o relativa): ",
                default=os.path.expanduser("~/")
            ).strip()
            if raw_path:
                _project_create(raw_path, state, rag, display_header_func)
            break

        elif action == "Ver Proyecto Activo":
            _project_info(state)
            input("\nPresiona Enter para continuar...")

        elif action == "Desvincular Proyecto":
            _project_unlink(state, display_header_func)
            break

        elif action == "Eliminar Proyecto":
            _project_delete(state, display_header_func)
            break

    if display_header_func:
        display_header_func()


def _project_create(raw_path: str, state, rag, display_header_func, methodology: str = None) -> None:
    """Crea o abre un proyecto en la ruta dada e inicializa archivos de metodología (Scrum o Cascada)."""
    from datetime import datetime

    project_path = os.path.abspath(os.path.expanduser(raw_path))

    # Crear directorio si no existe
    if not os.path.exists(project_path):
        if Confirm.ask(f"El directorio [cyan]{project_path}[/cyan] no existe. ¿Crearlo?"):
            try:
                os.makedirs(project_path, exist_ok=True)
            except OSError as e:
                console.print(f"[red]Error creando directorio: {e}[/red]")
                return
        else:
            console.print("[yellow]Operación cancelada.[/yellow]")
            return

    # Selección de Metodología interactiva
    if not methodology:
        methodology_choice = interactive_picker(
            "SELECCIONAR METODOLOGÍA",
            ["Scrum (Ágil)", "Cascada (Waterfall)"]
        )
        if not methodology_choice:
            console.print("[yellow]Operación cancelada: No se seleccionó ninguna metodología.[/yellow]")
            return
        methodology = "scrum" if "Scrum" in methodology_choice else "cascada"

    today = datetime.now().strftime("%Y-%m-%d")

    # Definir plantillas según la metodología
    if methodology == "cascada":
        methodology_files = {
            "WATERFALL_METHODOLOGY.md": _WATERFALL_METHODOLOGY_TEMPLATE,
            "REQUIREMENTS.md": _REQUIREMENTS_TEMPLATE.format(date=today),
            "DESIGN.md": _DESIGN_TEMPLATE.format(date=today),
            "GANTT.md": _GANTT_TEMPLATE.format(date=today),
            "TESTS_LOG.md": _TESTS_LOG_TEMPLATE.format(date=today),
        }
    else:
        methodology_files = {
            "SCRUM_METHODOLOGY.md": _SCRUM_METHODOLOGY_TEMPLATE,
            "BACKLOG.md": _BACKLOG_TEMPLATE.format(date=today),
            "SPRINT_BOARD.md": _SPRINT_BOARD_TEMPLATE.format(date=today),
            "DAILY.md": _DAILY_TEMPLATE.format(date=today),
        }

    created = []
    for filename, content in methodology_files.items():
        filepath = os.path.join(project_path, filename)
        if not os.path.exists(filepath):
            try:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(content)
                created.append(filename)
            except OSError as e:
                console.print(f"[red]Error escribiendo {filename}: {e}[/red]")

    methodology_label = "Scrum" if methodology == "scrum" else "Cascada"
    if created:
        console.print(f"[green]✓ Archivos de metodología {methodology_label} creados: {', '.join(created)}[/green]")
    else:
        console.print(f"[dim]Los archivos de {methodology_label} ya existían, no se sobreescribieron.[/dim]")

    # Guardar como proyecto activo y registrar metodología
    state.save_config(active_project=project_path, project_methodology=methodology)
    console.print(f"[bold green]✓ Proyecto activo: {project_path} ({methodology_label})[/bold green]")

    # Agregar archivos al contexto activo
    for filename in methodology_files:
        filepath = os.path.join(project_path, filename)
        if os.path.isfile(filepath):
            state.context_files.add(filepath)
    state.refresh_static_context()

    # Indexar en RAG si el usuario lo desea
    if Confirm.ask("¿Indexar el proyecto en el RAG para análisis inteligente?", default=True):
        import threading

        result = {"count": 0}

        def _index_worker():
            result["count"] = rag.index_codebase(project_path)

        thread = threading.Thread(target=_index_worker, daemon=True)
        thread.start()

        # Sprint 7.0 — Panel de progreso parpadeante (rojo → verde)
        with TaskProgress(tui_engine, "project_rag", "Indexando proyecto con RAG..."):
            thread.join()

    input("\nPresiona Enter para continuar...")


def _project_info(state) -> None:
    """Muestra información del proyecto activo."""
    if not state.active_project:
        console.print("[yellow]⚠ No hay proyecto activo. Usa /project para crear uno.[/yellow]")
        return

    methodology = getattr(state, "project_methodology", "scrum").lower()
    if methodology == "cascada":
        methodology_files = ["WATERFALL_METHODOLOGY.md", "REQUIREMENTS.md", "DESIGN.md", "GANTT.md", "TESTS_LOG.md"]
        title_label = "📁 PROYECTO ACTIVO (CASCADA)"
    else:
        methodology_files = ["SCRUM_METHODOLOGY.md", "BACKLOG.md", "SPRINT_BOARD.md", "DAILY.md"]
        title_label = "📁 PROYECTO ACTIVO (SCRUM)"

    status_lines = []
    for f in methodology_files:
        fp = os.path.join(state.active_project, f)
        if os.path.isfile(fp):
            size = os.path.getsize(fp)
            status_lines.append(f"  [green]✓[/green] {f} ({size:,} bytes)")
        else:
            status_lines.append(f"  [red]✗[/red] {f} (no encontrado)")

    content = (
        f"[bold cyan]Proyecto Activo:[/bold cyan] {state.active_project}\n\n"
        f"[bold cyan]Metodología:[/bold cyan] {methodology.upper()}\n\n"
        f"[bold cyan]Archivos de Seguimiento:[/bold cyan]\n" + "\n".join(status_lines)
    )
    console.print(Panel(content, title=title_label, border_style="cyan"))


def _project_unlink(state, display_header_func) -> None:
    """Desvincula el proyecto activo."""
    if not state.active_project:
        console.print("[yellow]⚠ No hay proyecto vinculado.[/yellow]")
        return

    old = state.active_project
    methodology = getattr(state, "project_methodology", "scrum").lower()

    if methodology == "cascada":
        methodology_files = ["WATERFALL_METHODOLOGY.md", "REQUIREMENTS.md", "DESIGN.md", "GANTT.md", "TESTS_LOG.md"]
    else:
        methodology_files = ["SCRUM_METHODOLOGY.md", "BACKLOG.md", "SPRINT_BOARD.md", "DAILY.md"]

    # Remover archivos del contexto
    for f in methodology_files:
        fp = os.path.join(old, f)
        state.context_files.discard(fp)

    state.save_config(active_project="", project_methodology="scrum")
    state.refresh_static_context()
    console.print(f"[green]✓ Proyecto desvinculado: {old}[/green]")


def _project_delete(state, display_header_func) -> None:
    """Elimina físicamente un proyecto tras confirmación explícita y lo desvincula si es el activo."""
    import shutil
    project_path = state.active_project
    
    if not project_path:
        console.print("[yellow]No hay un proyecto activo vinculado actualmente.[/yellow]")
        session = PromptSession()
        raw_path = session.prompt(
            "Introduce la ruta del proyecto a eliminar físicamente (o Enter para cancelar): "
        ).strip()
        if not raw_path:
            console.print("[yellow]Operación cancelada.[/yellow]")
            return
        project_path = os.path.abspath(os.path.expanduser(raw_path))
    
    if not os.path.exists(project_path):
        console.print(f"[red]Error: La ruta del proyecto no existe: {project_path}[/red]")
        return
        
    console.print(f"[bold red]⚠️  ¡ADVERTENCIA DE ELIMINACIÓN FÍSICA! Se eliminará permanentemente la carpeta:[/bold red]")
    console.print(f"   [cyan]{project_path}[/cyan]")
    console.print("   Todos los archivos y subcarpetas serán borrados de forma irrecuperable.")
    
    confirm = input("¿Estás absolutamente seguro? Escribe 'ELIMINAR' para confirmar: ").strip()
    
    if confirm == "ELIMINAR":
        try:
            # Si el proyecto que se elimina es el activo, primero lo desvinculamos
            if state.active_project and os.path.abspath(state.active_project) == os.path.abspath(project_path):
                methodology = getattr(state, "project_methodology", "scrum").lower()
                if methodology == "cascada":
                    methodology_files = ["WATERFALL_METHODOLOGY.md", "REQUIREMENTS.md", "DESIGN.md", "GANTT.md", "TESTS_LOG.md"]
                else:
                    methodology_files = ["SCRUM_METHODOLOGY.md", "BACKLOG.md", "SPRINT_BOARD.md", "DAILY.md"]
                for f in methodology_files:
                    fp = os.path.join(state.active_project, f)
                    state.context_files.discard(fp)
                state.save_config(active_project="", project_methodology="scrum")
                state.refresh_static_context()
                console.print("[green]✓ Proyecto desvinculado del estado.[/green]")
            
            # Borrado físico
            shutil.rmtree(project_path)
            console.print(f"[bold green]✓ Carpeta y proyecto eliminados con éxito del disco duro.[/bold green]")
        except Exception as e:
            console.print(f"[red]Error al eliminar físicamente el proyecto: {e}[/red]")
    else:
        console.print("[yellow]Operación cancelada. No se modificó ningún archivo.[/yellow]")
