"""core/orchestration/build_healer.py — Lógica desacoplada de auto-curación y Sentinel auto-healing."""

import os
import re
import time
import logging
from datetime import datetime
from rich.console import Console
from core.utils import _safe_read

logger = logging.getLogger("jellyfish.orchestration.build_healer")
console = Console()

SENTINEL_HEALER_SYSTEM = """Eres @Sentinel, el agente experto de control de calidad, depuración y auto-curación de Jellyfish OS.
Tu misión es recibir una tarea técnica, los archivos de código que se generaron, y el log detallado del error de compilación, sintaxis o DoD.
Debes analizar el log de error para diagnosticar exactamente qué causó el fallo.

Tienes tres opciones de respuesta. Debes elegir la más adecuada y responder en el formato exacto:

1) AUTO_FIX: Si puedes corregir el código del archivo que falló directamente (ej: añadir un import, corregir sintaxis YAML, cambiar una línea de código).
Formato de respuesta:
[AUTO_FIX]
Explicación breve de la corrección.
<write_file path="ruta/del/archivo.ext">
contenido del archivo corregido...
</write_file>

2) FEEDBACK: Si la corrección requiere lógica compleja en múltiples archivos o reestructuraciones que debe hacer el desarrollador original.
Formato de respuesta:
[FEEDBACK]
Instrucciones detalladas paso a paso para corregir el error en el próximo intento.

3) ASK_USER: Si necesitas aclarar requisitos críticos, decisiones de diseño o permisos especiales del usuario.
Formato de respuesta:
[ASK_USER]
Escribe la pregunta específica y directa para el usuario.
"""

def classify_build_error(output: str) -> str:
    """Clasifica el error de compilación para guiar al Auto-Healing."""
    out_lower = output.lower()
    if "dependency" in out_lower or "cannot find module" in out_lower or "no module named" in out_lower or "unresolved reference" in out_lower or "import error" in out_lower:
        return "ERROR DE DEPENDENCIAS: Faltan paquetes o librerías en el entorno."
    if "permission denied" in out_lower or "command not found" in out_lower or "not recognized" in out_lower:
        return "ERROR DE ENTORNO/PERMISOS: Falta ejecutar herramientas o configurar permisos de ejecución."
    if "syntax" in out_lower or "compile error" in out_lower or "indentationerror" in out_lower or "unexpected token" in out_lower:
        return "ERROR DE SINTAXIS/CÓDIGO: El código generado tiene errores de sintaxis o de compilación estática."
    return "ERROR GENERAL DE COMPILACIÓN: Error de lógica o configuración."

def is_safe_healing_command(cmd: str) -> bool:
    """Verifica si un comando del auto-healing es seguro (control de blast radius)."""
    cmd_lower = cmd.lower()
    dangerous = ["rm ", "rm -", "uninstall", "purge", "delete", "fdisk", "mkfs", "dd ", "shred"]
    for d in dangerous:
        if d in cmd_lower:
            allowed_rm = [
                "rm -rf build", "rm -rf dist", "rm -rf .pytest_cache", 
                "rm -rf __pycache__", "rm -rf node_modules", 
                "rm -rf .venv", "rm -rf venv", "rm -f package-lock.json",
                "rm -f yarn.lock", "rm -f pnpm-lock.yaml"
            ]
            is_allowed = False
            for clean_rm in allowed_rm:
                if clean_rm in cmd_lower:
                    is_allowed = True
            if not is_allowed:
                return False
    return True

def try_deterministic_healing(orchestrator, cmd: str, build_output: str) -> tuple[bool, int, str]:
    """Intenta curar errores comunes de forma determinista sin usar IA."""
    from core.terminal import run_terminal_command
    
    # 1. Módulo Python faltante o error de importación
    python_import_match = re.search(r"ModuleNotFoundError:\s+No\s+module\s+named\s+['\"]?([a-zA-Z0-9_-]+)['\"]?", build_output)
    if not python_import_match:
        python_import_match = re.search(r"ImportError:\s+cannot\s+import\s+name\s+['\"]?([a-zA-Z0-9_-]+)['\"]?", build_output)
        
    if python_import_match:
        module_name = python_import_match.group(1)
        console.print(f"       [bold green]✓[/bold green] [green]Curación Determinista: Detectado módulo Python faltante '{module_name}'. Instalando...[/green]")
        pip_cmd = "pip"
        for venv_dir in ("venv", ".venv"):
            venv_pip = os.path.join(orchestrator.project_path, venv_dir, "bin", "pip")
            if os.path.exists(venv_pip):
                pip_cmd = venv_pip
                break
        
        run_terminal_command(f"{pip_cmd} install {module_name}", orchestrator.state, silent_history=True)
        
        # Re-correr comando original
        ret_dict = {'returncode': 0}
        new_output = run_terminal_command(cmd, orchestrator.state, silent_history=True, force_confirm=True, return_code_dict=ret_dict)
        return True, ret_dict['returncode'], new_output

    # 2. Módulo Node.js/npm faltante
    node_import_match = re.search(r"Cannot\s+find\s+module\s+['\"]?([a-zA-Z0-9_-]+)['\"]?", build_output)
    if node_import_match:
        module_name = node_import_match.group(1)
        console.print(f"       [bold green]✓[/bold green] [green]Curación Determinista: Detectado módulo npm faltante '{module_name}'. Instalando...[/green]")
        run_terminal_command(f"npm install {module_name}", orchestrator.state, silent_history=True)
        
        # Re-correr comando original
        ret_dict = {'returncode': 0}
        new_output = run_terminal_command(cmd, orchestrator.state, silent_history=True, force_confirm=True, return_code_dict=ret_dict)
        return True, ret_dict['returncode'], new_output

    return False, 0, ""

def auto_heal_build_error(orchestrator, cmd: str, returncode: int, build_output: str) -> tuple[int, str]:
    """Bucle Autónomo de Resolución de Errores (Auto-Healing Loop) con un máximo de 3 iteraciones."""
    from core.terminal import run_terminal_command
    from core.llm_engine import _call_llm_silent
    
    current_code = returncode
    current_output = build_output
    healing_attempts_log = []
    
    # Intentar curación determinista rápida antes de recurrir a la IA
    resolved, code, out = try_deterministic_healing(orchestrator, cmd, build_output)
    if resolved:
        if code == 0:
            console.print("       ✓ ¡Auto-Healing Determinista exitoso! El entorno se ha auto-recuperado.")
            return 0, out
        else:
            current_code = code
            current_output = out
            
    error_class = classify_build_error(current_output)
    
    for attempt in range(1, 4):
        console.print(f"\n       ⚡ [Auto-Healing Loop] Intento {attempt}/3 para resolver fallo de compilación...")
        console.print(f"       [dim]Clasificación del fallo: {error_class}[/dim]")
        
        # DIAGNÓSTICO: Analizar archivos del entorno para dar contexto
        files_list = []
        for root, dirs, files in os.walk(orchestrator.project_path):
            dirs[:] = [d for d in dirs if d not in ('.git', 'node_modules', '.venv', 'venv', '__pycache__')]
            for f in files:
                files_list.append(os.path.relpath(os.path.join(root, f), orchestrator.project_path))
                
        files_context = "\n".join(files_list[:100])
        
        system_prompt = (
            "Eres un Agente Especialista en Auto-Recuperación de Sistemas (Auto-Healing Agent).\n"
            "Tu objetivo es diagnosticar y reparar problemas del entorno (ej. dependencias no instaladas, permisos faltantes, configuraciones erróneas, Dockerfiles rotos, etc.) para que el comando de compilación/verificación tenga éxito.\n\n"
            "Instrucciones:\n"
            "1. Analiza el comando que falló y la salida exacta del error.\n"
            "2. Propón la solución:\n"
            "   - Para escribir/modificar un archivo, usa:\n"
            "     <write_file path=\"ruta/relativa/archivo.ext\">\n"
            "     contenido corregido del archivo\n"
            "     </write_file>\n"
            "   - Para ejecutar comandos que solucionen el entorno (ej. chmod +x, npm install, export, mkdir, etc.), usa:\n"
            "     <run_command>comando a ejecutar</run_command>\n\n"
            "No des introducciones, sé ultra directo y responde solo con código y parches."
        )
        
        user_prompt = (
            f"COMANDO QUE FALLÓ:\n`{cmd}`\n\n"
            f"CÓDIGO DE SALIDA: {current_code}\n\n"
            f"TIPO DE ERROR DETECTADO: {error_class}\n\n"
            f"SALIDA DE ERROR (stdout/stderr):\n```\n{current_output}\n```\n\n"
            f"ARCHIVOS DISPONIBLES EN EL PROYECTO:\n{files_context}\n\n"
            f"Genera tus parches de corrección usando <write_file> y/o <run_command>."
        )
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        response = _call_llm_silent(orchestrator.state, messages, provider=orchestrator.state.provider, model=orchestrator.state.model)
        if not response:
            console.print("       ⚠ No se obtuvo respuesta del Agente de Auto-Recuperación.")
            healing_attempts_log.append(f"Intento {attempt}: Sin respuesta del modelo.")
            continue
            
        # EJECUCIÓN DE PARCHE
        created_files = orchestrator._extract_and_write_files(response)
        executed_cmds = []
        cmd_matches = re.findall(r'<run_command>(.*?)</run_command>', response, re.DOTALL)
        for cmd_to_run in cmd_matches:
            cmd_clean = cmd_to_run.strip()
            if cmd_clean:
                if not is_safe_healing_command(cmd_clean):
                    console.print(f"       🛡 Bloqueado comando potencialmente peligroso en Auto-Healing: {cmd_clean}")
                    healing_attempts_log.append(f"Intento {attempt}: Comando peligroso '{cmd_clean}' bloqueado por seguridad.")
                    continue
                console.print(f"       ⚙ Ejecutando parche de entorno: {cmd_clean}")
                run_terminal_command(cmd_clean, orchestrator.state, silent_history=True)
                executed_cmds.append(cmd_clean)
                
        healing_attempts_log.append(
            f"Intento {attempt}:\n"
            f"  - Archivos modificados: {created_files}\n"
            f"  - Comandos ejecutados: {executed_cmds}"
        )
        
        # REINTENTO
        console.print(f"       🔄 Reintentando comando original: {cmd}")
        ret_dict = {'returncode': 0}
        new_output = run_terminal_command(
            cmd,
            orchestrator.state,
            silent_history=True,
            timeout=300,
            force_confirm=True,
            return_code_dict=ret_dict
        )
        
        current_code = ret_dict['returncode']
        current_output = new_output
        
        if current_code == 0:
            console.print("       ✓ ¡Auto-Healing exitoso! El entorno se ha auto-recuperado.")
            return 0, current_output
            
    # ESCALAMIENTO
    console.print("       ❌ Auto-Healing Loop falló tras 3 intentos. Escalando error.")
    if not hasattr(orchestrator.state, "healing_failures"):
        orchestrator.state.healing_failures = {}
    orchestrator.state.healing_failures[cmd] = "\n".join(healing_attempts_log)
    
    return current_code, current_output

def run_sentinel_auto_healing(
    orchestrator,
    task_id: str,
    agent_name: str,
    task_desc: str,
    output_file: str,
    error_log: str,
    created_files: list[str],
    get_user_input_nonblocking_fn
) -> tuple[str, str]:
    """Invoca autónomamente a @Sentinel para diagnosticar y auto-corregir el error."""
    from core.terminal import screen_console as scr_console
    from core.llm_engine import _call_llm_silent
    
    scr_console.print(f"\n[bold yellow]🛡️  @Sentinel[/bold yellow] analizando error del primer fallo para auto-curar la tarea...")
    
    files_context = ""
    for rel_f in created_files:
        abs_f = os.path.join(orchestrator.project_path, rel_f)
        if os.path.isfile(abs_f):
            content = _safe_read(abs_f)
            files_context += f"--- ARCHIVO: {rel_f} ---\n{content}\n\n"
            
    user_prompt = (
        f"TAREA ID: {task_id}\n"
        f"AGENTE ENCARGADO: @{agent_name}\n"
        f"DESCRIPCIÓN DE LA TAREA: {task_desc}\n"
        f"ENTREGABLE ESPERADO: {output_file}\n\n"
        f"[ARCHIVOS DE CÓDIGO ACTUALES]\n{files_context}\n"
        f"[LOG DE ERROR DETALLADO]\n{error_log}\n"
    )
    
    try:
        sentinel_res = _call_llm_silent(
            orchestrator.state,
            [
                {"role": "system", "content": SENTINEL_HEALER_SYSTEM},
                {"role": "user", "content": user_prompt}
            ],
            agent_name="sentinel"
        )
    except Exception as e:
        logger.error("Error al invocar a @Sentinel para auto-healing: %s", e)
        return "FEEDBACK", f"Error invocando a @Sentinel Healer: {e}"
        
    if not sentinel_res:
        return "FEEDBACK", "Sentinel Healer no retornó ninguna respuesta."
        
    sentinel_res_strip = sentinel_res.strip()
    
    if sentinel_res_strip.startswith("[AUTO_FIX]"):
        fixed_files = orchestrator._extract_and_write_files(sentinel_res_strip)
        explanation = sentinel_res_strip.split("[AUTO_FIX]")[1].split("<write_file")[0].strip()
        
        if not fixed_files and "<write_file" not in sentinel_res_strip:
            code_match = re.search(r'```[a-zA-Z0-9_-]*\n(.*?)\n```', sentinel_res_strip, re.DOTALL)
            if code_match and len(created_files) == 1:
                target_f = created_files[0]
                full_target = os.path.join(orchestrator.project_path, target_f)
                with open(full_target, "w", encoding="utf-8") as f:
                    f.write(code_match.group(1))
                fixed_files = [target_f]
        
        if fixed_files:
            log_msg = f"🛡️ @Sentinel (Auto-Healing) aplicó corrección en: {', '.join(fixed_files)}. Razón: {explanation}"
            scr_console.print(f"       [bold green]✓[/bold green] [green]{log_msg}[/green]")
            logger.info(log_msg)
            
            _write_sentinel_action_to_log(orchestrator, task_id, log_msg)
            return "AUTO_FIX", explanation
        else:
            return "FEEDBACK", f"Sentinel intentó AUTO_FIX pero no se pudieron parsear las etiquetas de escritura. Razón: {explanation}"
            
    elif sentinel_res_strip.startswith("[ASK_USER]"):
        question = sentinel_res_strip.replace("[ASK_USER]", "").strip()
        scr_console.print("\n[bold yellow]──────────────────────────────────────────────────────────────────────[/bold yellow]")
        scr_console.print(f"[bold yellow]🛡️ @Sentinel REQUIERE TU AYUDA PARA DEPURAR:[/bold yellow]")
        scr_console.print(f"[yellow]{question}[/yellow]")
        scr_console.print("[bold yellow]──────────────────────────────────────────────────────────────────────[/bold yellow]")
        
        user_response = get_user_input_nonblocking_fn("✍ Escribe tu respuesta: ").strip()
        feedback_msg = f"Respuesta del usuario para Sentinel: '{user_response}'. Análisis previo de Sentinel: {question}"
        return "ASK_USER", feedback_msg
        
    else:
        feedback_text = sentinel_res_strip.replace("[FEEDBACK]", "").strip()
        log_msg = f"🛡️ @Sentinel generó instrucciones de corrección: {feedback_text[:120]}..."
        scr_console.print(f"       [yellow]{log_msg}[/yellow]")
        return "FEEDBACK", feedback_text

def _write_sentinel_action_to_log(orchestrator, task_id: str, log_msg: str) -> None:
    """Registra la acción correctiva de Sentinel en DEVELOPMENT_LOG.md."""
    try:
        log_filename = "DEVELOPMENT_LOG.md"
        existing_log = orchestrator._read_project_file(log_filename) or ""
        
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        entry = f"\n* **[{timestamp}] 🛡️ @Sentinel (Auto-Healing) — {task_id}**: {log_msg}\n"
        
        updated_log = existing_log.rstrip() + "\n" + entry
        orchestrator._write_project_file(log_filename, updated_log)
    except Exception as e:
        logger.warning("No se pudo registrar la acción de Sentinel en DEVELOPMENT_LOG.md: %s", e)
