import os
import sys
import json
import requests
import subprocess
import re
import termios
import tty
import importlib.util
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.prompt import Confirm
from rich.table import Table
from rich.columns import Columns
from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.styles import Style
from core.rag_coder import CodeKnowledgeBase

# --- CONFIGURACIÓN PRINCIPAL ---
MODEL = os.getenv("JELLYFISH_MODEL", "qwen2.5-agent:latest")
OLLAMA_URL = "http://localhost:11434/api/chat"
AGENCY_DIR = os.path.expanduser("~/MisModelosIA/agencia")
PLUGINS_DIR = os.path.join(AGENCY_DIR, "plugins")
DB_PATH = os.path.join(AGENCY_DIR, "code_vector_db")
console = Console()

# --- BOOTSTRAP ---
for folder in ["agents", "skills", "memory", "plugins"]:
    os.makedirs(os.path.join(AGENCY_DIR, folder), exist_ok=True)

claude_style = Style.from_dict({
    'completion-menu': 'bg:#1e1e1e #ffffff',
    'completion-menu.completion': 'bg:#1e1e1e #888888',
    'completion-menu.completion.current': 'bg:#333333 #ffffff',
})

# --- MOTOR RAG ---
rag = CodeKnowledgeBase(DB_PATH)

# --- ARQUITECTURA DE PLUGINS (Mejora 3) ---
class PluginManager:
    def __init__(self):
        self.plugins = {}
        self.load_all_plugins()

    def load_all_plugins(self):
        if not os.path.exists(PLUGINS_DIR): return
        for filename in os.listdir(PLUGINS_DIR):
            if filename.endswith(".py") and not filename.startswith("__"):
                plugin_name = filename[:-3]
                filepath = os.path.join(PLUGINS_DIR, filename)
                spec = importlib.util.spec_from_file_location(plugin_name, filepath)
                module = importlib.util.module_from_spec(spec)
                try:
                    spec.loader.exec_module(module)
                    if hasattr(module, "execute"):
                        self.plugins[plugin_name] = module
                except Exception as e:
                    console.print(f"[dim red]Error en plugin {plugin_name}: {e}[/dim red]")

    def run_plugin(self, plugin_name, args):
        if plugin_name in self.plugins:
            try:
                return self.plugins[plugin_name].execute(args)
            except Exception as e:
                return f"Error: {e}"
        return f"Plugin '{plugin_name}' no encontrado."

# --- AUTOCOMPLETADO (Regla de Oro: Intacto) ---
class ClaudeCompleter(Completer):
    def __init__(self):
        self.commands = {
            "/add": "Vincular archivos al contexto",
            "/context": "Gestionar archivos vinculados",
            "/agent": "Gestión de agentes (Personalidades)",
            "/skill": "Gestión de habilidades (Funciones)",
            "/run": "Ejecutar comando en la terminal",
            "/plugin": "Ejecutar script local", # Mejora 3
            "/clear": "Limpiar chat",
            "/help": "Ver guía extendida",
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
            agents_dir = os.path.join(AGENCY_DIR, "agents")
            if os.path.exists(agents_dir):
                for f in os.listdir(agents_dir):
                    if f.endswith(".md") and f[:-3].lower().startswith(query):
                        yield Completion(f"@{f[:-3]}", start_position=-len(text), display_meta="Agente")

# --- ESTADO DEL SISTEMA ---
class JellyfishState:
    def __init__(self):
        self.active_agent = "default"
        self.active_skills = set()
        self.context_files = set()
        self.history = [] 
        self.static_history = [] 
        self.system_prompt = ""
        self.load_agent("default")

    def load_agent(self, agent_name):
        self.active_agent = agent_name.lower()
        template_file = os.path.join(AGENCY_DIR, "agents", "template.md")
        agent_file = os.path.join(AGENCY_DIR, "agents", f"{self.active_agent}.md")
        
        self.system_prompt = ""
        if os.path.exists(template_file):
            try:
                with open(template_file, "r", encoding='utf-8', errors='ignore') as f: 
                    self.system_prompt = f"[PROTOCOLO]\n{f.read()}\n\n"
            except: pass

        if self.active_agent == "default":
            self.system_prompt += "Eres Jellyfish, un asistente técnico. Tienes acceso a la terminal."
        else:
            if os.path.exists(agent_file):
                try:
                    with open(agent_file, "r", encoding='utf-8', errors='ignore') as f: 
                        self.system_prompt += f"[IDENTIDAD]\n{f.read()}"
                except: pass
        
        self.history = [] 
        self.refresh_static_context()

    def refresh_static_context(self):
        self.static_history = [{"role": "system", "content": self.system_prompt}]
        skill_template = os.path.join(AGENCY_DIR, "skills", "template.md")
        if os.path.exists(skill_template):
            try:
                with open(skill_template, "r", encoding='utf-8', errors='ignore') as f: 
                    self.static_history.append({"role": "system", "content": f"[SKILL_PROTO]\n{f.read()}"})
            except: pass

        for skill_path in self.active_skills:
            if "template.md" in skill_path: continue
            try:
                with open(skill_path, "r", encoding='utf-8', errors='ignore') as f: 
                    self.static_history.append({"role": "system", "content": f"[SKILL]\n{f.read()}"})
            except: pass
        
        for f in self.context_files:
            if os.path.isfile(f):
                try:
                    with open(f, "r", encoding='utf-8', errors='ignore') as file: 
                        self.static_history.append({"role": "system", "content": f"[DOC]\n{file.read()}"})
                except: pass

    def get_full_history(self):
        return self.static_history + self.history[-20:]

# --- UI (Regla de Oro: Diseño ASCII y Picker Intactos) ---
def display_header():
    os.system('clear')
    logo = r"""
        ▄██████▄            ▄██████▄            ▄██████▄
       ██████████          ██████████          ██████████
       ███▀▀██▀▀█          ███▀▀██▀▀█          ███▀▀██▀▀█
        █  █  █             █  █  █             █  █  █ 
        ▀  ▀  ▀             ▀  ▀  ▀             ▀  ▀  ▀ 
    """
    console.print(logo, style="bold red", justify="center")
    console.print("╦╔═╗╦  ╦  ╦ ╦╔═╗╦╔═╗╦ ╦\n║║╣ ║  ║  ╚╦╝╠╣ ║╚═╗╠═╣\n╚╝╚═╝╩═╝╩═╝ ╩ ╚  ╩╚═╝╩ ╩", style="bold red", justify="center")
    
    status_cols = Columns([
        Panel(f"👤 [bold green]@{state.active_agent.upper()}[/bold green]", border_style="blue", expand=True),
        Panel(f"🤖 [bold magenta]{MODEL}[/bold magenta]", border_style="blue", expand=True),
        Panel(f"⚡ [bold cyan]{len(state.active_skills)} Skills[/bold cyan]", border_style="blue", expand=True),
        Panel(f"📂 [bold yellow]{len(state.context_files)} Docs[/bold yellow]", border_style="blue", expand=True)
    ])
    console.print(Panel(status_cols, title="JELLYFISH OS v3.4.0", border_style="red"))

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
    ignore_folders = ["venv", ".git", "__pycache__"]
    while True:
        try:
            items = [f for f in os.listdir(curr) if not f.startswith(".") and f not in ignore_folders]
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

# --- FORJA AVANZADA (Mejora 2) ---
def detailed_interview(type_key):
    session = PromptSession()
    if type_key == "agents":
        console.print(Panel("🎭 FORJA AVANZADA DE AGENTE", border_style="green"))
        name = session.prompt("1. Alias (ej. arquitecto_software): ").strip()
        if not name: return None
        rol = session.prompt("2. Rol Principal: ").strip()
        contexto = session.prompt("3. Contexto Operativo: ").strip()
        tono = session.prompt("4. Tono: ").strip()
        conocimiento = session.prompt("5. Expertise: ").strip()
        regla = session.prompt("6. Regla Inquebrantable: ").strip()
        ejemplo = session.prompt("7. Ejemplo de Interacción: ").strip()
        
        content = (f"# AGENTE: @{name.upper()}\n**ROL:** {rol}\n**CONTEXTO:** {contexto}\n"
                   f"**TONO:** {tono}\n**EXPERTISE:** {conocimiento}\n**REGLA:** {regla}\n"
                   f"\n**EJEMPLO:**\n{ejemplo}\n")
    else:
        console.print(Panel("🛠️ FORJA AVANZADA DE HABILIDAD", border_style="cyan"))
        name = session.prompt("1. Nombre: ").strip()
        if not name: return None
        obj = session.prompt("2. Propósito: ").strip()
        trigger = session.prompt("3. Activación (Trigger): ").strip()
        deps = session.prompt("4. Dependencias Linux: ").strip()
        comando = session.prompt("5. Comando Bash Exacto: ").strip()
        errores = session.prompt("6. Manejo de Errores: ").strip()
        
        content = (f"# HABILIDAD: @{name.upper()}\n**OBJETIVO:** {obj}\n**TRIGGER:** {trigger}\n"
                   f"**DEPENDENCIAS:** {deps}\n**INSTRUCCIÓN:**\n\n```bash\n{comando}\n```\n\n"
                   f"**ERRORES:** {errores}\n")
    
    path = os.path.join(AGENCY_DIR, type_key, f"{name.lower()}.md")
    with open(path, "w", encoding='utf-8') as f: f.write(content)
    console.print(f"[green]✓ @{name.lower()} forjado profesionalmente.[/green]")
    return name.lower()

# --- CRUD Y COMANDOS ---
def handle_crud(entity_type):
    base_dir = os.path.join(AGENCY_DIR, entity_type)
    while True:
        action = interactive_picker(f"GESTIÓN DE {entity_type.upper()}", ["cargar", "añadir", "editar", "ver", "eliminar"])
        if not action: break
        items = [f[:-3] for f in os.listdir(base_dir) if f.endswith(".md")]
        
        if action == "cargar":
            name = interactive_picker("SELECCIONAR", items)
            if name:
                if entity_type == "agents": state.load_agent(name)
                else: 
                    state.active_skills.add(os.path.join(base_dir, f"{name}.md"))
                    state.refresh_static_context()
                break
        elif action == "añadir": detailed_interview(entity_type)
        elif action == "editar":
            name = interactive_picker("EDITAR", items)
            if name:
                path = os.path.join(base_dir, f"{name}.md")
                try:
                    with open(path, "r", encoding='utf-8', errors='ignore') as f: old = f.read()
                    new = PromptSession().prompt(f"Editando @{name}: ", default=old)
                    if new.strip():
                        with open(path, "w", encoding='utf-8') as f: f.write(new)
                except: pass
        elif action == "ver":
            name = interactive_picker("VER", items)
            if name:
                try:
                    with open(os.path.join(base_dir, f"{name}.md"), "r", encoding='utf-8', errors='ignore') as f:
                        console.print(Panel(Markdown(f.read()), title=f"@{name}", border_style="cyan"))
                except: pass
        elif action == "eliminar":
            name = interactive_picker("BORRAR", items)
            if name and Confirm.ask(f"¿Borrar {name}?"):
                os.remove(os.path.join(base_dir, f"{name}.md"))
                if entity_type == "agents" and state.active_agent == name: state.load_agent("default")
                if entity_type == "skills": state.active_skills.discard(os.path.join(base_dir, f"{name}.md"))
    display_header() 

def handle_slash_command(cmd_input):
    parts = cmd_input.split(" ")
    command = parts[0].lower()
    arg = " ".join(parts[1:])

    if command == "/exit": sys.exit(0)
    elif command == "/clear": state.history = []; display_header()
    elif command == "/help":
        table = Table(title="GUÍA JELLYFISH", box=None)
        table.add_column("Comando", style="cyan"); table.add_column("Función")
        for c, d in ClaudeCompleter().commands.items(): table.add_row(c, d)
        table.add_row("/context-f.del", "Forzar limpieza total de contexto [AVANZADO]")
        console.print(Panel(table, border_style="red"))
    elif command == "/add":
        path = file_browser(arg if arg else ".")
        if path:
            if os.path.isdir(path):
                binary_ext = ('.pyc', '.png', '.jpg', '.jpeg', '.gif', '.exe', '.bin', '.so', '.dll', '.o')
                for root, _, files in os.walk(path):
                    if any(x in root for x in ["venv", ".git", "__pycache__"]): continue
                    for f in files:
                        if f.lower().endswith(binary_ext): continue
                        state.context_files.add(os.path.join(root, f))
                # Lanzar indexación RAG
                rag.index_codebase(path)
            else: 
                state.context_files.add(path)
            state.refresh_static_context()
            console.print("[green]✓ Contexto e Índice RAG actualizados.[/green]")
            input("\nPresiona Enter para continuar...")
            display_header()
    elif command == "/context":
        files = list(state.context_files)
        if not files:
            console.print("[yellow]Aviso: El contexto está vacío. Usa /add para vincular archivos.[/yellow]")
            input("\nPresiona Enter para continuar...") # Pausa de confirmación
        else:
            while True:
                files = list(state.context_files)
                if not files: break
                sel = interactive_picker("CONTEXTO", ["Limpiar todo"] + files)
                if not sel: break
                if sel == "Limpiar todo": state.context_files.clear(); state.refresh_static_context(); break
                state.context_files.remove(sel); state.refresh_static_context()
        display_header() 
    elif command == "/context-f.del":
        if not state.context_files:
            console.print("[yellow]Aviso: No hay nada que purgar, el contexto ya está vacío.[/yellow]")
            input("\nPresiona Enter para continuar...") # Pausa de confirmación
        else:
            state.context_files.clear()
            state.refresh_static_context()
            console.print("[bold red]☢ Contexto purgado por completo.[/bold red]")
            input("\nPresiona Enter para continuar...") # Pausa de confirmación
        display_header()
    elif command == "/run":
        if not arg: arg = PromptSession().prompt("Comando: ").strip()
        if arg:
            res = subprocess.getoutput(arg)
            console.print(Panel(res, title="Terminal", border_style="yellow"))
            state.history.append({"role": "system", "content": f"[SALIDA]\n{res}"})
    elif command == "/plugin": 
        if not arg: 
            available = ", ".join(plugins.plugins.keys()) if plugins.plugins else "Ninguno"
            console.print(f"Plugins: {available}"); return
        p_name = arg.split(" ")[0]
        p_args = " ".join(arg.split(" ")[1:])
        res = plugins.run_plugin(p_name, p_args)
        console.print(Panel(str(res), title=f"Plugin: {p_name}", border_style="blue"))
        state.history.append({"role": "system", "content": f"[PLUGIN {p_name}]\n{res}"})
    elif command == "/agent": handle_crud("agents")
    elif command == "/skill": handle_crud("skills")

# --- LLM ENGINE ---
def stream_ollama():
    try:
        response = requests.post(OLLAMA_URL, json={"model": MODEL, "messages": state.get_full_history(), "stream": True}, stream=True)
        full = ""
        from rich.live import Live
        with Live(Panel("", title=f"@{state.active_agent}"), refresh_per_second=15) as live:
            for line in response.iter_lines():
                if line:
                    data = json.loads(line.decode("utf-8"))
                    if "message" in data:
                        chunk = data["message"]["content"]
                        full += chunk
                        live.update(Panel(Markdown(full), title=f"@{state.active_agent}", border_style="bright_black"))
        # Action Loop
        ticks = chr(96)*3
        matches = re.findall(rf"{ticks}(?:bash|sh)\n(.*?)\n{ticks}", full, re.DOTALL)
        for cmd in matches:
            if Confirm.ask(f"\n[bold yellow]¿Ejecutar?[/bold yellow] {cmd}"):
                res = subprocess.getoutput(cmd)
                console.print(Panel(res, title="Terminal", border_style="yellow"))
                state.history.append({"role": "system", "content": f"[SALIDA]\n{res}"})
        return full
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]"); return None

# --- MAIN ---
state = JellyfishState()
plugins = PluginManager()

def main():
    display_header()
    session = PromptSession(completer=ClaudeCompleter(), style=claude_style)
    while True:
        try:
            prompt_html = f"<b><ansigreen>@{state.active_agent}</ansigreen> <ansiblue>> </ansiblue></b>"
            user_input = session.prompt(HTML(prompt_html)).strip()
            if not user_input: continue
            if user_input.startswith("@"):
                if user_input.lower() == "@exit": state.load_agent("default"); continue
                name = user_input[1:].lower()
                if os.path.exists(os.path.join(AGENCY_DIR, "agents", f"{name}.md")): state.load_agent(name); continue
            if user_input.startswith("/"): handle_slash_command(user_input); continue
            
            # --- HEURÍSTICA RAG (Mejora 3.4.0) ---
            keywords = ["código", "arquitectura", "función", "clase", "archivo", "implementación", "code", "architecture", "function", "class", "file"]
            if any(k in user_input.lower() for k in keywords):
                context_rag = rag.query_code(user_input)
                if context_rag:
                    state.history.append({"role": "system", "content": context_rag})

            state.history.append({"role": "user", "content": user_input})
            res = stream_ollama()
            if res: state.history.append({"role": "assistant", "content": res})
        except KeyboardInterrupt: pass
        except Exception as e: console.print(f"[red]Error: {e}[/red]")

if __name__ == "__main__": main()