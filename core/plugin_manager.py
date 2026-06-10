import os
import sys
import json
import importlib.util
import subprocess
import logging
import traceback
import tempfile
import shutil
from rich.console import Console

logger = logging.getLogger("jellyfish.plugins")
console = Console()

# Sprint 4.2 — Tiempo máximo de ejecución para cada plugin en modo sandbox
_PLUGIN_TIMEOUT_S = 30
_PLUGIN_MEMORY_LIMIT_BYTES = 512 * 1024 * 1024

# Refactored Sandbox Runner to support both PluginInterface classes and legacy execute functions
_SANDBOX_RUNNER = """
import sys, json, importlib.util, traceback, inspect

plugin_path = sys.argv[1]
args        = sys.argv[2] if len(sys.argv) > 2 else ""

try:
    spec   = importlib.util.spec_from_file_location("_plugin", plugin_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    
    # 1. Look for PluginInterface subclass
    plugin_class = None
    try:
        from plugins.plugin_core import PluginInterface
        for name in dir(module):
            obj = getattr(module, name)
            if isinstance(obj, type) and issubclass(obj, PluginInterface) and obj != PluginInterface:
                plugin_class = obj
                break
    except ImportError:
        pass
        
    if plugin_class:
        plugin_inst = plugin_class()
        try:
            from core.state_proxy import StateProxy
            plugin_inst.initialize({"proxy": StateProxy(None)})
        except Exception:
            plugin_inst.initialize({})
            
        parts = args.split(" ", 1)
        method = parts[0]
        method_args = parts[1] if len(parts) > 1 else ""
        
        if hasattr(plugin_inst, method) and method != "execute":
            result = plugin_inst.execute(method, method_args)
        else:
            sig = inspect.signature(plugin_inst.execute)
            params = [p for p in sig.parameters.values() if p.name != 'self']
            if len(params) == 1:
                result = plugin_inst.execute(args)
            else:
                result = plugin_inst.execute(method, method_args)
                
    elif hasattr(module, "execute") and callable(module.execute):
        result = module.execute(args)
    else:
        # Look for any class ending in Plugin that has execute method
        found = False
        for name in dir(module):
            obj = getattr(module, name)
            if isinstance(obj, type) and name.endswith("Plugin"):
                inst = obj()
                if hasattr(inst, "execute"):
                    sig = inspect.signature(inst.execute)
                    params = [p for p in sig.parameters.values() if p.name != 'self']
                    if len(params) == 1:
                        result = inst.execute(args)
                    else:
                        parts = args.split(" ", 1)
                        result = inst.execute(parts[0], parts[1] if len(parts) > 1 else "")
                    found = True
                    break
        if not found:
            raise AttributeError("El plugin no tiene función execute() ni clase válida con execute().")
            
    print(json.dumps({"ok": True, "result": str(result) if result is not None else ""}))
except Exception as e:
    print(json.dumps({"ok": False, "error": str(e), "tb": traceback.format_exc()[-800:]}))
"""


def _limit_plugin_resources() -> None:
    """Aplica límites defensivos en sistemas POSIX."""
    try:
        import resource

        resource.setrlimit(resource.RLIMIT_CPU, (_PLUGIN_TIMEOUT_S + 5, _PLUGIN_TIMEOUT_S + 5))
        resource.setrlimit(resource.RLIMIT_AS, (_PLUGIN_MEMORY_LIMIT_BYTES, _PLUGIN_MEMORY_LIMIT_BYTES))
        resource.setrlimit(resource.RLIMIT_FSIZE, (10 * 1024 * 1024, 10 * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    except Exception:
        # preexec_fn no debe romper el arranque del subproceso.
        pass


class PluginManager:
    """Sistema de plugins dinámicos para Jellyfish.

    Los plugins son archivos .py en la carpeta plugins/ que pueden implementar
    la interfaz PluginInterface o exportar una función execute(args: str) -> str.
    """

    def __init__(self, plugins_dir: str, state=None):
        self.plugins_dir = plugins_dir
        self._plugins_root = os.path.realpath(plugins_dir)
        self._plugin_files: dict[str, str] = {}
        self.plugins: dict = {}
        self._sandbox = os.getenv("JELLYFISH_PLUGIN_UNSAFE", "0") != "1"
        
        from core.state_proxy import StateProxy
        self.proxy = StateProxy(state) if state is not None else None
        
        os.makedirs(plugins_dir, exist_ok=True)
        self.load_all_plugins()

    def load_all_plugins(self) -> None:
        """Escanea la carpeta de plugins y registra los archivos disponibles."""
        self._plugin_files.clear()
        self.plugins.clear()

        # 1. Cargar plugins desde paquetes utilizando PluginRegistry
        try:
            from plugins.plugin_core import PluginRegistry
            registry = PluginRegistry()
            registry.load_plugins_from_package("plugins.integration")
            registry.load_plugins_from_package("plugins.automation")
            registry.load_plugins_from_package("plugins.utility")
            
            for name in registry.list_plugins():
                plugin = registry.get_plugin(name)
                if plugin:
                    try:
                        plugin.initialize({"proxy": self.proxy})
                    except Exception as ie:
                        logger.warning("Error inicializando plugin '%s': %s", name, ie)
        except Exception as e:
            logger.error("Error inicializando PluginRegistry: %s", e)

        # 2. Escanear directorio físico de plugins (para custom y retrocompatibilidad)
        if not os.path.exists(self.plugins_dir):
            return

        for root_dir, _, files in os.walk(self.plugins_dir):
            for filename in sorted(files):
                if not filename.endswith(".py") or filename.startswith("__"):
                    continue

                filepath = os.path.realpath(os.path.join(root_dir, filename))
                rel_path = os.path.relpath(filepath, self._plugins_root)
                plugin_name = rel_path[:-3]  # Quitar .py
                
                if not filepath.startswith(self._plugins_root + os.sep):
                    logger.warning("Plugin fuera de plugins_dir ignorado: %s", filepath)
                    continue
                self._plugin_files[plugin_name] = filepath

                if not self._sandbox:
                    self._load_module(plugin_name, filepath)
                else:
                    logger.info("Plugin descubierto (sandbox): %s", plugin_name)

    def _load_module(self, plugin_name: str, filepath: str) -> None:
        """Carga un módulo Python en memoria (modo legado, sin sandbox)."""
        try:
            spec = importlib.util.spec_from_file_location(plugin_name, filepath)
            if spec is None or spec.loader is None:
                return
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Comprobar si exporta una clase PluginInterface
            plugin_class = None
            try:
                from plugins.plugin_core import PluginInterface
                for name in dir(module):
                    obj = getattr(module, name)
                    if isinstance(obj, type) and issubclass(obj, PluginInterface) and obj != PluginInterface:
                        plugin_class = obj
                        break
            except ImportError:
                pass

            if plugin_class:
                inst = plugin_class()
                inst.initialize({"proxy": self.proxy})
                self.plugins[plugin_name] = inst
                logger.info("Plugin clase cargado (legado): %s", plugin_name)
            elif hasattr(module, "execute") and callable(module.execute):
                self.plugins[plugin_name] = module
                logger.info("Plugin función cargado (legado): %s", plugin_name)
            else:
                # Buscar cualquier clase con execute
                found = False
                for name in dir(module):
                    obj = getattr(module, name)
                    if isinstance(obj, type) and name.endswith("Plugin"):
                        inst = obj()
                        if hasattr(inst, "execute"):
                            self.plugins[plugin_name] = inst
                            found = True
                            logger.info("Plugin clase genérica cargado (legado): %s", plugin_name)
                            break
                if not found:
                    logger.warning("Plugin '%s' no tiene execute() ni clase válida.", plugin_name)
        except SyntaxError as e:
            console.print(f"[dim red]Error de sintaxis en plugin {plugin_name}: {e}[/dim red]")
        except ImportError as e:
            console.print(f"[dim red]Dependencia faltante en plugin {plugin_name}: {e}[/dim red]")
        except Exception as e:
            console.print(f"[dim red]Error cargando plugin {plugin_name}: {e}[/dim red]")

    def run_plugin(self, plugin_name: str, args: str) -> str:
        """Ejecuta un plugin por nombre."""
        if plugin_name == "reload":
            self.load_all_plugins()
            discovered = ", ".join(self._plugin_files.keys()) or "ninguno"
            return f"✓ Plugins recargados: {discovered}"

        # Auto-redescubrir si no está registrado
        if plugin_name not in self._plugin_files:
            try:
                from plugins.plugin_core import PluginRegistry
                if plugin_name not in PluginRegistry().list_plugins():
                    self.load_all_plugins()
            except Exception:
                self.load_all_plugins()

        # Si corre en sandbox
        if self._sandbox:
            if plugin_name in self._plugin_files:
                return self._run_sandboxed(plugin_name, args)
            else:
                # Los built-ins no están en self._plugin_files directos, los corremos inprocess de forma segura
                return self._run_inprocess(plugin_name, args)
        else:
            return self._run_inprocess(plugin_name, args)

    def _run_sandboxed(self, plugin_name: str, args: str) -> str:
        """Ejecuta el plugin en un subproceso aislado con timeout."""
        filepath = self._plugin_files[plugin_name]

        # Escribir el runner wrapper en un archivo temporal
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", delete=False, encoding="utf-8"
            ) as tmp:
                tmp.write(_SANDBOX_RUNNER)
                runner_path = tmp.name
        except OSError as e:
            return f"Error creando sandbox runner: {e}"

        try:
            cmd, mode = self._sandbox_command(runner_path, filepath, args)
            result = self._run_plugin_process(cmd)
            if mode == "bubblewrap" and result.returncode != 0 and not result.stdout.strip():
                logger.warning("Bubblewrap no pudo iniciar plugin, usando fallback aislado.")
                fallback = [sys.executable, "-I", runner_path, filepath, args]
                result = self._run_plugin_process(fallback)
            stdout = result.stdout.strip()
            stderr = result.stderr.strip()

            if not stdout:
                if stderr:
                    logger.error("Plugin sandbox stderr: %s", stderr)
                    if "traceback" in stderr.lower():
                        return f"⚠ Plugin '{plugin_name}' falló con un error interno en el proceso secundario (traceback ocultado)."
                    return f"⚠ Plugin '{plugin_name}' no produjo output. stderr: {stderr[:200]}"
                return f"⚠ Plugin '{plugin_name}' no produjo output."

            try:
                data = json.loads(stdout)
                if not isinstance(data, dict):
                    return f"⚠ Plugin '{plugin_name}' no retornó un objeto JSON válido."
                if "ok" not in data:
                    return f"⚠ Plugin '{plugin_name}' no retornó el campo de estado 'ok'."
                
                if data.get("ok"):
                    if "result" not in data:
                        return f"⚠ Plugin '{plugin_name}' no retornó el campo de datos 'result'."
                    return data["result"] or "✓ Plugin ejecutado (sin output)."
                else:
                    logger.debug(
                        "Error en plugin sandbox '%s': %s\n%s",
                        plugin_name, data.get("error"), data.get("tb", "")
                    )
                    return f"Error en plugin '{plugin_name}': {data.get('error', 'Error desconocido')}"
            except json.JSONDecodeError:
                return f"⚠ Plugin '{plugin_name}' produjo output no-JSON: {stdout[:300]}"

        except subprocess.TimeoutExpired:
            logger.warning("Plugin '%s' excedió el timeout (%ds)", plugin_name, _PLUGIN_TIMEOUT_S)
            return f"⏰ Plugin '{plugin_name}' abortado: excedió {_PLUGIN_TIMEOUT_S}s de timeout."
        except Exception as e:
            logger.error("Error ejecutando plugin sandbox '%s': %s", plugin_name, e)
            return f"Error en sandbox de plugin '{plugin_name}': {e}"
        finally:
            try:
                os.unlink(runner_path)
            except OSError:
                pass

    def _sandbox_command(self, runner_path: str, plugin_path: str, args: str) -> tuple[list[str], str]:
        """Construye el comando de sandbox más fuerte disponible."""
        bwrap = shutil.which("bwrap")
        if not bwrap:
            return [sys.executable, "-I", runner_path, plugin_path, args], "python-isolated"

        cmd = [
            bwrap,
            "--die-with-parent",
            "--new-session",
            "--unshare-all",
            "--proc", "/proc",
            "--dev", "/dev",
            "--tmpfs", "/tmp",
            "--tmpfs", "/sandbox",
        ]

        for path in ("/usr", "/bin", "/lib", "/lib64"):
            if os.path.exists(path):
                cmd.extend(["--ro-bind", path, path])

        venv_root = os.path.realpath(sys.prefix)
        if venv_root and os.path.exists(venv_root) and not venv_root.startswith(("/usr", "/bin", "/lib")):
            cmd.extend(["--ro-bind", venv_root, "/venv"])
            try:
                python_cmd = os.path.join("/venv", os.path.relpath(sys.executable, venv_root))
            except ValueError:
                python_cmd = "/venv/bin/python"

        cmd.extend([
            "--ro-bind", runner_path, "/sandbox/runner.py",
            "--ro-bind", plugin_path, "/sandbox/plugin.py",
            "--chdir", "/sandbox",
            "--setenv", "PYTHONDONTWRITEBYTECODE", "1",
            "--setenv", "PYTHONNOUSERSITE", "1",
            python_cmd,
            "-I",
            "/sandbox/runner.py",
            "/sandbox/plugin.py",
            args,
        ])
        return cmd, "bubblewrap"

    def _run_plugin_process(self, cmd: list[str]) -> subprocess.CompletedProcess:
        """Ejecuta el comando del plugin con entorno limpio y límites básicos."""
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=_PLUGIN_TIMEOUT_S,
            env=self._plugin_env(),
            preexec_fn=_limit_plugin_resources if os.name == "posix" else None,
        )

    def _plugin_env(self) -> dict:
        env = {
            "PATH": os.getenv("PATH", "/usr/bin:/bin"),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONNOUSERSITE": "1",
        }
        for key in ("LANG", "LC_ALL"):
            if os.getenv(key):
                env[key] = os.getenv(key)
        return env

    def _run_inprocess(self, plugin_name: str, args: str) -> str:
        """Ejecuta el plugin en el proceso principal."""
        try:
            from plugins.plugin_core import PluginRegistry
            registry = PluginRegistry()
            plugin_inst = registry.get_plugin(plugin_name)
        except Exception:
            plugin_inst = None

        if plugin_inst:
            try:
                import inspect
                parts = args.split(" ", 1)
                method = parts[0]
                method_args = parts[1] if len(parts) > 1 else ""

                if hasattr(plugin_inst, method) and method != "execute":
                    result = plugin_inst.execute(method, method_args)
                else:
                    sig = inspect.signature(plugin_inst.execute)
                    params = [p for p in sig.parameters.values() if p.name != 'self']
                    if len(params) == 1:
                        result = plugin_inst.execute(args)
                    else:
                        result = plugin_inst.execute(method, method_args)
                return str(result) if result is not None else "✓ Plugin ejecutado."
            except Exception as e:
                logger.error("Error en plugin '%s': %s", plugin_name, e)
                return f"Error en plugin '{plugin_name}': {e}"

        # Fallback legado
        if plugin_name not in self.plugins:
            if plugin_name in self._plugin_files:
                self._load_module(plugin_name, self._plugin_files[plugin_name])

        if plugin_name in self.plugins:
            try:
                inst = self.plugins[plugin_name]
                if hasattr(inst, "execute"):
                    import inspect
                    sig = inspect.signature(inst.execute)
                    params = [p for p in sig.parameters.values() if p.name != 'self']
                    if len(params) == 1:
                        result = inst.execute(args)
                    else:
                        parts = args.split(" ", 1)
                        result = inst.execute(parts[0], parts[1] if len(parts) > 1 else "")
                else:
                    # module or other call
                    result = inst(args)
                return str(result) if result is not None else "✓ Plugin ejecutado (sin output)."
            except KeyboardInterrupt:
                return f"⚠ Plugin '{plugin_name}' interrumpido."
            except MemoryError:
                return f"☢ Plugin '{plugin_name}' consumió demasiada memoria."
            except Exception as e:
                tb = traceback.format_exc()
                logger.error("Error ejecutando plugin '%s': %s\n%s", plugin_name, e, tb)
                return f"Error ejecutando plugin '{plugin_name}': {e}"

        return f"Plugin '{plugin_name}' no pudo cargarse."

    def list_plugins(self) -> str:
        """Retorna una lista formateada de plugins disponibles."""
        try:
            from plugins.plugin_core import PluginRegistry
            registry = PluginRegistry()
            reg_plugins = set(registry.list_plugins())
        except Exception:
            reg_plugins = set()

        all_plugins = set(self._plugin_files.keys()) | reg_plugins
        if not all_plugins:
            return "No hay plugins instalados."

        mode_tag = "[bubblewrap]" if self._sandbox and shutil.which("bwrap") else (
            "[python-isolated]" if self._sandbox else "[legado]"
        )
        lines = [f"Modo: {mode_tag}"]
        
        for name in sorted(all_plugins):
            desc = "Sin descripción"
            try:
                meta = registry.get_metadata(name)
                if meta:
                    desc = meta.description
                elif name in self._plugin_files:
                    filepath = self._plugin_files[name]
                    with open(filepath, encoding="utf-8", errors="ignore") as fh:
                        src = fh.read(2000)
                    import re
                    m = re.search(r'def execute\s*\([^)]*\)[^:]*:[\s\n]+"""([^"]+)"""', src)
                    if m:
                        desc = m.group(1).strip().split("\n")[0][:60]
            except Exception:
                pass
            lines.append(f"  • {name}: {desc}")

        return "\n".join(lines)
