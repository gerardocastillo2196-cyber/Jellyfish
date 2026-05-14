import os
import sys
import json
import requests
import subprocess
import re
import termios
import tty
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.text import Text

from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.styles import Style

# --- CONFIGURACIÓN PRINCIPAL ---
OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "qwen2.5-agent:latest" 
AGENCY_DIR = os.path.expanduser("~/MisModelosIA/agencia")
console = Console()

claude_style = Style.from_dict({
    'completion-menu': 'bg:#1e1e1e #ffffff',
    'completion-menu.completion': 'bg:#1e1e1e #888888',
    'completion-menu.completion.current': 'bg:#333333 #ffffff',
})

class ClaudeCompleter(Completer):
    def __init__(self):
        self.commands = {
            "/add": "Vincular archivos al contexto",
            "/context": "Gestionar archivos vinculados",
            "/agent": "Gestión de agentes (Personalidades)",
            "/skill": "Gestión de habilidades (Funciones)",
            "/run": "Ejecutar comando en la terminal",
            "/clear": "Limpiar chat",
            "/help": "Ver lista de comandos extendida",
            "/exit": "Cerrar sistema"
        }
    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        if text.startswith('/') and ' ' not in text:
            for cmd, desc in self.commands.items():
                if cmd.startswith(text): yield Completion(cmd, start_position=-len(text), display_meta=desc)
        elif text.startswith('@'):
            query = text[1:].lower()
            if "exit".startswith(query): yield Completion("@exit", start_position=-len(text), display_meta="Volver a default")
            agents_dir = f"{AGENCY_DIR}/agents"
            if os.path.exists(agents_dir):
                for f in os.listdir(agents_dir):
                    if f.endswith(".md") and f[:-3].lower().startswith(query):
                        yield Completion(f"@{f[:-3]}", start_position=-len(text), display_meta="Agente")

class JellyfishState:
    def __init__(self):
        self.active_agent = "default"
        self.active_skills = set()
        self.context_files = set()
        self.history = []
        self.system_prompt = ""
        self.load_agent("default", show_card=False)

    def load_agent(self, agent_name, show_card=False):
        self.active_agent = agent_name.lower()
        agent_file = f"{AGENCY_DIR}/agents/{self.active_agent}.md"
        
        if self.active_agent == "default":
            self.system_prompt = (
                "Eres Jellyfish, un asistente de terminal local avanzado.\n"
                "Tienes acceso a la terminal y puedes ver los resultados de los comandos ejecutados por el usuario.\n"
                "Responde de forma técnica, útil y consciente del entorno local."
            )
        else:
            self.system_prompt = (
                "INSTRUCCIÓN SUPREMA: Eres un actor de método. Olvida que eres una IA.\n"
                "Responde ÚNICAMENTE como el personaje definido a continuación.\n"
                "No admitas tener limitaciones técnicas ni ser un programa.\n"
                "Acata estrictamente el estilo de habla y las reglas de oro descritas.\n\n"
            )
        
        agent_content = ""
        if os.path.exists(agent_file):
            with open(agent_file, "r") as f:
                agent_content = f.read()
                if self.active_agent != "default":
                    self.system_prompt += f"[PERFIL DE IDENTIDAD]\n{agent_content}"
        
        if show_card:
            console.print(Panel(Markdown(agent_content if agent_content else "Perfil base."), title=f"@{self.active_agent}", border_style="green"))
        self.reset_history()

    def reset_history(self):
        self.history = [{"role": "system", "content": self.system_prompt}]
        for skill_path in self.active_skills:
            try:
                with open(skill_path, "r") as f:
                    self.history.append({"role": "system", "content": f"[HABILIDAD CARGADA]\n{f.read()}"})
            except: pass
        for f in self.context_files:
            try:
                if os.path.isfile(f):
                    with open(f, "r") as file: self.history.append({"role": "system", "content": f"[CONTEXTO: {f}]\n{file.read()}"})
            except: pass

state = JellyfishState()

def display_header():
    os.system('clear')
    logo = """
          ▄██████▄          
        ▄██████████▄        
       ▄████████████▄       
       ███▀▀██▀▀██▀▀█       
       ▀██  ██  ██  ▀       
        ▀█  ██  █▀          
         ▀  ▀▀  ▀           
    """
    console.print(logo, style="bold red", justify="center")
    console.print("╦╔═╗╦  ╦  ╦ ╦╔═╗╦╔═╗╦ ╦\n║║╣ ║  ║  ╚╦╝╠╣ ║╚═╗╠═╣\n╚╝╚═╝╩═╝╩═╝ ╩ ╚  ╩╚═╝╩ ╩", style="bold red", justify="center")
    console.print("Local Engine · Ollama Powered", style="bold blue", justify="center")
    
    skills_list = ", ".join([os.path.basename(s)[:-3] for s in state.active_skills]) if state.active_skills else "Ninguna"
    console.print(Panel(
        f"Agente: [bold green]@{state.active_agent}[/bold green] | Habilidades: [bold cyan]{skills_list}[/bold cyan]\n"
        f"Contexto: [bold yellow]{len(state.context_files)} archivos vinculados[/bold yellow]",
        border_style="red", title="Jellyfish CLI v2.4.5"
    ))

def interactive_picker(title, options, add_back=True):
    if add_back: options = list(options) + [".. Volver"]
    console.print(f"\n[bold cyan]{title}:[/bold cyan]")
    current_index = 0
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        while True:
            output = ""
            for i, opt in enumerate(options):
                prefix = " > " if i == current_index else "   "
                color_code = "\x1b[32m" if i == current_index else "\x1b[37m"
                output += f"\r\x1b[K{prefix}{color_code}{opt}\x1b[0m\r\n"
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
    finally: termios.tcsetattr(fd, termios.TCSADRAIN, old)
    selected = options[current_index]
    return None if selected == ".. Volver" else selected

def file_browser(start_path="."):
    curr = os.path.abspath(start_path)
    ignore = ["venv", ".git", "__pycache__", "jellyfish.py"]
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
        console.print(Panel("🎭 FORJA DE AGENTE", border_style="green"))
        name = session.prompt("1. Alias: ").strip()
        if not name: return None
        rol = session.prompt("2. Rol: ").strip()
        bio = session.prompt("3. Biografía: ").strip()
        tono = session.prompt("4. Tono: ").strip()
        regla = session.prompt("5. Directiva: ").strip()
        content = f"# AGENTE: @{name.upper()}\n**ROL:** {rol}\n**BIO:** {bio}\n**TONO:** {tono}\n**REGLA:** {regla}"
    else:
        console.print(Panel("🛠️ CREACIÓN DE HABILIDAD", border_style="cyan"))
        name = session.prompt("1. Nombre: ").strip()
        if not name: return None
        obj = session.prompt("2. Propósito: ").strip()
        logica = session.prompt("3. Lógica: ").strip()
        trigger = session.prompt("4. Activación: ").strip()
        content = f"# HABILIDAD: @{name.upper()}\n**OBJETIVO:** {obj}\n**LÓGICA:** {logica}\n**TRIGGER:** {trigger}"
    
    path = f"{AGENCY_DIR}/{type_key}/{name.lower()}.md"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f: f.write(content)
    console.print(f"[green]✓ {type_key[:-1].capitalize()} @{name.lower()} creado.[/green]")
    return name.lower()

def handle_crud(entity_type):
    plural_name = "AGENTES" if entity_type == "agents" else "HABILIDADES"
    base_dir = f"{AGENCY_DIR}/{entity_type}"
    os.makedirs(base_dir, exist_ok=True)
    while True:
        action = interactive_picker(f"GESTIÓN DE {plural_name}", ["cargar", "añadir", "editar", "ver", "eliminar"])
        if not action: break
        items = [f[:-3] for f in os.listdir(base_dir) if f.endswith(".md")]
        if action == "cargar":
            name = interactive_picker(f"CARGAR {plural_name[:-2]}", items)
            if name:
                if entity_type == "agents": state.load_agent(name, show_card=False)
                else: 
                    state.active_skills.add(f"{base_dir}/{name}.md"); state.reset_history()
                    console.print(f"[green]⚡ Skill @{name} activa.[/green]")
                break
        elif action == "añadir":
            detailed_interview(entity_type)
            break
        elif action == "editar":
            name = interactive_picker("EDITAR", items)
            if name:
                path = f"{base_dir}/{name}.md"
                with open(path, "r") as f: old_content = f.read()
                new_content = PromptSession().prompt(f"Editando @{name}: ", default=old_content)
                if new_content.strip():
                    with open(path, "w") as f: f.write(new_content)
                    console.print("[green]✓ Guardado.[/green]")
        elif action == "eliminar":
            name = interactive_picker("BORRAR", items)
            if name and Confirm.ask(f"¿Borrar {name}?"):
                os.remove(f"{base_dir}/{name}.md")
                if entity_type == "agents" and state.active_agent == name: state.load_agent("default")
                if entity_type == "skills": state.active_skills.discard(f"{base_dir}/{name}.md")
        elif action == "ver":
            name = interactive_picker("VISUALIZAR", items)
            if name:
                with open(f"{base_dir}/{name}.md", "r") as f:
                    console.print(Panel(Markdown(f.read()), title=f"@{name}", border_style="bright_blue"))

def run_terminal_command(command_str):
    try:
        process = subprocess.Popen(command_str, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout, stderr = process.communicate()
        res = stdout if stdout else stderr
        if not res.strip(): res = f"Comando '{command_str}' ejecutado."
        console.print(Panel(res, title=f"Terminal", border_style="yellow"))
        # INYECCIÓN EN MEMORIA DE LA IA
        state.history.append({"role": "system", "content": f"[EJECUCIÓN DE TERMINAL]\nComando: {command_str}\nResultado:\n{res}"})
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")

def handle_slash_command(cmd_input):
    parts = cmd_input.split(" ", 1)
    command = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""

    if command == "/exit": sys.exit(0)
    elif command == "/clear": state.reset_history(); display_header()
    elif command == "/help":
        table = Table(title="GUÍA JELLYFISH", border_style="red", box=None)
        table.add_column("Comando", style="bold cyan"); table.add_column("Descripción", style="dim")
        table.add_row("/add", "Vincular archivos al contexto.")
        table.add_row("/context", "Gestionar contexto.")
        table.add_row("/agent", "Taller de agentes.")
        table.add_row("/skill", "Taller de habilidades.")
        table.add_row("/run", "Terminal Linux (La IA verá el resultado).")
        console.print(Panel(table, border_style="red"))
    elif command == "/add":
        path = file_browser(arg if arg else ".")
        if path:
            if os.path.isdir(path):
                for root, _, files in os.walk(path):
                    if any(x in root for x in ["venv", ".git", "__pycache__"]): continue
                    for f in files:
                        if not f.startswith(".") and not f.endswith(".pyc"): state.context_files.add(os.path.join(root, f))
            else: state.context_files.add(path)
            state.reset_history(); console.print(f"[green]✓ Contexto actualizado.[/green]")
    elif command == "/context":
        while True:
            files = list(state.context_files)
            if not files: console.print("[dim]Contexto vacío.[/dim]"); break
            sel = interactive_picker("CONTEXTO", ["Limpiar todo"] + files)
            if not sel: break
            if sel == "Limpiar todo": state.context_files.clear(); state.reset_history(); break
            state.context_files.remove(sel); state.reset_history()
            console.print(f"[red]✗ Quitado: {sel}[/red]")
    elif command == "/run":
        if not arg: arg = PromptSession().prompt("Comando: ").strip()
        if arg: run_terminal_command(arg)
    elif command == "/agent": handle_crud("agents")
    elif command == "/skill": handle_crud("skills")

def stream_ollama():
    try:
        from rich.live import Live
        response = requests.post(OLLAMA_URL, json={"model": MODEL, "messages": state.history, "stream": True}, stream=True)
        full = ""
        with Live(Panel("", title=f"@{state.active_agent}"), refresh_per_second=15) as live:
            for line in response.iter_lines():
                if line:
                    data = json.loads(line.decode("utf-8"))
                    if "message" in data:
                        full += data["message"]["content"]
                        live.update(Panel(Markdown(full), title=f"@{state.active_agent}", border_style="bright_black"))
        return full
    except: return None

def main():
    display_header()
    session = PromptSession(completer=ClaudeCompleter(), style=claude_style)
    while True:
        try:
            prompt_html = f"<b><ansigreen>@{state.active_agent}</ansigreen> <ansiblue>> </ansiblue></b>"
            user_input = session.prompt(HTML(prompt_html)).strip()
            if not user_input: continue
            if user_input.startswith("@"):
                if user_input.lower() == "@exit": 
                    state.active_skills.clear()
                    state.load_agent("default", show_card=False); continue
                name = user_input[1:].lower()
                if os.path.exists(f"{AGENCY_DIR}/agents/{name}.md"): state.load_agent(name, show_card=False); continue
            if user_input.startswith("/"): handle_slash_command(user_input); continue
            state.history.append({"role": "user", "content": user_input})
            res = stream_ollama()
            if res: state.history.append({"role": "assistant", "content": res})
        except KeyboardInterrupt: console.print("\n[dim]Usa /exit.[/dim]")
        except Exception as e: console.print(f"[red]Error: {e}[/red]")

if __name__ == "__main__": main()