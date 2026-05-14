import os
import sys
from rich.console import Console
from rich.panel import Panel
from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.styles import Style

# Importaciones del Framework Modular
from core.state import JellyfishState, AGENCY_DIR, MODEL
from core.llm_engine import stream_ollama
from core.crud import handle_slash_command
from core.plugin_manager import PluginManager

console = Console()
state = JellyfishState()
plugins = PluginManager()

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
            "/plugin": "Ejecutar plugin de Python",
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
            agents_dir = f"{AGENCY_DIR}/agents"
            if os.path.exists(agents_dir):
                for f in os.listdir(agents_dir):
                    if f.endswith(".md") and f[:-3].lower().startswith(query):
                        yield Completion(f"@{f[:-3]}", start_position=-len(text), display_meta="Agente")

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
    
    skills_list = ", ".join([os.path.basename(s)[:-3] for s in state.active_skills]) if state.active_skills else "Ninguna"
    console.print(Panel(
        f"Agente: [bold green]@{state.active_agent}[/bold green] | Habilidades: [bold cyan]{skills_list}[/bold cyan]\n"
        f"Modelo: [bold magenta]{MODEL}[/bold magenta] | Contexto: [bold yellow]{len(state.context_files)} archivos[/bold yellow]",
        border_style="red", title=f"Jellyfish Framework v3.0.0"
    ))

def main():
    display_header()
    session = PromptSession(completer=ClaudeCompleter(), style=claude_style)
    while True:
        try:
            prompt_html = f"<b><ansigreen>@{state.active_agent}</ansigreen> <ansiblue>> </ansiblue></b>"
            user_input = session.prompt(HTML(prompt_html)).strip()
            if not user_input: continue
            
            # 1. Comandos de Agente (@nombre)
            if user_input.startswith("@"):
                if user_input.lower() == "@exit": 
                    state.active_skills.clear(); state.load_agent("default"); continue
                name = user_input[1:].lower()
                if os.path.exists(f"{AGENCY_DIR}/agents/{name}.md"): state.load_agent(name); continue
            
            # 2. Comandos de Plugin (/plugin [name] [args])
            if user_input.startswith("/plugin"):
                parts = user_input.split(" ")
                if len(parts) == 1:
                    available = ", ".join(plugins.plugins.keys()) if plugins.plugins else "Ninguno"
                    console.print(Panel(f"Plugins disponibles: {available}\nUso: /plugin <nombre> [argumentos]", title="Ayuda de Plugins", border_style="blue"))
                else:
                    plugin_name = parts[1]
                    plugin_args = " ".join(parts[2:]) if len(parts) > 2 else ""
                    res = plugins.run_plugin(plugin_name, plugin_args)
                    console.print(Panel(str(res), title=f"Plugin: {plugin_name}", border_style="blue"))
                    state.history.append({"role": "system", "content": f"[PLUGIN: {plugin_name}]\n{res}"})
                continue

            # 3. Comandos de Framework (/)
            if user_input.startswith("/"): 
                handle_slash_command(user_input, state, display_header)
                continue
            
            # 4. Inferencia Normal
            state.history.append({"role": "user", "content": user_input})
            res = stream_ollama(state)
            if res: state.history.append({"role": "assistant", "content": res})
            
        except KeyboardInterrupt: pass
        except Exception as e: console.print(f"[dim red]Aviso: Fallo en el bucle principal: {e}[/dim red]")

if __name__ == "__main__": main()