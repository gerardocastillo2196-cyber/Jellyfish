import subprocess
from rich.panel import Panel
from rich.console import Console

console = Console()

def run_terminal_command(command_str, state, silent_history=False):
    """Ejecuta comando y lo inyecta en el historial del estado"""
    try:
        process = subprocess.Popen(command_str, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout, stderr = process.communicate()
        res = stdout if stdout else stderr
        if not res.strip(): res = f"Comando '{command_str}' ejecutado con éxito."
        
        console.print(Panel(res, title=f"Terminal", border_style="yellow"))
        
        if not silent_history:
            state.history.append({"role": "system", "content": f"[SALIDA TERMINAL]\n{res}"})
        return res
    except Exception as e:
        console.print(f"[dim red]Error al ejecutar comando: {e}[/dim red]")
        return str(e)
