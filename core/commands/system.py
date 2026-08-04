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
# 🪼 Jellyfish OS v6.9.15 — Manual del Usuario

Jellyfish OS v6.9.15 es un sistema operativo y framework corporativo de agentes técnicos cognitivos impulsados por IA. Integra el **Enjambre Multi-Agencia (Swarm Architecture)** con enrutamiento heterogéneo (Ollama, Gemini 3.x Flash, Claude, Groq, OpenAI), ejecución autónoma y auto-reparación determinística (Auto-ReAct & Auto-Healing), recuperación de código vectorial con AST Splitter (RAG) y el **Mega Planner** para orquestar desarrollos y proyectos de software complejos en entornos Linux.

---

## 📚 1. CONCEPTOS FUNDAMENTALES & ARQUITECTURA SWARM

**A. Enrutador Heterogéneo (Swarm Router)**
En v6.9.15, los agentes se organizan en **Agencies & Swarms**. El `SwarmRouter` enruta cada rol al modelo y proveedor más eficiente:
*   **Agentes de Auditoría & Crítica (`@qa_engineer`, `@security_auditor`, `@critic`):** Enrutados a modelos de baja latencia y alta precisión lógica (ej. Groq / Llama 3.3 70B o modelos QA dedicados) para evaluación ultrarrapida sin sesgo de autor.
*   **Agentes Constructores & Planificadores (`@developer`, `@architect`, `@scrum_master`):** Enrutados a modelos con ventanas de contexto masivo y alta capacidad de codificación y razonamiento extensivo (ej. Gemini 3.6 Flash / Pro, Claude 3.5, OpenAI, o Qwen 2.5 local).

**B. Contexto Activo vs. Contexto RAG Inteligente (Auto-Habilitado)**
*   **Estado RAG por Defecto (OFF):** Para optimizar la memoria y latencia, el motor vectorial inicia en estado `OFF` por defecto en v6.9.15. Se activa de forma 100% automática tan pronto se realiza un import o ingesta de código con el comando `/add`.
*   **Contexto Activo:** Archivos individuales añadidos con `/add` se cargan completos en memoria de la IA. Ideal para precisión absoluta en 1-4 archivos de edición directa.
*   **Contexto RAG (Indexación Vectorial AST):** Al importar carpetas completas, Jellyfish procesa el código utilizando transformadores y analizadores AST en Python para mantener integras funciones y clases, indexándolas en bases ChromaDB separadas y aisladas con hash criptográfico por cada proyecto.

**C. Bucle Auto-ReAct & Auto-Healing Determinístico**
Cuando los agentes proponen comandos de terminal o modificaciones sobre el proyecto, intervienen los mecanismos reactivos de seguridad:
*   `[y] Permitir una vez:` Ejecuta el comando o cambio de forma aislada.
*   `[n] Denegar:` Detiene con seguridad y devuelve un mensaje explícito de cancelación al agente.
*   `[a] Permitir siempre para este proyecto:` Persiste el permiso de auto-aprobación en `.jellyfish_project_config.json`.
*   **Auto-Healing & Parcheo Determinístico (`BuildHealer`):** Desvinculado del orquestador monolítico clásico, este motor repara compilaciones fallidas y aplica diffs o parches granulares de forma determinística con hasta 3 intentos por fallo antes de activar un Circuit Breaker.
*   **Lista Negra & Sandbox:** Bloquea de raíz cualquier comando destructivo (`rm -rf /`, `dd`, `mkfs`, fork bombs) y ejecuta plugins o extensiones aislando sistema de archivos y red mediante `bubblewrap`.

---

## ⚙️ 2. CONFIGURACIÓN DEL SISTEMA

### `/model` (alias: `/m`) — Selector Interactivo TUI de Modelos & Swarm
*   Abre el selector interactivo para cambiar modelos generales, de planificación o enrutamiento híbrido entre Ollama (locales) y nube (Gemini, OpenRouter, Claude, Groq, OpenAI).

### `/config` — Panel de Configuración Hot-Reload
*   `/config` (o `/config menu`): Menú de configuración para ver/editar proveedores, modelos del enjambre y API keys.
*   `/config providers` — Muestra el catálogo de proveedores y endpoints activos.
*   `/config provider [nombre]` — Opciones: `ollama`, `gemini`, `openai`, `claude`, `groq`, `openrouter`, `deepseek`, `qwen`, `kimi`, `zhipu`, `custom`.
*   `/config model [nombre]` — Define el modelo del Lead Agent o ejecutor.
*   `/config key [proveedor] [valor]` — Almacena de forma segura (con `chmod 600`) la llave API en el archivo `.env`.
*   `/config endpoint [proveedor] [base_url]` — Customiza URLs base para endpoints compatibles.
*   `/config subagent_model / subagent_provider` — Define modelos para sub-agentes del enjambre de investigación.

### `/ignore` — Filtros de Ingesta (.jellyfishignore)
*   `/ignore` (o `/ignore menu`): Gestión interactiva de exclusiones RAG.
*   `/ignore init`: Genera `.jellyfishignore` estándar (`.venv`, `node_modules`, `build`, `__pycache__`...).

---

## 🧠 3. GESTIÓN DEL RAG Y CONTEXTO

### `/add` — Ingesta e Indexación Auto-Activada
*   `/add`: Abre explorador de archivos. Al ingresar una carpeta, activa el motor RAG del proyecto e indexa inteligentemente mediante AST.

### `/context` (alias: `/c`) — Inspector de Contexto Activo
*   Muestra, revisa y permite desvincular o depurar archivos cargados actualmente en memoria activa.

### `/rag` — Panel del Motor Vectorial
*   `/rag status`: Visualiza el estado, chunks indexados y si el motor se encuentra en `ON` (activo) u `OFF` (en espera).
*   `/rag reindex / remove / clear`: Gestión granular de reconstrucción y limpieza de índices por proyecto.

### `/purge` — Reinicio de Contexto (Amnesia)
*   Purga la memoria activa del chat y limpia la base vectorial del proyecto en curso.

---

## 🤖 4. ORQUESTADOR MULTI-AGENTE & MEGA PLANNER

### `/research <consulta>` — Investigación Autónoma Multi-Agente
Pipeline en 4 etapas para consultas arquitectónicas o técnicas profundas sobre tu repositorio:
1.  **🗺 Lead Planner:** Descomposición algorítmica del problema y planificación en JSON.
2.  **🔍 Search Agents:** Consulta reactiva y silenciosa en la base de conocimiento local (RAG).
3.  **✍ Lead Synthesizer:** Redacción de informe con streaming interactivo TUI.
4.  **📚 Citation Agent:** Validación de referencias con enlaces directos `file://`.

### `/auto <descripción>` (alias: `/build`) — Agencia Autónoma de Desarrollo con Mega Planner
Orquesta el ciclo de vida de ingeniería y sprint completo con 5 agentes cognitivos especializados:
1.  **📝 Product Owner:** Redacción del `BACKLOG.md` con historias de usuario priorizadas **(✋ Checkpoint de aprobación)**.
2.  **📋 Scrum Master & Mega Planner:** Descomposición estructural y creación del tablero `SPRINT_BOARD.md` con tareas secuenciales.
3.  **🏗️ Arquitecto:** Diseño e infraestructura en `ARCHITECTURE.md` (con Sprint 0 / US-000 obligatorio para configuración base).
4.  **💻 Developer:** Desarrollo e implementación granular (`IMPLEMENTATION_PLAN.md`).
5.  **🧪 QA Engineer:** Estrategia de validación y testeo continuo (`TEST_PLAN.md`) supervisada por Circuit Breaker (El Juez).

---

## 🛠️ 5. AGENTES Y HABILIDADES (SKILLS)

### `/agent` (alias: `/a`) — Taller de Agencias & Personalidades
*   Administra las agencias especializadas (DEVELOPMENT, MARKETING, etc.) y carga roles persistenes desde archivos `.md`.

### `@<nombre>` — Activación Instantánea de Agente
*   Escribe `@developer`, `@qa_engineer`, `@architect`, `@sentinel`, `@marketing_strategist`, etc. para conmutar al instante. autocompletado disponible con Tab.

### `/skill` (alias: `/s`) — Macros & Habilitadores Automatizados
*   Ejecución y registro de macros seguras para automatizar tareas repetitivas de terminal (deployments, git, test pipelines).

---

## 📁 6. PROYECTOS, AISLAMIENTO VIRTUAL & GUÍAS

### `/project <ruta>` — Gestión y Entornos `.venv`
*   Carga un repositorio como proyecto activo en Jellyfish. Crea de manera automática un entorno virtual Python `.venv` aislado del sistema operativo raíz y aplica bloqueos concurrentes (locks) contra colisiones temporales.

### Guías de Construcción (`/gon` y `/goff`)
*   `/gon` / `/goff`: Activa o deshabilita la asistencia didáctica de metodología ágil y convenciones durante el chat.

### `/compile` — Verificación e Integridad
*   Ejecuta las herramientas de build detectadas (Python, Node, Java/Gradle) en el sandbox con supervisión del módulo `BuildHealer`.

---

## 🚀 7. HERRAMIENTAS DE SISTEMA & PLUGIN SANDBOXING

### `/run` (alias: `/r`) — Terminal Seguro Integrado
*   Ejecuta comandos Bash con truncamiento inteligente en logs e inspección de seguridad en tiempo real.

### `/plugin` — Extensiones con Aislamiento Bubblewrap
*   `/plugin`: Visualiza o ejecuta módulos Python de terceros en entornos restringidos sin acceso al sistema raíz ni claves.
*   Desactivable bajo propio riesgo con `JELLYFISH_PLUGIN_UNSAFE=1`.

### `/clear`, `/provider`, `/errors`, `/status`
*   Comandos de inspección TUI para diagnosticar fallos (`/errors`), verificar configuración activa (`/provider`, `/status`) o limpiar vista (`/clear`).

---

## 🔑 8. VARIABLES DE ENTORNO AVANZADAS (`.env`)

| Variable | Default | Descripción |
|---|---|---|
| `JELLYFISH_PROVIDER` | `ollama` | Proveedor principal (`ollama`, `gemini`, `openai`, `claude`, `groq`, `openrouter`...) |
| `JELLYFISH_MODEL` | `qwen2.5-coder:latest` | Modelo de ejecución general / código |
| `JELLYFISH_PLANNER_MODEL` | `gemini-3.6-flash` | Modelo por defecto para el Lead Planner en Swarm |
| `JELLYFISH_QA_MODEL` | `llama-3.3-70b-versatile` | Modelo para auditorías QA (Groq / local) |
| `JELLYFISH_USE_HYBRID` | `1` | Activa enrutamiento heterogéneo (SwarmRouter) |
| `JELLYFISH_CONTEXT_LIMIT` | `8192` | Capacidad máxima del historial en tokens |
| `JELLYFISH_PLUGIN_UNSAFE` | `0` | `1` deshabilita aislamiento Bubblewrap en plugins |

---

## ⚡ REFERENCIA RÁPIDA DE COMANDOS v6.9.15

| Comando | Alias | Función |
|---|---|---|
| `/model` | `/m` | Selector interactivo de modelos y Swarm TUI |
| `/config` | — | Configurar proveedor, modelos o API keys |
| `/add` | — | Añadir archivo o carpeta y activar RAG auto-habilitado |
| `/context` | `/c` | Inspector de memoria y archivos activos |
| `/rag` | — | Monitor del índice vectorial AST |
| `/project` | `/p` | Cargar o crear proyecto y entorno aislado `.venv` |
| `/auto` | `/build` | Orquestar agencia autónoma con Mega Planner |
| `/research` | — | Investigación profunda multi-agente en 4 etapas |
| `/agent` | `/a` | Administrar personalidades de agentes cognitivos |
| `/skill` | `/s` | Gestor de macros y habilidades |
| `/run` | `/r` | Terminal seguro sin salir del sistema |
| `/compile` | — | Compilar proyecto con supervisión BuildHealer |
| `/gon` / `/goff` | — | Habilitar / deshabilitar guías ágiles interactivas |
| `/plugin` | — | Módulo de extensiones bajo sandbox Bubblewrap |
| `/ignore` | — | Control del archivo `.jellyfishignore` |
| `/errors` | `/d` | Monitor de excepciones del sistema |
| `/status` | `/info` | Diagnóstico completo de configuración y sesión |
| `/purge` | — | Amnesia total: limpiar historial, RAG y memoria |
| `/clear` | — | Limpiar pantalla de terminal |
| `/help` | `/h` | Visualizar este manual v6.9.15 |
| `/exit` | — | Cerrar Jellyfish OS en orden y apagar servicios |

"""r proveedor activo |
| `/status` | `/info` | Ver el estado actual del sistema y la configuración activa |
| `/purge` | — | Borrar todo contexto y RAG |
| `/clear` | — | Limpiar historial de chat |
| `/help` | `/h` | Este manual |
| `/exit` | — | Cerrar Jellyfish |

"""

def handle_system_command(command: str, arg: str, state, plugins, display_header_func) -> None:
    if command == "/goff":
        state.show_guides = False
        state.save_config(show_guides="0")
        os.system("cls" if os.name == "nt" else "clear")
        from core.tui import tui_engine
        tui_engine.print_welcome_logo()
        display_header_func(force=True)
        console.print("🪼 Guías del proyecto DESACTIVADAS. Escribe /gon para volver a activarlas.")

    elif command == "/gon":
        state.show_guides = True
        state.save_config(show_guides="1")
        os.system("cls" if os.name == "nt" else "clear")
        from core.tui import tui_engine
        tui_engine.print_welcome_logo()
        display_header_func(force=True)
        from core.commands.project import show_project_guide_if_needed
        show_project_guide_if_needed(state)

    elif command == "/clear":
        state.reset_history()
        os.system("cls" if os.name == "nt" else "clear")
        from core.tui import tui_engine
        tui_engine.print_welcome_logo()
        display_header_func(force=True)
        from core.commands.project import show_project_guide_if_needed
        show_project_guide_if_needed(state)

    elif command == "/status":
        display_header_func(force=True)

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
    from core.ui import handle_exit_flow
    
    errors = getattr(state, "captured_errors", [])
    if not errors:
        console.print("✓ No se han capturado errores en esta sesión.")
        return

    handle_exit_flow(state)

def _show_help(display_header_func):
    """Muestra la guía de comandos y manual completo."""
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
