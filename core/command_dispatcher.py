import sys
from core.ui import console

def handle_slash_command(cmd_input: str, state, rag, plugins, display_header_func) -> None:
    parts = cmd_input.split(" ", 1)
    command = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""

    # Aliases
    aliases = {
        "/a": "/agent",
        "/s": "/skill",
        "/c": "/context",
        "/r": "/run",
        "/p": "/project",
        "/h": "/help",
        "/m": "/model",
        "/d": "/debug",
        "/build": "/auto",
        "/info": "/status"
    }
    command = aliases.get(command, command)

    if command == "/exit":
        sys.exit(0)
    
    elif command in ("/goff", "/gon", "/clear", "/help", "/run", "/plugin", "/errors", "/debug", "/status"):
        from core.commands.system import handle_system_command
        handle_system_command(command, arg, state, plugins, display_header_func)
        
    elif command in ("/add", "/context", "/purge", "/context-f.del", "/rag", "/ignore"):
        from core.commands.rag import handle_rag_command
        handle_rag_command(command, arg, state, rag, display_header_func)
        
    elif command in ("/project", "/compile"):
        from core.commands.project import handle_project_command
        handle_project_command(command, arg, state, rag, display_header_func)
        
    elif command in ("/config", "/model", "/provider"):
        from core.commands.config import handle_config_command
        handle_config_command(command, arg, state, display_header_func)
        
    elif command in ("/agent", "/skill"):
        from core.commands.entity import handle_entity_command
        handle_entity_command(command, arg, state, display_header_func)
        
    elif command in ("/auto", "/research", "/agency"):
        from core.commands.orchestration import handle_orchestration_command
        handle_orchestration_command(command, arg, state, rag, display_header_func)
        
    else:
        console.print(f"Comando desconocido: {command}. Usa /help.")
