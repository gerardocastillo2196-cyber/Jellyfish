import os
import sys
import termios
import tty
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.prompt import Confirm
from rich.table import Table
from prompt_toolkit import PromptSession
from core.state import AGENCY_DIR
from core.terminal import run_terminal_command

console = Console()

def interactive_picker(title, options, add_back=True):
    if add_back: options = list(options) + [".. Volver"]
    console.print(f"\n[bold cyan]{title}:[/bold cyan]")
    current_index = 0
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        while True:
            output = ""
            for i, opt in enumerate(options):
                prefix = " > " if i == current_index else "   "
                color = "\x1b[32m" if i == current_index else "\x1b[37m"
                output += f"\r\x1b[K{prefix}{color}{opt}\x1b[0m\r\n"
            sys.stdout.write(output)
            sys.stdout.flush()
            char = sys.stdin.read(1)
            if char == '\x1b':
                char2 = sys.stdin.read(2)
                if char2 == '[A': current_index = (current_index - 1) % len(options)
                elif char2 == '[B': current_index = (current_index + 1) % len(options)
            elif char in ['\r', '\n']: break
            elif char == '\x03': raise KeyboardInterrupt
            sys.stdout.write(f"\x1b[{len(options)}A")
            sys.stdout.flush()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    
    selected = options[current_index]
    return None if selected == ".. Volver" else selected

def file_browser(start_path="."):
    curr = os.path.abspath(start_path)
    ignore = ["venv", ".git", "__pycache__", "jellyfish.py", "core"]
    while True:
        try:
            items = [f for f in os.listdir(curr) if f not in ignore and not f.startswith(".")]
            items.sort()
            options = ["(Seleccionar esta carpeta)", ".. (Subir)"] + items
            sel = interactive_picker(f"EXPLORADOR: {curr}", options)
            if not sel: return None
            if sel == "(Seleccionar esta carpeta)": return curr
            if sel == ".. (Subir)": curr = os.path.dirname(curr); continue
            path = os.path.join(curr, sel)
            if os.path.isdir(path): curr = path
            else: return path
        except: return None

def detailed_interview(type_key):
    session = PromptSession()
    if type_key == "agents":
        console.print(Panel("🎭 FORJA AVANZADA DE AGENTE", border_style="green"))
        name = session.prompt("1. Alias: ").strip()
        if not name: return None
        rol = session.prompt("2. Rol: ").strip()
        contexto = session.prompt("3. Contexto Operativo: ").strip()
        tono = session.prompt("4. Tono: ").strip()
        conocimiento = session.prompt("5. Expertise: ").strip()
        regla = session.prompt("6. Regla Suprema: ").strip()
        ejemplo = session.prompt("7. Ejemplo [Opcional]: ").strip()
        
        content = (f"# AGENTE: @{name.upper()}\n**ROL:** {rol}\n**CONTEXTO:** {contexto}\n"
                   f"**TONO:** {tono}\n**EXPERTISE:** {conocimiento}\n**REGLA:** {regla}\n")
        if ejemplo: content += f"\n**EJEMPLO:**\n{ejemplo}\n"
            
    else:
        console.print(Panel("🛠️ FORJA AVANZADA DE HABILIDAD", border_style="cyan"))
        name = session.prompt("1. Nombre: ").strip()
        if not name: return None
        obj = session.prompt("2. Propósito: ").strip()
        trigger = session.prompt("3. Activación: ").strip()
        deps = session.prompt("4. Dependencias Linux: ").strip()
        comando = session.prompt("5. Comando(s) Bash: ").strip()
        errores = session.prompt("6. Manejo de Errores: ").strip()
        
        content = (f"# HABILIDAD: @{name.upper()}\n**OBJETIVO:** {obj}\n**TRIGGER:** {trigger}\n"
                   f"**DEPENDENCIAS:** {deps}\n**INSTRUCCIÓN:** Genera este bloque:\n\n"
                   f"```bash\n{comando}\n```\n\n**ERRORES:** {errores}\n")
    
    path = f"{AGENCY_DIR}/{type_key}/{name.lower()}.md"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f: f.write(content)
    console.print(f"[green]✓ @{name.lower()} forjado profesionalmente.[/green]")
    return name.lower()

def handle_crud(entity_type, state):
    plural = "AGENTES" if entity_type == "agents" else "HABILIDADES"
    base_dir = f"{AGENCY_DIR}/{entity_type}"
    while True:
        action = interactive_picker(f"GESTIÓN DE {plural}", ["cargar", "añadir", "editar", "ver", "eliminar"])
        if not action: break
        items = [f[:-3] for f in os.listdir(base_dir) if f.endswith(".md")]
        
        if action == "cargar":
            name = interactive_picker(f"SELECCIONAR", items)
            if name:
                if entity_type == "agents": state.load_agent(name)
                else: 
                    state.active_skills.add(f"{base_dir}/{name}.md")
                    state.refresh_static_context()
                break
        elif action == "añadir":
            detailed_interview(entity_type)
        elif action == "editar":
            name = interactive_picker("EDITAR", items)
            if name:
                path = f"{base_dir}/{name}.md"
                with open(path, "r") as f: old = f.read()
                new = PromptSession().prompt(f"Editando @{name}: ", default=old)
                if new.strip():
                    with open(path, "w") as f: f.write(new)
        elif action == "ver":
            name = interactive_picker("VER", items)
            if name:
                with open(f"{base_dir}/{name}.md", "r") as f:
                    console.print(Panel(Markdown(f.read()), title=f"@{name}", border_style="cyan"))
        elif action == "eliminar":
            name = interactive_picker("BORRAR", items)
            if name and Confirm.ask(f"¿Borrar {name}?"):
                os.remove(f"{base_dir}/{name}.md")
                if entity_type == "agents" and state.active_agent == name: state.load_agent("default")
                if entity_type == "skills": state.active_skills.discard(f"{base_dir}/{name}.md")

def handle_slash_command(cmd_input, state, display_header_func):
    parts = cmd_input.split(" ", 1)
    command, arg = parts[0].lower(), parts[1] if len(parts) > 1 else ""

    if command == "/exit": sys.exit(0)
    elif command == "/clear": state.reset_history(); display_header_func()
    elif command == "/help":
        table = Table(title="GUÍA JELLYFISH", box=None)
        table.add_column("Comando", style="cyan"); table.add_column("Función")
        table.add_row("/add", "Vincular archivos al contexto"); table.add_row("/context", "Gestionar contexto")
        table.add_row("/agent", "Taller de agentes"); table.add_row("/skill", "Taller de habilidades")
        table.add_row("/run", "Terminal real"); table.add_row("/clear", "Limpiar chat")
        console.print(Panel(table, border_style="red"))
    elif command == "/add":
        path = file_browser(arg if arg else ".")
        if path:
            if os.path.isdir(path):
                for root, _, files in os.walk(path):
                    if any(x in root for x in ["venv", ".git", "__pycache__", "core"]): continue
                    for f in files:
                        if not f.startswith(".") and not f.endswith(".pyc"): state.context_files.add(os.path.join(root, f))
            else: state.context_files.add(path)
            state.refresh_static_context(); console.print(f"[green]✓ Contexto actualizado.[/green]")
    elif command == "/context":
        while True:
            files = list(state.context_files)
            if not files: 
                console.print("[yellow]Aviso: El contexto está vacío.[/yellow]")
                break
            sel = interactive_picker("ADMINISTRAR CONTEXTO", ["Limpiar todo"] + files)
            if not sel: break
            if sel == "Limpiar todo": state.context_files.clear(); state.refresh_static_context(); break
            state.context_files.remove(sel); state.refresh_static_context()
    elif command == "/run":
        if not arg: arg = PromptSession().prompt("Comando: ").strip()
        if arg: run_terminal_command(arg, state)
    elif command == "/agent": handle_crud("agents", state)
    elif command == "/skill": handle_crud("skills", state)
