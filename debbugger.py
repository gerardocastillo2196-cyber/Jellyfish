import subprocess
import time
import sys

def simulate_terminal_issue():
    print("Iniciando prueba de captura de comando (similar a core/terminal.py)...")
    command = "echo 'Iniciando tarea larga...' && sleep 2 && echo 'Paso 1' && sleep 2 && echo 'Terminado!'"
    
    # Esto es exactamente lo que hace run_terminal_command
    print("Ejecutando (ahora deberías ver el texto en tiempo real)...")
    start = time.time()
    process = subprocess.Popen(
        command,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    
    captured_output = []
    
    import threading
    def _read_output():
        for line in process.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
            captured_output.append(line)
            
    reader = threading.Thread(target=_read_output)
    reader.start()
    
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        
    reader.join()
    end = time.time()
    stdout = "".join(captured_output)
    
    print(f"\n¡Comando finalizado en {end - start:.2f}s!")
    print("Salida capturada:")
    print(stdout)
    
if __name__ == "__main__":
    simulate_terminal_issue()
