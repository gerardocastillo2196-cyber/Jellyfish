import requests
import json
import re
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.live import Live
from rich.prompt import Confirm
from core.terminal import run_terminal_command
from core.state import OLLAMA_URL, MODEL

console = Console()

def stream_ollama(state):
    try:
        response = requests.post(
            OLLAMA_URL, 
            json={"model": MODEL, "messages": state.get_full_history(), "stream": True}, 
            stream=True
        )
        full = ""
        with Live(Panel("", title=f"@{state.active_agent}"), refresh_per_second=15) as live:
            for line in response.iter_lines():
                if line:
                    data = json.loads(line.decode("utf-8"))
                    if "message" in data:
                        chunk = data["message"]["content"]
                        full += chunk
                        live.update(Panel(Markdown(full), title=f"@{state.active_agent}", border_style="bright_black"))
        
        # Action Loop: Interceptor de código
        ticks = chr(96)*3
        matches = re.findall(rf"{ticks}(?:bash|sh)\n(.*?)\n{ticks}", full, re.DOTALL)
        for cmd in matches:
            if Confirm.ask(f"\n[bold yellow]¿Ejecutar comando sugerido?[/bold yellow]\n[cyan]{cmd}[/cyan]"):
                run_terminal_command(cmd, state)
        
        return full
    except Exception as e:
        console.print(f"[dim red]Error de conexión con Ollama: {e}[/dim red]")
        return None
