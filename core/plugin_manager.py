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

# Sprint 4.2 — Wrapper que ejecuta la función execute() del plugin en un
# subproceso Python aislado, pasando args por stdin y recibiendo resultado por stdout.
_SANDBOX_RUNNER = """
import sys, json, importlib.util, traceback

plugin_path = sys.argv[1]
args        = sys.argv[2] if len(sys.argv) > 2 else ""

try:
    spec   = importlib.util.spec_from_file_location("_plugin", plugin_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.execute(args)
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

    Los plugins son archivos .py en la carpeta plugins/ que deben
    exportar una función execute(args: str) -> str.

    Sprint 4.2 — Modo Sandbox:
        Cada plugin se ejecuta en un subproceso Python independiente con timeout,
        evitando que un plugin malicioso o roto acceda a memoria del proceso principal,
        cuelgue el sistema indefinidamente, o cause errores de importación cruzada.

    El modo sandbox se activa por defecto. Si JELLYFISH_PLUGIN_UNSAFE=1 está
    en el entorno, se usa el modo legado (importación directa) para compatibilidad.
    """

    def __init__(self, plugins_dir: str):
        self.plugins_dir = plugins_dir
        self._plugins_root = os.path.realpath(plugins_dir)
        # Metadatos de plugins descubiertos: {name -> filepath}
        self._plugin_files: dict[str, str] = {}
        # Módulos cargados (solo en modo legado)
        self.plugins: dict = {}
        # Sprint 4.2 — Usar sandbox por defecto, salvo override explícito
        self._sandbox = os.getenv("JELLYFISH_PLUGIN_UNSAFE", "0") != "1"
        os.makedirs(plugins_dir, exist_ok=True)
        self.load_all_plugins()

    # ------------------------------------------------------------------
    # Descubrimiento
    # ------------------------------------------------------------------

    def load_all_plugins(self) -> None:
        """Escanea la carpeta de plugins y registra los archivos disponibles.

        Sprint 4.2 — En modo sandbox solo necesitamos conocer la ruta del archivo;
        la importación ocurre en el subproceso aislado durante run_plugin().
        En modo legado se carga el módulo directamente como antes.
        """
        self._plugin_files.clear()
        self.plugins.clear()

        if not os.path.exists(self.plugins_dir):
            return

        for root_dir, _, files in os.walk(self.plugins_dir):
            for filename in sorted(files):
                if not filename.endswith(".py") or filename.startswith("__"):
                    continue

                filepath = os.path.realpath(os.path.join(root_dir, filename))
                # El nombre del plugin incluye el subdirectorio si existe
                rel_path = os.path.relpath(filepath, self._plugins_root)
                plugin_name = rel_path[:-3] # Quitar .py
                
                if not filepath.startswith(self._plugins_root + os.sep):
                    logger.warning("Plugin fuera de plugins_dir ignorado: %s", filepath)
                    continue
                self._plugin_files[plugin_name] = filepath

            if not self._sandbox:
                # Modo legado: importación directa
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
            if hasattr(module, "execute") and callable(module.execute):
                self.plugins[plugin_name] = module
                logger.info("Plugin cargado (legado): %s", plugin_name)
            else:
                logger.warning("Plugin '%s' no tiene función execute().", plugin_name)
        except SyntaxError as e:
            console.print(f"[dim red]Error de sintaxis en plugin {plugin_name}: {e}[/dim red]")
        except ImportError as e:
            console.print(f"[dim red]Dependencia faltante en plugin {plugin_name}: {e}[/dim red]")
        except Exception as e:
            console.print(f"[dim red]Error cargando plugin {plugin_name}: {e}[/dim red]")

    # ------------------------------------------------------------------
    # Ejecución
    # ------------------------------------------------------------------

    def run_plugin(self, plugin_name: str, args: str) -> str:
        """Ejecuta un plugin por nombre.

        Sprint 4.2 — En modo sandbox, el plugin corre en un subproceso
        Python aislado con timeout. En modo legado, corre en-proceso.

        Args:
            plugin_name: Nombre del plugin.
            args: Argumentos para la función execute().

        Returns:
            Resultado como string, o mensaje de error detallado.
        """
        if plugin_name == "reload":
            self.load_all_plugins()
            discovered = ", ".join(self._plugin_files.keys()) or "ninguno"
            return f"✓ Plugins recargados: {discovered}"

        # Auto-redescubrir si no está registrado
        if plugin_name not in self._plugin_files:
            self.load_all_plugins()

        if plugin_name not in self._plugin_files:
            available = ", ".join(self._plugin_files.keys()) or "ninguno"
            return f"Plugin '{plugin_name}' no encontrado. Disponibles: {available}"

        if self._sandbox:
            return self._run_sandboxed(plugin_name, args)
        else:
            return self._run_inprocess(plugin_name, args)

    def _run_sandboxed(self, plugin_name: str, args: str) -> str:
        """Ejecuta el plugin en un subproceso aislado con timeout.

        Si bubblewrap está disponible, se usa un sandbox de filesystem/red.
        Si no, se cae a Python aislado (-I), entorno sin secretos y límites
        básicos de recursos.
        """
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
                if data.get("ok"):
                    return data["result"] or "✓ Plugin ejecutado (sin output)."
                else:
                    # Bug fix: logger.error enviaba el traceback a stderr (visible en consola).
                    # El traceback va a DEBUG; el usuario ve solo el mensaje de error limpio.
                    logger.debug(
                        "Error en plugin sandbox '%s': %s\n%s",
                        plugin_name, data.get("error"), data.get("tb", "")
                    )
                    return f"Error en plugin '{plugin_name}': {data.get('error')}"
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

        # Si Jellyfish corre desde un venv bajo /home, Python necesita ese venv,
        # pero no se expone el resto del proyecto ni el .env.
        python_cmd = sys.executable
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
        """Ejecuta el plugin en el proceso principal (modo legado)."""
        if plugin_name not in self.plugins:
            self._load_module(plugin_name, self._plugin_files[plugin_name])

        if plugin_name in self.plugins:
            try:
                result = self.plugins[plugin_name].execute(args)
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

    # ------------------------------------------------------------------
    # Listado
    # ------------------------------------------------------------------

    def list_plugins(self) -> str:
        """Retorna una lista formateada de plugins disponibles."""
        if not self._plugin_files:
            return "No hay plugins instalados."

        mode_tag = "[bubblewrap]" if self._sandbox and shutil.which("bwrap") else (
            "[python-isolated]" if self._sandbox else "[legado]"
        )
        lines = [f"Modo: {mode_tag}"]
        for name, filepath in sorted(self._plugin_files.items()):
            # Leer docstring de execute() sin importar el módulo completo
            desc = "Sin descripción"
            try:
                with open(filepath, encoding="utf-8", errors="ignore") as fh:
                    src = fh.read(2000)
                # Buscar docstring simple después de "def execute"
                import re
                m = re.search(r'def execute\s*\([^)]*\)[^:]*:[\s\n]+"""([^"]+)"""', src)
                if m:
                    desc = m.group(1).strip().split("\n")[0][:60]
            except OSError:
                pass
            lines.append(f"  • {name}: {desc}")

        return "\n".join(lines)
