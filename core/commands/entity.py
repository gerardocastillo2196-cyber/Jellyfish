import os
import re
from rich.prompt import Confirm
from prompt_toolkit import PromptSession
from core.ui import console
from core.config import AGENCY_DIR
from core.ui import (
    interactive_picker, print_panel, print_code
)

_UNSAFE_FILENAME_RE = re.compile(r'[^\w\s\-.]', re.UNICODE)

def _sanitize_name(name: str) -> str:
    """Sanitiza un nombre para uso seguro como nombre de archivo.

    Elimina caracteres especiales que podrían causar problemas
    en el sistema de archivos o inyección en Markdown/Python.
    """
    clean = _UNSAFE_FILENAME_RE.sub('', name).strip()
    clean = clean.replace(' ', '_')
    return clean.lower() if clean else ""

def detailed_interview(type_key: str) -> str | None:
    """Entrevista guiada para crear un agente o habilidad en formato Python (.py)."""
    session = PromptSession()

    if type_key == "agents":
        console.print("🎭 FORJA AVANZADA DE AGENTE (PYTHON)")
        raw_name = session.prompt("1. Alias (ej. arquitecto_software): ").strip()
        name = _sanitize_name(raw_name)
        if not name:
            console.print("⚠ Nombre inválido o vacío.")
            return None
        rol = session.prompt("2. Rol Principal: ").strip()
        contexto = session.prompt("3. Contexto Operativo: ").strip()
        tono = session.prompt("4. Tono: ").strip()
        conocimiento = session.prompt("5. Expertise (separada por comas): ").strip()
        regla = session.prompt("6. Regla Inquebrantable: ").strip()
        ejemplo = session.prompt("7. Ejemplo de Interacción [Opcional]: ").strip()
        agency = session.prompt("8. Agencia (ej. development, devops, custom) [default]: ").strip().lower() or "default"

        class_name = "".join(word.capitalize() for word in name.split("_")) + "Agent"
        expertise_list = [x.strip() for x in conocimiento.split(",") if x.strip()]
        directives_list = [ejemplo] if ejemplo else []
        rules_list = [regla] if regla else []

        content = f'''"""Agente: @{name} — {rol}."""
from core.agents.base import BaseAgent


class {class_name}(BaseAgent):
    """{rol}"""

    def __init__(self):
        super().__init__(
            name="{name}",
            agency="{agency}",
            role="{rol}",
            context="{contexto}",
            tone="{tono}",
            expertise={expertise_list},
            directives={directives_list},
            rules={rules_list},
        )
'''
        path = os.path.join(AGENCY_DIR, "agents", f"{name}.py")

    else:
        console.print("🛠️ FORJA AVANZADA DE HABILIDAD (PYTHON)")
        raw_name = session.prompt("1. Nombre (ej. Async Messaging): ").strip()
        name = _sanitize_name(raw_name)
        if not name:
            console.print("⚠ Nombre inválido o vacío.")
            return None
        obj = session.prompt("2. Propósito / Objetivo: ").strip()
        trigger = session.prompt("3. Activación (Trigger): ").strip()
        deps = session.prompt("4. Dependencias Linux: ").strip()
        comando = session.prompt("5. Comando(s) Bash: ").strip()
        errores = session.prompt("6. Manejo de Errores: ").strip()
        keywords = session.prompt("7. Palabras clave (keywords separadas por coma): ").strip()
        agency = session.prompt("8. Agencia (ej. development, devops, custom) [custom]: ").strip().lower() or "custom"

        class_name = "".join(word.capitalize() for word in name.split("_")) + "Skill"
        keywords_list = [x.strip().lower() for x in keywords.split(",") if x.strip()]
        
        safe_comando = comando.replace('"""', '\\"\\"\\"')
        safe_errores = errores.replace('"""', '\\"\\"\\"')

        content = f'''"""Skill: {raw_name}."""
from core.skills.base import BaseSkill


class {class_name}(BaseSkill):
    """{obj}"""

    name = "{raw_name}"
    agency = "{agency}"
    keywords = {keywords_list}

    def get_instructions(self) -> str:
        return """## {raw_name}

**Agencia:** {agency}

## Objetivo de la Skill
{obj}

## Activación (Trigger)
{trigger}

## Dependencias
{deps}

## Instrucción
```bash
{safe_comando}
```

## Manejo de Errores
{safe_errores}"""
'''
        path = os.path.join(AGENCY_DIR, "skills", agency, f"{name}.py")

    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        console.print(f"✓ @{name} forjado profesionalmente en {os.path.basename(path)}.")
        return name
    except (OSError, IOError) as e:
        console.print(f"Error guardando: {e}")
        return None

def handle_entity_command(command: str, arg: str, state, display_header_func) -> None:
    entity_type = "agents" if command == "/agent" else "skills"
    handle_crud(entity_type, state, display_header_func)

def handle_crud(entity_type: str, state, display_header_func=None) -> None:
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

        items_map = {}
        for root_dir, _, files in os.walk(base_dir):
            for file in sorted(files):
                if file.endswith((".py", ".md")) and not file.startswith("__") and file not in ("base.py", "registry.py", "template.md"):
                    rel_path = os.path.relpath(os.path.join(root_dir, file), base_dir)
                    name_key = rel_path[:-3]
                    ext = rel_path[-3:]
                    # Priorizar archivos Python (.py)
                    if name_key not in items_map or ext == ".py":
                        items_map[name_key] = ext

        items = sorted(list(items_map.keys()))

        if action == "cargar":
            if not items:
                console.print(f"No hay {plural.lower()} disponibles.")
                continue
            name = interactive_picker("SELECCIONAR", items)
            if name:
                ext = items_map[name]
                if entity_type == "agents":
                    state.load_agent(name)
                else:
                    state.active_skills.add(os.path.join(base_dir, f"{name}{ext}"))
                    state.refresh_static_context()
                break

        elif action == "añadir":
            name = detailed_interview(entity_type)
            if name:
                state.scan_agencies()
                state.refresh_static_context()

        elif action == "editar":
            if not items:
                console.print(f"No hay {plural.lower()} para editar.")
                continue
            name = interactive_picker("EDITAR", items)
            if name:
                ext = items_map[name]
                path = os.path.join(base_dir, f"{name}{ext}")
                try:
                    with open(path, "r", encoding="utf-8", errors="ignore") as f:
                        old = f.read()
                    new = PromptSession().prompt(f"Editando @{name}: ", default=old)
                    if new.strip():
                        with open(path, "w", encoding="utf-8") as f:
                            f.write(new)
                        console.print(f"✓ @{name} actualizado.")
                        state.scan_agencies()
                        state.refresh_static_context()
                except (OSError, IOError) as e:
                    console.print(f"Error editando: {e}")

        elif action == "ver":
            if not items:
                console.print(f"No hay {plural.lower()} para ver.")
                continue
            name = interactive_picker("VER", items)
            if name:
                ext = items_map[name]
                try:
                    filepath = os.path.join(base_dir, f"{name}{ext}")
                    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    if ext == ".py":
                        print_code(content, filename=f"{name}.py", language="python")
                    elif entity_type == "skills" and "```" in content:
                        print_code(content, filename=f"{name}.md", language="markdown")
                    else:
                        print_panel(content, title=f"@{name}", border_style="dim white", is_markdown=True)
                except (OSError, IOError) as e:
                    console.print(f"Error leyendo: {e}")

        elif action == "eliminar":
            if not items:
                console.print(f"No hay {plural.lower()} para eliminar.")
                continue
            name = interactive_picker("BORRAR", items)
            if name and Confirm.ask(f"¿Borrar @{name}?"):
                ext = items_map[name]
                try:
                    os.remove(os.path.join(base_dir, f"{name}{ext}"))
                    console.print(f"✓ @{name} eliminado.")
                    if entity_type == "agents" and state.active_agent == name:
                        state.load_agent("default")
                    if entity_type == "skills":
                        state.active_skills.discard(os.path.join(base_dir, f"{name}{ext}"))
                    state.scan_agencies()
                    state.refresh_static_context()
                except (OSError, IOError) as e:
                    console.print(f"Error eliminando: {e}")
