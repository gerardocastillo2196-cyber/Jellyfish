import os
import time
import subprocess
import tempfile
import pytest
from core.process_reaper import ProcessReaper


def test_process_reaper_terminates_registered_subprocess():
    # Crear una nueva instancia independiente para test para no afectar la principal
    reaper = ProcessReaper.__new__(ProcessReaper)
    reaper._processes = set()
    reaper._callbacks = []
    reaper._reaping_done = False
    reaper._lock = ProcessReaper._lock
    
    # Arrancar un subproceso de prueba que dura 60 segundos
    proc = subprocess.Popen(
        ["sleep", "60"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        preexec_fn=os.setpgrp,
    )
    
    reaper.register_process(proc)
    assert len(reaper._processes) == 1
    
    # Ejecutar reap_all
    reaper.reap_all()
    
    # Verificar que el proceso ha sido terminado y ya no sigue activo
    proc.poll()
    if proc.returncode is None:
        # Esperar un instante por la propagación de la señal en Linux
        time.sleep(0.2)
        proc.poll()
        
    assert proc.returncode is not None, "El proceso hijo debería haber sido terminado por ProcessReaper"
    assert len(reaper._processes) == 0


def test_process_reaper_executes_callbacks():
    reaper = ProcessReaper.__new__(ProcessReaper)
    reaper._processes = set()
    reaper._callbacks = []
    reaper._reaping_done = False
    reaper._lock = ProcessReaper._lock
    
    callback_executed = []
    
    def my_cleanup_callback(filename):
        callback_executed.append(filename)

    reaper.register_callback(my_cleanup_callback, "test_lock_file.lock")
    assert len(reaper._callbacks) == 1
    
    reaper.reap_all()
    
    assert callback_executed == ["test_lock_file.lock"]
    assert len(reaper._callbacks) == 0


def test_is_same_session_process():
    from core.project_manager import is_same_session_process
    # Nuestro propio PID es de la misma sesión
    assert is_same_session_process(os.getpid()) is True
    # PID 0 no existe/no es de la misma sesión
    assert is_same_session_process(0) is False


def test_cleanup_lock_same_session():
    from core.project_manager import cleanup_lock
    with tempfile.TemporaryDirectory() as tmpdir:
        lock_path = os.path.join(tmpdir, ".jellyfish.lock")
        # Crear lock con el PID actual
        with open(lock_path, "w") as f:
            f.write(str(os.getpid()))
        
        cleanup_lock(tmpdir)
        assert not os.path.exists(lock_path)

