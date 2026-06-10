#!/usr/bin/env python3
"""setup.py — Script de configuración y auditoría para Jellyfish OS v6.0.

Permite:
  --setup: Inicializar la estructura y copiar agentes, skills y plugins.
  --status: Auditar el estado actual del entorno y configuración de Jellyfish.
"""

import os
import sys
import argparse

# Asegurar que el core se puede importar desde el directorio del script
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.config import AGENCY_DIR

def setup_environment():
    import shutil
    repo_dir = os.path.dirname(os.path.abspath(__file__))
    print(f"Inicializando Jellyfish OS en AGENCY_DIR: {AGENCY_DIR}")
    
    # Crear directorios
    for folder in ["agents", "skills", "plugins", "memory"]:
        dest_folder = os.path.join(AGENCY_DIR, folder)
        os.makedirs(dest_folder, exist_ok=True)
        print(f"✓ Directorio verificado/creado: {dest_folder}")
        
    # Copiar agentes
    agents_src = os.path.join(repo_dir, "agents")
    if os.path.isdir(agents_src):
        for root, _, files in os.walk(agents_src):
            for file in sorted(files):
                if file.endswith(".py") or file.endswith(".md"):
                    src_file = os.path.join(root, file)
                    rel_path = os.path.relpath(src_file, agents_src)
                    dest_file = os.path.join(AGENCY_DIR, "agents", rel_path)
                    os.makedirs(os.path.dirname(dest_file), exist_ok=True)
                    shutil.copy2(src_file, dest_file)
        print("✓ Agentes copiados.")

    # Copiar skills
    skills_src = os.path.join(repo_dir, "skills")
    if os.path.isdir(skills_src):
        for root, _, files in os.walk(skills_src):
            for file in sorted(files):
                if file.endswith(".py") or file.endswith(".md") or file.endswith(".json"):
                    src_file = os.path.join(root, file)
                    rel_path = os.path.relpath(src_file, skills_src)
                    dest_file = os.path.join(AGENCY_DIR, "skills", rel_path)
                    os.makedirs(os.path.dirname(dest_file), exist_ok=True)
                    shutil.copy2(src_file, dest_file)
        print("✓ Skills copiados.")

    # Copiar plugins
    plugins_src = os.path.join(repo_dir, "plugins")
    if os.path.isdir(plugins_src):
        for root, _, files in os.walk(plugins_src):
            for file in sorted(files):
                if file.endswith(".py") or file.endswith(".json"):
                    src_file = os.path.join(root, file)
                    rel_path = os.path.relpath(src_file, plugins_src)
                    dest_file = os.path.join(AGENCY_DIR, "plugins", rel_path)
                    os.makedirs(os.path.dirname(dest_file), exist_ok=True)
                    shutil.copy2(src_file, dest_file)
        print("✓ Plugins copiados.")

    # Sincronizar .env de la raíz al AGENCY_DIR
    env_dest = os.path.join(AGENCY_DIR, ".env")
    env_src = os.path.join(repo_dir, ".env")
    if not os.path.isfile(env_src):
        env_src = os.path.join(repo_dir, ".env.example")
        
    if os.path.isfile(env_src):
        if os.path.isfile(env_dest):
            # Hacer backup del .env actual antes de sobreescribir
            try:
                shutil.copy2(env_dest, env_dest + ".bak")
                print(f"✓ Copia de respaldo de .env creada en {env_dest}.bak")
            except Exception as e:
                print(f"⚠ No se pudo crear copia de respaldo: {e}")
        shutil.copy2(env_src, env_dest)
        print(f"✓ Archivo .env sincronizado desde {os.path.basename(env_src)}")
    else:
        print("⚠ Advertencia: No se encontró archivo .env o .env.example en la raíz del repositorio.")
        
    print("\n🎉 Configuración completada con éxito.")

def check_status():
    try:
        from rich.console import Console
        from rich.table import Table
    except ImportError:
        print("Error: El paquete 'rich' es requerido para mostrar el estado. Ejecuta: pip install rich")
        sys.exit(1)

    from core.agents.registry import AgentRegistry
    from core.skills.registry import SkillRegistry
    
    console = Console()
    console.print("\n[bold purple]🔍 Auditando Estado de Jellyfish OS v6.0[/bold purple]\n")
    
    # 1. Rutas
    console.print(f"[bold]Directorio de Trabajo (AGENCY_DIR):[/bold] {AGENCY_DIR}")
    
    # 2. Archivo .env
    env_path = os.path.join(AGENCY_DIR, ".env")
    if os.path.isfile(env_path):
        console.print("[green]✓ Archivo .env encontrado[/green]")
    else:
        console.print("[red]✗ Archivo .env NO encontrado[/red]")
        
    # 3. Escaneo de agentes y skills en AGENCY_DIR
    agents_dir = os.path.join(AGENCY_DIR, "agents")
    skills_dir = os.path.join(AGENCY_DIR, "skills")
    
    # Escanear
    num_agents = AgentRegistry.scan(agents_dir)
    num_skills = SkillRegistry.scan(skills_dir)
    
    console.print(f"[bold]Agentes registrados:[/bold] {num_agents}")
    console.print(f"[bold]Skills registradas:[/bold] {num_skills}")
    
    # Listado de agentes registrados
    if num_agents > 0:
        agents_list = sorted(list(AgentRegistry._registry.keys()))
        console.print(f"[dim]Agentes: {', '.join('@' + name for name in agents_list)}[/dim]")
        
    # Listado de agencias de skills
    if num_skills > 0:
        skills_list = sorted(list(SkillRegistry._registry.keys()))
        console.print(f"[dim]Total de habilidades detectadas: {len(skills_list)}[/dim]")
        
    # 4. Proveedor e IA
    from core.state import JellyfishState
    state = JellyfishState()
    # Inicializar config
    try:
        from core.config import load_config_from_env
        load_config_from_env(state)
        console.print(f"\n[bold]Proveedor Activo:[/bold] {state.provider.upper()}")
        console.print(f"[bold]Modelo Activo:[/bold] {state.model}")
        
        # Verificar api key si es un cloud provider
        if state.provider in ["openai", "deepseek", "openrouter", "gemini", "qwen", "kimi", "zhipu"]:
            key_name = f"{state.provider}_api_key"
            api_key = getattr(state, key_name, "") or state.api_keys.get(state.provider, "")
            if api_key:
                masked = api_key[:6] + "..." + api_key[-4:] if len(api_key) > 10 else "configurada"
                console.print(f"[green]✓ API Key configurada:[/green] {masked}")
            else:
                console.print("[red]✗ API Key NO configurada para el proveedor activo[/red]")
    except Exception as e:
        console.print(f"[red]Error leyendo configuración: {e}[/red]")
        
    # 5. Proyecto Activo
    project_path = getattr(state, "active_project", "")
    if project_path:
        console.print(f"[bold]Proyecto Activo:[/bold] {project_path}")
        if os.path.isdir(project_path):
            console.print("[green]✓ Directorio de proyecto activo válido[/green]")
        else:
            console.print("[yellow]⚠ Directorio de proyecto activo no existe o es inválido[/yellow]")
    else:
        console.print("[yellow]⚠ No hay ningún proyecto activo configurado (usa /project <path>)[/yellow]")

def main():
    parser = argparse.ArgumentParser(description="Script de configuración y auditoría para Jellyfish OS.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--setup", action="store_true", help="Inicializa el entorno y copia los archivos a AGENCY_DIR.")
    group.add_argument("--status", action="store_true", help="Muestra el estado de la instalación y configuración.")
    
    args = parser.parse_args()
    
    if args.setup:
        setup_environment()
    elif args.status:
        check_status()

if __name__ == "__main__":
    main()
