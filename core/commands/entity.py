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
    en el sistema de archivos o inyección en Markdown.
    """
    clean = _UNSAFE_FILENAME_RE.sub('', name).strip()
    clean = clean.replace(' ', '_')
    return clean.lower() if clean else ""

def detailed_interview(type_key: str) -> str | None:
    """Entrevista guiada para crear un agente o habilidad."""
    session = PromptSession()

    if type_key == "agents":
        console.print("🎭 FORJA AVANZADA DE AGENTE")
        raw_name = session.prompt("1. Alias (ej. arquitecto_software): ").strip()
        name = _sanitize_name(raw_name)
        if not name:
            console.print("⚠ Nombre inválido o vacío.")
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
        console.print("🛠️ FORJA AVANZADA DE HABILIDAD")
        raw_name = session.prompt("1. Nombre: ").strip()
        name = _sanitize_name(raw_name)
        if not name:
            console.print("⚠ Nombre inválido o vacío.")
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
        console.print(f"✓ @{name} forjado profesionalmente.")
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

        items = []
        for root_dir, _, files in os.walk(base_dir):
            for file in sorted(files):
                if file.endswith(".md"):
                    rel_path = os.path.relpath(os.path.join(root_dir, file), base_dir)
                    items.append(rel_path[:-3])

        if action == "cargar":
            if not items:
                console.print(f"No hay {plural.lower()} disponibles.")
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
                console.print(f"No hay {plural.lower()} para editar.")
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
                        console.print(f"✓ @{name} actualizado.")
                except (OSError, IOError) as e:
                    console.print(f"Error editando: {e}")

        elif action == "ver":
            if not items:
                console.print(f"No hay {plural.lower()} para ver.")
                continue
            name = interactive_picker("VER", items)
            if name:
                try:
                    filepath = os.path.join(base_dir, f"{name}.md")
                    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    if entity_type == "skills" and "```" in content:
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
                try:
                    os.remove(os.path.join(base_dir, f"{name}.md"))
                    console.print(f"✓ @{name} eliminado.")
                    if entity_type == "agents" and state.active_agent == name:
                        state.load_agent("default")
                    if entity_type == "skills":
                        state.active_skills.discard(os.path.join(base_dir, f"{name}.md"))
                        state.refresh_static_context()
                except (OSError, IOError) as e:
                    console.print(f"Error eliminando: {e}")
