import os
import sys
import pydoc
from io import StringIO
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from prompt_toolkit import PromptSession
from core.state import get_term_width
from core.ui import console
from core.terminal import run_terminal_command

# Manual content from core/crud.py
_MANUAL = """
# 🪼 Jellyfish OS v5.1 — Manual del Usuario

Jellyfish es un framework de agentes técnicos impulsados por IA. Combina modelos locales o en la nube (Ollama, OpenAI, DeepSeek, OpenRouter) con ejecución autónoma (Auto-ReAct), recuperación de código vectorial (RAG) y un **Orquestador Multi-Agente** para investigaciones complejas.

---

## 📚 1. CONCEPTOS FUNDAMENTALES

**A. Contexto Activo vs. Contexto RAG**
*   **Contexto Activo:** Archivos añadidos con `/add` se cargan COMPLETOS en la memoria de la IA. Ideal para 1-4 archivos donde necesitas precisión absoluta.
*   **Contexto RAG (Indexación Vectorial):** Al hacer `/add` sobre una *carpeta*, Jellyfish trocea el código y lo guarda en una base vectorial (ChromaDB) aislada por proyecto. Cada pregunta recupera solo los fragmentos más relevantes.
*   **Importante:** El RAG ahora crea una base de datos separada por cada proyecto indexado (basada en el hash del directorio), evitando que el código de proyectos distintos se mezcle.

**B. Bucle Auto-ReAct (Autonomía y Permisos Dinámicos)**
Cuando el modelo o el Task Runner sugieren comandos Bash, Jellyfish detiene la ejecución para pedir confirmación interactiva a través de un sistema de permisos:
*   `[y] Permitir una vez:` Ejecuta el comando actual de forma aislada.
*   `[n] Denegar:` Detiene de forma segura y devuelve un mensaje de cancelación al agente.
*   `[a] Permitir siempre para este proyecto:` Activa la auto-aprobación permanente para el proyecto actual, persistiendo la decisión en `.jellyfish_project_config.json`.
*   **Lista negra rígida:** Los comandos destructivos (como `rm` recursivo destructivo, `mkfs`, `fdisk`, `dd of=/dev/`, `chmod`/`chown` masivos en directorios raíz, y `curl | sh`) se abortan de inmediato y reportan un incidente de seguridad, sin dar opción de omisión al usuario.
*   **Auto-rechazo:** Si no respondes en 60 segundos, el comando se rechaza automáticamente.
*   **Ctrl+C grácil:** Interrumpir el stream conserva la respuesta parcial ya recibida sin matar Jellyfish.

**C. Orquestador Multi-Agente (`/research`)**
Un sistema de 4 fases para consultas complejas: **Planificación → Búsqueda en RAG → Síntesis → Citación**. Los subagentes trabajan en silencio y solo el reporte final se muestra en pantalla. Al terminar se imprime una tabla con el tiempo de cada fase.

---

## ⚙️ 2. CONFIGURACIÓN DEL SISTEMA

### `/model` — Selector Interactivo de Modelos
*   `/model` (o `/m`): Abre un selector interactivo en TUI para elegir rápidamente el proveedor (Ollama, Gemini, Claude) y el modelo específico a utilizar.

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

## 📁 6. GESTIÓN DE PROYECTOS Y GUÍAS DE CONSTRUCCIÓN

### `/project <ruta>` — Aislamiento y Entornos Virtuales
*   `/project [ruta_directorio]` — Carga o inicializa un proyecto Scrum o Cascada en Jellyfish.
*   **Aislamiento automático:** Al cargar un proyecto con código Python, Jellyfish crea automáticamente un entorno virtual `.venv` y lo activa para aislar todas las instalaciones de dependencias del sistema host.
*   **Locks de concurrencia:** Crea un lock en la raíz del proyecto para evitar colisiones de ChromaDB o archivos si se abre en otra sesión de Jellyfish.

### Guías de Construcción (`/gon` y `/goff`)
*   `/gon` — Activa la guía interactiva del proyecto para sprints y metodología Scrum.
*   `/goff` — Desactiva las guías interactivas para una experiencia de chat más limpia.

### `/compile` — Compilación y Verificación de Integridad
*   `/compile` — Lanza la compilación del proyecto utilizando la detección automática de herramientas (ej. Java, Node, Python) en un entorno de ejecución seguro.

---

## 🚀 7. HERRAMIENTAS DE SISTEMA

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

## 🔑 8. VARIABLES DE ENTORNO AVANZADAS (`.env`)

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
| `/project <ruta>` | — | Cargar/Crear un proyecto Scrum o Cascada |
| `/compile` | — | Compilar y validar el proyecto activo |
| `/gon` | — | Activar guías del proyecto (Guides On) |
| `/goff` | — | Desactivar guías del proyecto (Guides Off) |
| `/purge` | — | Borrar todo contexto y RAG |
| `/agent` | `/a` | Gestionar agentes |
| `/skill` | `/s` | Gestionar habilidades |
| `/run <cmd>` | `/r` | Ejecutar comando en terminal |
| `/plugin [nombre]` | — | Ejecutar plugin en sandbox |
| `/config [opción]` | — | Configurar proveedor/modelo/keys |
| `/ignore [opción]` | — | Registrar .jellyfishignore |
| `/errors` | `/debug`, `/d` | Ver y diagnosticar errores de la sesión con IA |
| `/provider` | — | Ver proveedor activo |
| `/clear` | — | Limpiar historial de chat |
| `/help` | `/h` | Este manual |
| `/exit` | — | Cerrar Jellyfish |

"""

def handle_system_command(command: str, arg: str, state, plugins, display_header_func) -> None:
    if command == "/goff":
        state.show_guides = False
        state.save_config(show_guides="0")
        from core.tui import tui_engine
        if tui_engine._initialized:
            tui_engine.clear_scroll_region()
        else:
            os.system("cls" if os.name == "nt" else "clear")
            tui_engine.print_welcome_logo()
        display_header_func()
        console.print("🪼 Guías del proyecto DESACTIVADAS. Escribe /Gon para volver a activarlas.")

    elif command == "/gon":
        state.show_guides = True
        state.save_config(show_guides="1")
        from core.tui import tui_engine
        if tui_engine._initialized:
            tui_engine.clear_scroll_region()
        else:
            os.system("cls" if os.name == "nt" else "clear")
            tui_engine.print_welcome_logo()
        display_header_func()
        from core.commands.project import show_project_guide_if_needed
        show_project_guide_if_needed(state)

    elif command == "/clear":
        state.reset_history()
        from core.tui import tui_engine
        if tui_engine._initialized:
            tui_engine.clear_scroll_region()
            tui_engine.move_cursor_to_scroll_region()
            display_header_func()
            from core.commands.project import show_project_guide_if_needed
            show_project_guide_if_needed(state)
        else:
            os.system("cls" if os.name == "nt" else "clear")
            tui_engine.print_welcome_logo()
            display_header_func()
            from core.commands.project import show_project_guide_if_needed
            show_project_guide_if_needed(state)

    elif command == "/help":
        _show_help(display_header_func)

    elif command == "/run":
        if not arg:
            arg = PromptSession().prompt("Comando: ").strip()
        if arg:
            run_terminal_command(arg, state)

    elif command == "/plugin":
        _handle_plugin(arg, plugins, state)

    elif command in ("/errors", "/debug"):
        _handle_errors_command(state, display_header_func)

def _handle_errors_command(state, display_header_func) -> None:
    """Muestra y diagnostica los errores capturados en la sesión."""
    from core.tui import tui_engine
    from core.ui import handle_exit_flow
    
    errors = getattr(state, "captured_errors", [])
    if not errors:
        console.print("✓ No se han capturado errores en esta sesión.")
        return

    if tui_engine._initialized:
        tui_engine.restore_terminal()
        handle_exit_flow(state)
        tui_engine.init_terminal()
        display_header_func()
    else:
        handle_exit_flow(state)

def _show_help(display_header_func):
    """Muestra la guía de comandos y manual completo."""
    from core.tui import tui_engine
    if tui_engine._initialized:
        tui_engine.restore_terminal()
        import pydoc
        from io import StringIO
        buf = StringIO()
        temp_console = Console(file=buf, force_terminal=True, width=min(120, get_term_width()))
        temp_console.print(Panel(Markdown(_MANUAL), border_style="dim white"))
        pydoc.pager(buf.getvalue())
        tui_engine.init_terminal()
        display_header_func()
        tui_engine.move_cursor_to_scroll_region()
    else:
        console.print(Panel(Markdown(_MANUAL), border_style="dim white"))

def _handle_plugin(arg: str, plugins, state):
    """Procesa el comando /plugin."""
    if not arg:
        listing = plugins.list_plugins()
        console.print(Panel(listing, title="Plugins Disponibles", border_style="dim white"))
        return

    p_parts = arg.split(" ", 1)
    p_name = p_parts[0]
    p_args = p_parts[1] if len(p_parts) > 1 else ""

    res = plugins.run_plugin(p_name, p_args)
    console.print(Panel(str(res), title=f"Plugin: {p_name}", border_style="dim white"))
    state.history.append({
        "role": "system",
        "content": f"[PLUGIN {p_name}]\n{res}"
    })
