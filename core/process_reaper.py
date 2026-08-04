"""
Process Reaper — Sistema de limpieza total de procesos hijo, descriptores de archivo y bloqueos en el host de Jellyfish OS.
Garantiza el aislamiento y terminación de cualquier subproceso huérfano (Ollama, terminales, servidores locales, etc.) al cerrar el sistema.
"""
import os
import signal
import subprocess
import threading
import time
import logging
import atexit
import sys

logger = logging.getLogger("jellyfish.process_reaper")


class ProcessReaper:
    """Orquestador centralizado para la gestión del ciclo de vida y limpieza de subprocesos y recursos de host."""
    
    _instance = None
    _lock = threading.RLock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(ProcessReaper, cls).__new__(cls)
                cls._instance._processes = set()
                cls._instance._callbacks = []
                cls._instance._initialized = False
                cls._instance._reaping_done = False
                cls._instance._setup_handlers()
            return cls._instance

    def _setup_handlers(self):
        """Registra los ganchos de limpieza en atexit y señales del sistema (SIGTERM, SIGHUP)."""
        if self._initialized:
            return
        self._initialized = True
        atexit.register(self.reap_all)
        
        try:
            if threading.current_thread() is threading.main_thread():
                signal.signal(signal.SIGTERM, self._signal_handler)
                signal.signal(signal.SIGHUP, self._signal_handler)
        except (ValueError, AttributeError, RuntimeError) as err:
            logger.debug("No se pudieron registrar manejadores de señal en ProcessReaper: %s", err)

    def _signal_handler(self, signum, frame):
        """Manejador de interrupciones para asegurar apagado ordenado ante kill o cierre de terminal."""
        logger.warning("Señal del sistema (%s) recibida. Ejecutando limpieza total en el host...", signum)
        self.reap_all()
        os._exit(0)

    def register_process(self, proc):
        """Registra un objeto Popen o PID para supervisión de ciclo de vida."""
        with self._lock:
            self._processes.add(proc)

    def unregister_process(self, proc):
        """Remueve un proceso que ya finalizó con éxito de la lista de supervisión."""
        with self._lock:
            self._processes.discard(proc)

    def register_callback(self, callback_fn, *args, **kwargs):
        """Registra una función de limpieza (e.g. desbloquear .jellyfish.lock o parar Ollama)."""
        with self._lock:
            self._callbacks.append((callback_fn, args, kwargs))

    def reap_all(self):
        """Ejecuta todos los callbacks de limpieza y fuerza la terminación de cualquier subproceso del host."""
        with self._lock:
            if self._reaping_done:
                return
            self._reaping_done = True
            logger.info("Iniciando reap_all() de subprocesos y recursos de Jellyfish OS...")

            # 1. Ejecutar todos los callbacks registrados de liberación (e.g., locks, clientes HTTP)
            for callback_fn, args, kwargs in list(self._callbacks):
                try:
                    callback_fn(*args, **kwargs)
                except Exception as err:
                    logger.debug("Error en callback de limpieza: %s", err)
            self._callbacks.clear()

            # 2. Terminar procesos registrados en el pool explícito (SIGTERM -> SIGKILL)
            for proc in list(self._processes):
                self._terminate_proc_handle(proc)
            self._processes.clear()

            # 3. Limpieza de Ollama (si hubiera instancia local huérfana de esta sesión)
            try:
                from core.llm_engine import _cleanup_ollama
                _cleanup_ollama()
            except Exception:
                pass

            # 4. SWEEP DE HOST (Fail-Safe en Linux): Eliminar cualquier subproceso huérfano
            # de nuestro PID actual mediante pkill -9 -P <pid>.
            try:
                my_pid = os.getpid()
                subprocess.run(["pkill", "-9", "-P", str(my_pid)], capture_output=True)
            except Exception:
                pass

    def _terminate_proc_handle(self, proc):
        """Intenta finalizar amablemente (SIGTERM) y si falla o sigue activo, liquida el grupo de procesos."""
        try:
            pid = getattr(proc, "pid", proc)
            if pid and isinstance(pid, int):
                try:
                    pgid = os.getpgid(pid)
                    os.killpg(pgid, signal.SIGTERM)
                    time.sleep(0.05)
                    try:
                        os.killpg(pgid, signal.SIGKILL)
                    except OSError:
                        pass
                except (ProcessLookupError, OSError):
                    try:
                        os.kill(pid, signal.SIGKILL)
                    except OSError:
                        pass
        except Exception as err:
            logger.debug("Error en terminación forzada del proceso %s: %s", proc, err)


# Instancia singleton global exportada
reaper = ProcessReaper()
