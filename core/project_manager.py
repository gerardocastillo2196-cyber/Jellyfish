import os
import logging

logger = logging.getLogger("jellyfish.project_manager")

def cleanup_lock(project_path: str) -> None:
    """Libera el lock del proyecto."""
    if project_path and os.path.isdir(project_path):
        lock_path = os.path.join(project_path, ".jellyfish.lock")
        if os.path.exists(lock_path):
            try:
                with open(lock_path, "r") as f:
                    pid = int(f.read().strip())
                if pid == os.getpid():
                    os.unlink(lock_path)
            except Exception:
                pass

def update_project_lock(state, old_project: str) -> None:
    """Libera el lock del proyecto anterior y adquiere el del nuevo proyecto."""
    if old_project:
        cleanup_lock(old_project)
        
    if state.active_project and os.path.isdir(state.active_project):
        lock_path = os.path.join(state.active_project, ".jellyfish.lock")
        try:
            with open(lock_path, "x") as f:
                f.write(str(os.getpid()))
            import atexit
            atexit.register(cleanup_lock, state.active_project)
        except FileExistsError:
            try:
                with open(lock_path, "r") as f:
                    pid = int(f.read().strip())
                
                pid_exists = False
                if pid > 0:
                    try:
                        os.kill(pid, 0)
                        pid_exists = True
                    except OSError:
                        pass
                        
                if not pid_exists:
                    with open(lock_path, "w") as f:
                        f.write(str(os.getpid()))
                    return
                    
                if pid != os.getpid():
                    from rich.console import Console
                    Console().print(
                        f"\n⚠️  ¡ADVERTENCIA DE CONCURRENCIA! El proyecto {state.active_project} "
                        f"ya está abierto en otra instancia de Jellyfish OS (PID: {pid}).\n"
                        f"Para prevenir corrupción de datos en ChromaDB y conflictos de archivos, "
                        f"por favor evita realizar cambios simultáneos desde ambas sesiones.\n"
                    )
            except Exception:
                pass

        try:
            setup_project_virtual_env(state)
        except Exception as e:
            logger.error("Error en setup_project_virtual_env: %s", e)

def setup_project_virtual_env(state) -> None:
    """Identifica si el proyecto activo tiene Python, y si es así crea un venv automáticamente."""
    if not state.active_project or not os.path.isdir(state.active_project):
        return
        
    has_python = False
    for root, dirs, files in os.walk(state.active_project):
        dirs[:] = [d for d in dirs if d not in ('.git', 'venv', '.venv', 'node_modules')]
        for f in files:
            if f.endswith('.py') or f in ('requirements.txt', 'pyproject.toml', 'setup.py', 'Pipfile'):
                has_python = True
                break
        if has_python:
            break
            
    if has_python:
        venv_path = os.path.join(state.active_project, ".venv")
        if not os.path.isdir(venv_path):
            from rich.console import Console
            import subprocess
            Console().print(f"\n⚡ Detectada tecnología Python en el proyecto. Creando entorno virtual (.venv)...")
            try:
                subprocess.run(["python3", "-m", "venv", ".venv"], cwd=state.active_project, check=True)
                Console().print("✓ Entorno virtual (.venv) creado con éxito.")
            except Exception as e:
                Console().print(f"⚠ Error al crear el entorno virtual: {e}")

def is_project_auto_approved(state) -> bool:
    """Retorna True si el proyecto activo tiene la auto-aprobación de comandos activada (Sprint 11)."""
    if not state.active_project or not os.path.isdir(state.active_project):
        return False
    config_path = os.path.join(state.active_project, ".jellyfish_project_config.json")
    if not os.path.isfile(config_path):
        return False
    try:
        import json
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("allow_all_commands", False)
    except Exception:
        return False

def enable_project_auto_approve(state) -> None:
    """Activa la auto-aprobación persistente para el proyecto activo (Sprint 11)."""
    if not state.active_project or not os.path.isdir(state.active_project):
        return
    config_path = os.path.join(state.active_project, ".jellyfish_project_config.json")
    try:
        import json
        data = {}
        if os.path.isfile(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                pass
        data["allow_all_commands"] = True
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        logger.error("Error guardando auto-aprobación del proyecto: %s", e)
