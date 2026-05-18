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

from core.state import AGENCY_DIR
from core.terminal import run_terminal_command
from core.ui import interactive_picker, file_browser, print_panel, print_code, console as ui_console

logger = logging.getLogger("jellyfish.crud")
console = Console()

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
        "/h": "/help",
    }
    command = aliases.get(command, command)

    if command == "/exit":
        console.print("[bold purple]🪼 Jellyfish desconectado. Hasta pronto.[/bold purple]")
        sys.exit(0)

    elif command == "/clear":
        state.reset_history()
        display_header_func()

    elif command == "/help":
        _show_help()

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

    else:
        console.print(f"[yellow]Comando desconocido: {command}. Usa /help.[/yellow]")


def _show_help():
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
*   `/config provider [nombre]` — Opciones: `ollama`, `openai`, `deepseek`, `openrouter`.
*   `/config model [nombre]` — Cambia el modelo activo (ej. `gpt-4o`, `qwen2.5:32b`).
*   `/config key [proveedor] [valor]` — Guarda una API Key en `.env` con permisos `600` automáticos.
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

### `/plugin` — Sistema Modular Python (Sandbox)
*   Los plugins son archivos `.py` en `agencia/plugins/` con una función `execute(args) -> str`.
*   `/plugin`: Lista los plugins disponibles con su descripción.
*   `/plugin [nombre] [args]`: Ejecuta el plugin en un **subproceso aislado** con timeout de 30s.
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
| `JELLYFISH_PROVIDER` | `ollama` | Proveedor de IA principal |
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
    console.print(Panel(Markdown(manual), border_style="cyan"))


def _show_provider_info(state):
    """Muestra información del proveedor de IA activo."""
    console.print(Panel(
        f"[bold]Proveedor:[/bold] {state.provider.upper()}\n"
        f"[bold]Modelo:[/bold] {state.model}\n"
        f"[bold]Tipo:[/bold] {'☁️  Nube' if state.provider != 'ollama' else '🖥️  Local (Ollama)'}",
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
    content = (
        f"[bold cyan]Proveedor Activo:[/bold cyan] {state.provider.upper()}\n"
        f"[bold cyan]Modelo Activo:[/bold cyan] {state.model}\n\n"
        f"[bold cyan]🔑 API Keys en .env:[/bold cyan]\n"
        f"  • OpenAI Key:     {_mask_key(state.openai_api_key)}\n"
        f"  • DeepSeek Key:   {_mask_key(state.deepseek_api_key)}\n"
        f"  • OpenRouter Key: {_mask_key(state.openrouter_api_key)}\n\n"
        f"[bold cyan]⚙️ RAG:[/bold cyan]\n"
        f"  • Embeddings:     {state.embed_model}\n"
        f"  • Umbral (L2):    {state.relevance_threshold}\n"
    )
    console.print(Panel(content, title="⚙️ CONFIGURACIÓN JELLYFISH", border_style="cyan"))


def _handle_config(arg: str, state, display_header_func):
    """Manejador del comando /config."""
    sub = arg.strip().lower()

    if not sub or sub == "show":
        _show_current_config(state)
        input("\nPresiona Enter para continuar...")
        return

    # --- Comandos CLI directos ---
    # /config provider [name]
    if sub.startswith("provider"):
        parts = sub.split(" ", 1)
        prov = parts[1].strip() if len(parts) > 1 else ""
        if prov not in ["ollama", "openai", "deepseek", "openrouter"]:
            console.print("[red]Proveedor inválido. Opciones: ollama, openai, deepseek, openrouter[/red]")
        else:
            state.save_config(provider=prov)
            console.print(f"[green]✓ Proveedor cambiado a: {prov}[/green]")
            display_header_func()
        return

    # /config model [name]
    elif sub.startswith("model"):
        parts = sub.split(" ", 1)
        mod = parts[1].strip() if len(parts) > 1 else ""
        if not mod:
            console.print("[red]Por favor especifica el nombre del modelo.[/red]")
        else:
            state.save_config(model=mod)
            console.print(f"[green]✓ Modelo cambiado a: {mod}[/green]")
            display_header_func()
        return

    # /config key [openai|deepseek|openrouter] [value]
    elif sub.startswith("key"):
        parts = sub.split(" ")
        if len(parts) < 3:
            console.print("[red]Uso: /config key <openai|deepseek|openrouter> <valor_clave>[/red]")
            return
        target_prov = parts[1].lower()
        key_val = parts[2].strip()
        
        if target_prov == "openai":
            state.save_config(openai_key=key_val)
        elif target_prov == "deepseek":
            state.save_config(deepseek_key=key_val)
        elif target_prov == "openrouter":
            state.save_config(openrouter_key=key_val)
        else:
            console.print("[red]Proveedor de key desconocido. Opciones: openai, deepseek, openrouter[/red]")
            return
        console.print(f"[green]✓ API Key de {target_prov} actualizada en .env.[/green]")
        return

    # --- Menú Interactivo ---
    if sub == "interactive" or sub == "menu":
        while True:
            action = interactive_picker(
                "CONFIGURACIÓN JELLYFISH",
                ["Ver Configuración", "Cambiar Proveedor", "Cambiar Modelo", "Configurar API Keys"]
            )
            if not action:
                break

            session = PromptSession()

            if action == "Ver Configuración":
                _show_current_config(state)
                input("\nPresiona Enter para continuar...")

            elif action == "Cambiar Proveedor":
                prov = interactive_picker("SELECCIONAR PROVEEDOR", ["ollama", "openai", "deepseek", "openrouter"])
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

            elif action == "Configurar API Keys":
                key_type = interactive_picker("SELECCIONAR KEY A CONFIGURAR", ["OpenAI Key", "DeepSeek Key", "OpenRouter Key"])
                if key_type == "OpenAI Key":
                    val = session.prompt("OpenAI API Key: ", default=state.openai_api_key).strip()
                    state.save_config(openai_key=val)
                elif key_type == "DeepSeek Key":
                    val = session.prompt("DeepSeek API Key: ", default=state.deepseek_api_key).strip()
                    state.save_config(deepseek_key=val)
                elif key_type == "OpenRouter Key":
                    val = session.prompt("OpenRouter API Key: ", default=state.openrouter_api_key).strip()
                    state.save_config(openrouter_key=val)
                
                if key_type:
                    console.print("[green]✓ API Key guardada exitosamente en .env.[/green]")
                    input("\nPresiona Enter para continuar...")

        display_header_func()


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
                    "node_modules/", "code_vector_db/", "test_db/",
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
            "node_modules/", "code_vector_db/", "test_db/",
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
    path = file_browser(arg if arg else ".")
    if not path:
        return

    if os.path.isdir(path):
        state.add_context_directory(path)
        # Indexar con RAG en hilo secundario con spinner
        console.print()
        result = {"count": 0}

        def _index_worker():
            result["count"] = rag.index_codebase(path)

        thread = threading.Thread(target=_index_worker, daemon=True)
        thread.start()

        # Mostrar spinner mientras se indexa
        with Live(
            Spinner("dots", text="[bold blue]Indexando código con RAG...[/bold blue]"),
            console=console,
            refresh_per_second=10
        ):
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

    else:
        console.print(
            "[cyan]Uso:[/cyan]\n"
            "  /rag status         — Ver estado del índice\n"
            "  /rag clear          — Eliminar el índice completo\n"
            "  /rag reindex <path> — Reindexar una ruta\n"
            "  /rag remove <path>  — Eliminar una ruta del índice"
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
