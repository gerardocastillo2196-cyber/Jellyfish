import os
import shutil
import threading
from rich.panel import Panel
from rich.prompt import Confirm
from prompt_toolkit import PromptSession
from core.ui import console
from core.ui import file_browser, interactive_picker
from core.tui import tui_engine, TaskProgress
from core.terminal import run_terminal_command

# Templates
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

def handle_project_command(command: str, arg: str, state, rag, display_header_func) -> None:
    if command == "/project":
        _handle_project(arg, state, rag, display_header_func)
    elif command == "/compile":
        _handle_compile(state)

def show_project_guide_if_needed(state) -> None:
    if not getattr(state, "show_guides", True):
        return
    if os.getenv("JELLYFISH_HIDE_PROJECT_GUIDE", "0") == "1":
        return

    active_path = getattr(state, "active_project", None)
    methodology = getattr(state, "project_methodology", "scrum").upper()
    agency = getattr(state, "active_agency", "default").upper()
    
    if active_path:
        project_status = f"VINCULADO ({active_path})"
    else:
        project_status = "NO VINCULADO (Escribe /project para crear o abrir uno)"

    guide_text = (
        f"ℹ️  ESTADO ACTUAL DEL PROYECTO: {project_status}\n"
        f"  • Metodología activa: {methodology}  • Agencia activa: {agency}\n"
        f"──────────────────────────────────────────────────────────────────────────────\n"
        f"🪼 ARQUITECTURA MULTI-AGENCIA (JELLYFISH OS v6.0)\n"
        f"Jellyfish OS ha evolucionado a un entorno corporativo Multi-Agencia. Los agentes\n"
        f"están agrupados de forma lógica bajo diferentes departamentos especializados:\n"
        f"  - DEVELOPMENT: Ingeniería de software, bugs, arquitectura y desarrollo.\n"
        f"  - MARKETING: Estrategias de venta, SEO, redacción de copy y contenido.\n"
        f"  - RESEARCH: Investigación profunda, análisis de mercado y ciencia de datos.\n"
        f"  - MANAGEMENT: Orquestación, Scrum Master y Product Owner de proyectos.\n"
        f"\n"
        f"🤖 EL CEO CLASIFICADOR (AGENCY ORCHESTRATOR)\n"
        f"Cuando ejecutas /auto <tu idea>, el **CEO invisible** de Jellyfish clasifica\n"
        f"tu prompt y lo deriva a la agencia más calificada. La agencia seleccionada\n"
        f"utilizará únicamente sus propios agentes especializados y generará su propio\n"
        f"tablero de control para evitar interferencias.\n"
        f"\n"
        f"📋 TABLEROS DE TRABAJO DINÁMICOS\n"
        f"Dependiendo de la agencia activa, Jellyfish orquesta el trabajo en tableros específicos:\n"
        f"  - Desarrollo / Default -> DEV_BOARD.md (o SPRINT_BOARD.md por retrocompatibilidad)\n"
        f"  - Marketing -> MKT_BOARD.md\n"
        f"  - Investigación -> RESEARCH_BOARD.md\n"
        f"\n"
        f"🔄 HANDOFFS INTER-AGENCIA (TRASPASOS)\n"
        f"Los Scrum Masters están entrenados para coordinar entregables cruzados. Si una tarea\n"
        f"excede la agencia activa, puede planificar un entregable (ej. un `COPY_LANDING.md` en\n"
        f"Marketing) para que sea consumido como insumo por la agencia de Desarrollo.\n"
        f"\n"
        f"🚀 GUÍA DE TRABAJO PASO A PASO\n"
        f"  PASO 1: Vincular o Crear un Proyecto\n"
        f"  • Ejecuta /project new ./mi-proyecto para inicializar tu espacio de trabajo.\n"
        f"  \n"
        f"  PASO 2: Navegar y Gestionar Agencias\n"
        f"  • Ejecuta /agency para listar el catálogo de agencias y sus agentes.\n"
        f"  • Ejecuta /agency switch <nombre> para cambiar manualmente de departamento.\n"
        f"  • Al cambiar de agencia, el autocompletador de agentes @ solo sugerirá personalidades\n"
        f"    pertinentes al departamento activo para mantener la estabilidad visual.\n"
        f"  \n"
        f"  PASO 3: Lanzar el Pipeline Autónomo\n"
        f"  • Escribe: /auto [Tu idea de proyecto]\n"
        f"    - Ejemplo: [italic]/auto Escribe una campaña publicitaria y diseña su landing page[/italic]\n"
        f"  • [bold]Fase 1 (PO)[/bold]: Diseña el `BACKLOG.md` con requerimientos de la agencia activa.\n"
        f"  • [bold]Fase 2 (SM)[/bold]: Desglosa tareas en el tablero específico de la agencia.\n"
        f"  • [bold]Fase 3 (Dev)[/bold]: Ejecución autónoma, depuración de lógica y compilación final.\n"
        f"  \n"
        f"  PASO 4: Interactuar con Agentes de la Agencia\n"
        f"  • Invoca personalidades con @agente (ej. @backend_dev).\n"
        f"  • Usa /add <archivo> para darles archivos del proyecto como contexto.\n"
        f"──────────────────────────────────────────────────────────────────────────────\n"
        f"👉 ¿Quieres ocultar esta guía? Escribe /Goff · Escribe /help para ver el manual de comandos."
    )
    console.print(Panel(guide_text, title="🪼 GUÍA DE CONSTRUCCIÓN MULTI-AGENCIA JELLYFISH OS", border_style="dim white"))

def _handle_project(arg: str, state, rag, display_header_func) -> None:
    sub = arg.strip()

    if sub.startswith("new "):
        raw_path = sub[4:].strip()
        if raw_path:
            _project_create(raw_path, state, rag, display_header_func)
            return
        console.print("Uso: /project new <ruta_del_proyecto>")
        return

    if sub == "info":
        _project_info(state)
        return

    if sub == "unlink":
        _project_unlink(state, display_header_func)
        return

    if sub in ("delete", "remove"):
        _project_delete(state, display_header_func)
        return

    if sub in ("reset-cb", "clear-cb", "reset-circuit-breaker"):
        _project_reset_circuit_breaker(state)
        return

    while True:
        action = interactive_picker(
            "GESTIÓN DE PROYECTOS",
            ["Crear / Abrir Proyecto", "Ver Proyecto Activo", "Desvincular Proyecto", "Eliminar Proyecto"]
        )
        if not action:
            break

        if action == "Crear / Abrir Proyecto":
            selected_dir = file_browser(".", header_func=display_header_func)
            if not selected_dir:
                break
            
            session = PromptSession()
            folder_name = session.prompt(
                f"Nombre de la carpeta a crear/usar dentro de:\n{selected_dir}\n(vacío para usar la seleccionada directamente): "
            ).strip()
            
            if folder_name:
                project_path = os.path.join(selected_dir, folder_name)
            else:
                project_path = selected_dir
                
            _project_create(project_path, state, rag, display_header_func)
            return

        elif action == "Ver Proyecto Activo":
            _project_info(state)
            input("\nPresiona Enter para continuar...")

        elif action == "Desvincular Proyecto":
            _project_unlink(state, display_header_func)
            break

        elif action == "Eliminar Proyecto":
            _project_delete(state, display_header_func)
            break

def _project_create(raw_path: str, state, rag, display_header_func, methodology: str = None) -> None:
    from datetime import datetime
    project_path = os.path.abspath(os.path.expanduser(raw_path))

    if not os.path.exists(project_path):
        if Confirm.ask(f"El directorio {project_path} no existe. ¿Crearlo?"):
            try:
                os.makedirs(project_path, exist_ok=True)
            except OSError as e:
                console.print(f"Error creando directorio: {e}")
                return
        else:
            console.print("Operación cancelada.")
            return

    if not methodology:
        methodology_choice = interactive_picker(
            "SELECCIONAR METODOLOGÍA",
            ["Scrum (Ágil)", "Cascada (Waterfall)"]
        )
        if not methodology_choice:
            console.print("Operación cancelada: No se seleccionó ninguna metodología.")
            return
        methodology = "scrum" if "Scrum" in methodology_choice else "cascada"

    today = datetime.now().strftime("%Y-%m-%d")

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
                console.print(f"Error escribiendo {filename}: {e}")

    methodology_label = "Scrum" if methodology == "scrum" else "Cascada"
    if created:
        console.print(f"✓ Archivos de metodología {methodology_label} creados: {', '.join(created)}")
    else:
        console.print(f"[dim]Los archivos de {methodology_label} ya existían, no se sobreescribieron.[/dim]")

    state.save_config(active_project=project_path, project_methodology=methodology)
    console.print(f"✓ Proyecto activo: {project_path} ({methodology_label})")

    for filename in methodology_files:
        filepath = os.path.join(project_path, filename)
        if os.path.isfile(filepath):
            state.context_files.add(filepath)
    state.refresh_static_context()

    if Confirm.ask("¿Indexar el proyecto en el RAG para análisis inteligente?", default=True):
        result = {"count": 0}

        def _index_worker():
            result["count"] = rag.index_codebase(project_path)

        thread = threading.Thread(target=_index_worker, daemon=True)
        thread.start()

        with TaskProgress(tui_engine, "project_rag", "Indexando proyecto con RAG..."):
            thread.join()

    input("\nPresiona Enter para continuar...")

def _project_info(state) -> None:
    if not state.active_project:
        console.print("⚠ No hay proyecto activo. Usa /project para crear uno.")
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
            status_lines.append(f"  ✓ {f} ({size:,} bytes)")
        else:
            status_lines.append(f"  ✗ {f} (no encontrado)")

    content = (
        f"Proyecto Activo: {state.active_project}\n\n"
        f"Metodología: {methodology.upper()}\n\n"
        f"Archivos de Seguimiento:\n" + "\n".join(status_lines)
    )
    console.print(Panel(content, title=title_label, border_style="dim white"))

def _project_unlink(state, display_header_func) -> None:
    if not state.active_project:
        console.print("⚠ No hay proyecto vinculado.")
        return

    old = state.active_project
    methodology = getattr(state, "project_methodology", "scrum").lower()

    if methodology == "cascada":
        methodology_files = ["WATERFALL_METHODOLOGY.md", "REQUIREMENTS.md", "DESIGN.md", "GANTT.md", "TESTS_LOG.md"]
    else:
        methodology_files = ["SCRUM_METHODOLOGY.md", "BACKLOG.md", "SPRINT_BOARD.md", "DAILY.md"]

    for f in methodology_files:
        fp = os.path.join(old, f)
        state.context_files.discard(fp)

    state.save_config(active_project="", project_methodology="scrum")
    state.refresh_static_context()
    console.print(f"✓ Proyecto desvinculado: {old}")

def _project_delete(state, display_header_func) -> None:
    project_path = state.active_project
    
    if not project_path:
        console.print("No hay un proyecto activo vinculado actualmente.")
        session = PromptSession()
        raw_path = session.prompt(
            "Introduce la ruta del proyecto a eliminar físicamente (o Enter para cancelar): "
        ).strip()
        if not raw_path:
            console.print("Operación cancelada.")
            return
        project_path = os.path.abspath(os.path.expanduser(raw_path))
    
    if not os.path.exists(project_path):
        console.print(f"Error: La ruta del proyecto no existe: {project_path}")
        return
        
    console.print(f"⚠️  ¡ADVERTENCIA DE ELIMINACIÓN FÍSICA! Se eliminará permanentemente la carpeta:")
    console.print(f"   {project_path}")
    console.print("   Todos los archivos y subcarpetas serán borrados de forma irrecuperable.")
    
    confirm = input("¿Estás absolutamente seguro? Escribe 'ELIMINAR' para confirmar: ").strip()
    
    if confirm == "ELIMINAR":
        try:
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
                console.print("✓ Proyecto desvinculado del estado.")
            
            try:
                shutil.rmtree(project_path)
                console.print(f"✓ Carpeta y proyecto eliminados con éxito del disco duro.")
            except Exception as pe:
                def _on_error(func, path, exc_info):
                    import stat
                    try:
                        os.chmod(path, stat.S_IREAD | stat.S_IWRITE | stat.S_IEXEC)
                        func(path)
                    except Exception:
                        pass
                try:
                    shutil.rmtree(project_path, onerror=_on_error)
                except Exception:
                    pass
                
                if os.path.exists(project_path):
                    import subprocess
                    try:
                        subprocess.run(["rm", "-rf", project_path], capture_output=True, text=True)
                    except Exception:
                        pass
                
                if os.path.exists(project_path):
                    console.print(f"Error de permisos al eliminar algunos archivos: {pe}")
                    console.print("Se requiere intervención manual o permisos de superusuario (sudo) para eliminar por completo la carpeta.")
                    console.print("Ejecuta en tu terminal host:")
                    console.print(f"   sudo rm -rf {project_path}\n")
                else:
                    console.print(f"✓ Carpeta y proyecto eliminados con éxito tras resolver permisos.")
        except Exception as e:
            console.print(f"Error al eliminar físicamente el proyecto: {e}")
    else:
        console.print("Operación cancelada. No se modificó ningún archivo.")

def _project_reset_circuit_breaker(state) -> None:
    if not state.active_project:
        console.print("⚠ No hay proyecto activo vinculado.")
        return
    
    cb_path = os.path.join(state.active_project, ".jellyfish_circuit_breaker")
    exit_code_path = os.path.join(state.active_project, ".jellyfish_last_exit_code")
    
    success = False
    for path in (cb_path, exit_code_path):
        if os.path.exists(path):
            try:
                os.remove(path)
                success = True
            except Exception as e:
                console.print(f"Error al eliminar {os.path.basename(path)}: {e}")
                
    if success:
        console.print("✓ Circuit Breaker restablecido. Puedes ejecutar /auto nuevamente.")
    else:
        console.print("[dim]El Circuit Breaker ya estaba limpio.[/dim]")

def _handle_compile(state) -> None:
    """Ejecuta el comando de compilación del proyecto activo en tiempo real."""
    if not state.active_project:
        console.print("⚠ No hay un proyecto activo vinculado. Usa /project primero.")
        return
        
    from core.project_orchestrator import ProjectOrchestrator
    orchestrator = ProjectOrchestrator(state)
    build_cmd = orchestrator._detect_compile_command()
    
    if not build_cmd:
        console.print("⚠ No se detectó ningún comando de compilación para este proyecto.")
        return
        
    console.print(f"🛠 Compilando proyecto activo con comando: {build_cmd}...")
    
    ret_dict = {'returncode': 0}
    run_terminal_command(build_cmd, state, return_code_dict=ret_dict)
    
    if ret_dict['returncode'] == 0:
        # Si compila con éxito manualmente, restablecer el circuit breaker del proyecto
        cb_path = os.path.join(state.active_project, ".jellyfish_circuit_breaker")
        exit_code_path = os.path.join(state.active_project, ".jellyfish_last_exit_code")
        for path in (cb_path, exit_code_path):
            if os.path.exists(path):
                try:
                    os.remove(path)
                except:
                    pass
        console.print("✓ Compilación exitosa. Circuit Breaker restablecido.")
