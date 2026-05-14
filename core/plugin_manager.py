import os
import importlib.util
from rich.console import Console

console = Console()
PLUGINS_DIR = os.path.expanduser("~/MisModelosIA/agencia/plugins")

class PluginManager:
    def __init__(self):
        self.plugins = {}
        self.load_all_plugins()

    def load_all_plugins(self):
        """Escanea la carpeta de plugins y los carga en memoria dinámicamente."""
        if not os.path.exists(PLUGINS_DIR):
            os.makedirs(PLUGINS_DIR, exist_ok=True)
            
        for filename in os.listdir(PLUGINS_DIR):
            if filename.endswith(".py") and not filename.startswith("__"):
                plugin_name = filename[:-3]
                filepath = os.path.join(PLUGINS_DIR, filename)
                
                # Importación dinámica del módulo Python
                spec = importlib.util.spec_from_file_location(plugin_name, filepath)
                module = importlib.util.module_from_spec(spec)
                try:
                    spec.loader.exec_module(module)
                    if hasattr(module, "execute"):
                        self.plugins[plugin_name] = module
                except Exception as e:
                    console.print(f"[dim red]Error cargando plugin {plugin_name}: {e}[/dim red]")

    def run_plugin(self, plugin_name, args):
        # Recargar para detectar nuevos archivos
        if plugin_name == "reload":
            self.plugins = {}
            self.load_all_plugins()
            return "Plugins recargados con éxito."
            
        # Auto-recarga si el plugin no existe en memoria
        if plugin_name not in self.plugins:
            self.load_all_plugins()

        if plugin_name in self.plugins:
            try:
                return self.plugins[plugin_name].execute(args)
            except Exception as e:
                return f"Error ejecutando plugin '{plugin_name}': {e}"
        return f"Plugin '{plugin_name}' no encontrado después de recargar."
