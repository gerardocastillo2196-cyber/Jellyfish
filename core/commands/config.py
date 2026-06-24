import os
from rich.panel import Panel
from rich.table import Table
from prompt_toolkit import PromptSession
from core.ui import console
from core.config import (
    PROVIDER_CONFIGS, PROVIDER_ALIASES, supported_provider_names
)
from core.ui import interactive_picker

def handle_config_command(command: str, arg: str, state, display_header_func) -> None:
    if command == "/config":
        _handle_config(arg, state, display_header_func)
    elif command == "/model":
        _handle_model_picker(state, display_header_func)
    elif command == "/provider":
        _show_provider_info(state)

def _show_provider_info(state):
    """Muestra información del proveedor de IA activo."""
    provider_meta = PROVIDER_CONFIGS.get(state.provider, {})
    key_status = "No requiere API key" if state.provider == "ollama" else _mask_key(state.api_keys.get(state.provider, ""))
    base_url = state.base_urls.get(state.provider, state.ollama_base_url)
    console.print(Panel(
        f"[bold]Proveedor:[/bold] {state.provider.upper()} — {provider_meta.get('label', '')}\n"
        f"[bold]Modelo:[/bold] {state.model}\n"
        f"[bold]Tipo:[/bold] {'Nube / API' if state.provider != 'ollama' else 'Local (Ollama)'}\n"
        f"[bold]API Key:[/bold] {key_status}\n"
        f"[bold]Endpoint:[/bold] {base_url}",
        title="Proveedor de IA",
        border_style="dim white"
    ))
    input("\nPresiona Enter para continuar...")

def _mask_key(key: str) -> str:
    """Enmascara una clave API para mostrarla con seguridad."""
    if not key:
        return "No configurada"
    if len(key) <= 8:
        return "****"
    return f"{key[:4]}...{key[-4:]}"

def _show_current_config(state):
    """Muestra la configuración actual de forma estilizada."""
    table = Table(title="CONFIGURACION JELLYFISH", border_style="dim white", show_lines=False)
    table.add_column("Activo", justify="center", width=7)
    table.add_column("Proveedor", style="bold")
    table.add_column("API Key")
    table.add_column("Base URL", overflow="fold")

    for name, meta in PROVIDER_CONFIGS.items():
        active = "*" if name == state.provider else ""
        key = "local" if name == "ollama" else _mask_key(state.api_keys.get(name, ""))
        base_url = state.base_urls.get(name, "")
        table.add_row(active, f"{name} — {meta['label']}", key, base_url or "(configurar)")

    console.print(table)
    console.print(Panel(
        f"[bold]Modelo activo:[/bold] {state.model}\n"
        f"[bold]Subagentes:[/bold] {state.subagent_provider}:{state.subagent_model}\n"
        f"[bold]RAG:[/bold] embeddings={state.embed_model} · umbral={state.relevance_threshold}",
        title="Runtime",
        border_style="dim white",
    ))

def _resolve_provider_name(value: str) -> str:
    """Resuelve alias humanos a proveedores soportados."""
    key = (value or "").strip().lower()
    key = PROVIDER_ALIASES.get(key, key)
    return key if key in PROVIDER_CONFIGS else ""

def _provider_menu_options() -> list[str]:
    return [f"{name} — {PROVIDER_CONFIGS[name]['label']}" for name in supported_provider_names()]

def _provider_from_menu_option(option: str) -> str:
    return option.split(" ", 1)[0].strip() if option else ""

def _save_provider_key(state, provider: str, value: str) -> bool:
    if provider == "ollama":
        console.print("Ollama local no requiere API key.")
        return False
    state.save_config(**{f"{provider}_key": value})
    return True

def _save_provider_base_url(state, provider: str, value: str) -> bool:
    if provider not in PROVIDER_CONFIGS:
        return False
    state.save_config(**{f"{provider}_base_url": value})
    return True

def _handle_config(arg: str, state, display_header_func):
    """Manejador del comando /config."""
    raw = arg.strip()
    subcmd = raw.split(maxsplit=1)[0].lower() if raw else ""

    if not raw or subcmd == "show":
        _show_current_config(state)
        input("\nPresiona Enter para continuar...")
        return

    if subcmd == "providers":
        _show_current_config(state)
        return

    if subcmd == "provider":
        parts = raw.split(maxsplit=1)
        prov = _resolve_provider_name(parts[1]) if len(parts) > 1 else ""
        if not prov:
            console.print(
                "Proveedor inválido. Opciones: "
                + ", ".join(supported_provider_names())
            )
        else:
            state.save_config(provider=prov)
            console.print(f"✓ Proveedor cambiado a: {prov}")
            display_header_func()
        return

    elif subcmd == "model":
        parts = raw.split(" ", 1)
        mod = parts[1].strip() if len(parts) > 1 else ""
        if not mod:
            console.print("Por favor especifica el nombre del modelo.")
        else:
            state.save_config(model=mod)
            console.print(f"✓ Modelo cambiado a: {mod}")
            display_header_func()
        return

    elif subcmd == "key":
        parts = raw.split(maxsplit=2)
        if len(parts) < 3:
            console.print(
                "Uso: /config key <proveedor> <valor_clave>\n"
                f"[dim]Proveedores: {', '.join(supported_provider_names())}[/dim]"
            )
            return
        target_prov = _resolve_provider_name(parts[1])
        key_val = parts[2].strip()

        if not target_prov:
            console.print("Proveedor de key desconocido.")
            return
        if _save_provider_key(state, target_prov, key_val):
            console.print(f"✓ API Key de {target_prov} actualizada en .env.")
        return

    elif subcmd in ("endpoint", "base_url", "url"):
        parts = raw.split(maxsplit=2)
        if len(parts) < 3:
            console.print("Uso: /config endpoint <proveedor> <base_url>")
            return
        target_prov = _resolve_provider_name(parts[1])
        base_url = parts[2].strip()
        if not target_prov:
            console.print("Proveedor desconocido.")
            return
        _save_provider_base_url(state, target_prov, base_url)
        console.print(f"✓ Endpoint de {target_prov} actualizado.")
        return

    elif subcmd == "subagent_model":
        parts = raw.split(" ", 1)
        mod = parts[1].strip() if len(parts) > 1 else ""
        if not mod:
            console.print("Uso: /config subagent_model <modelo>")
        else:
            state.save_config(subagent_model=mod)
            console.print(f"✓ Modelo de subagentes: {mod}")
        return

    elif subcmd == "subagent_provider":
        parts = raw.split(maxsplit=1)
        prov = _resolve_provider_name(parts[1]) if len(parts) > 1 else ""
        if not prov:
            console.print("Uso: /config subagent_provider <proveedor>")
        else:
            state.save_config(subagent_provider=prov)
            console.print(f"✓ Proveedor de subagentes: {prov}")
        return

    elif subcmd == "context_limit":
        parts = raw.split(maxsplit=1)
        value = parts[1].strip() if len(parts) > 1 else ""
        try:
            tokens = int(value)
            if tokens < 1024:
                raise ValueError
        except ValueError:
            console.print("Uso: /config context_limit <tokens>, mínimo 1024")
            return
        state.save_config(context_limit=str(tokens))
        console.print(f"✓ Límite de contexto configurado: {tokens} tokens")
        return

    if subcmd in ("interactive", "menu", "wizard"):
        while True:
            action = interactive_picker(
                "CONFIGURACIÓN JELLYFISH",
                [
                    "Ver Configuración",
                    "Cambiar Proveedor",
                    "Cambiar Modelo",
                    "Configurar API Key",
                    "Configurar Endpoint",
                    "Configurar Subagentes",
                ]
            )
            if not action:
                break

            session = PromptSession()

            if action == "Ver Configuración":
                _show_current_config(state)
                input("\nPresiona Enter para continuar...")

            elif action == "Cambiar Proveedor":
                selected = interactive_picker("SELECCIONAR PROVEEDOR", _provider_menu_options())
                prov = _provider_from_menu_option(selected)
                if prov:
                    state.save_config(provider=prov)
                    console.print(f"✓ Proveedor cambiado a: {prov}")
                    input("\nPresiona Enter para continuar...")

            elif action == "Cambiar Modelo":
                mod = session.prompt("Escribe el nombre del modelo: ", default=state.model).strip()
                if mod:
                    state.save_config(model=mod)
                    console.print(f"✓ Modelo cambiado a: {mod}")
                    input("\nPresiona Enter para continuar...")

            elif action == "Configurar API Key":
                selected = interactive_picker("SELECCIONAR PROVEEDOR", _provider_menu_options())
                prov = _provider_from_menu_option(selected)
                if prov:
                    current = state.api_keys.get(prov, "")
                    val = session.prompt(f"API Key para {prov}: ", default=current).strip()
                    if _save_provider_key(state, prov, val):
                        console.print("✓ API Key guardada exitosamente en .env.")
                    input("\nPresiona Enter para continuar...")

            elif action == "Configurar Endpoint":
                selected = interactive_picker("SELECCIONAR PROVEEDOR", _provider_menu_options())
                prov = _provider_from_menu_option(selected)
                if prov:
                    current = state.base_urls.get(prov, "")
                    val = session.prompt(f"Base URL para {prov}: ", default=current).strip()
                    if val:
                        _save_provider_base_url(state, prov, val)
                        console.print("✓ Endpoint guardado exitosamente en .env.")
                    input("\nPresiona Enter para continuar...")

            elif action == "Configurar Subagentes":
                selected = interactive_picker("PROVEEDOR SUBAGENTES", _provider_menu_options())
                prov = _provider_from_menu_option(selected)
                if prov:
                    mod = session.prompt("Modelo de subagentes: ", default=state.subagent_model).strip()
                    state.save_config(subagent_provider=prov, subagent_model=mod or state.subagent_model)
                    console.print("✓ Configuración de subagentes actualizada.")
                    input("\nPresiona Enter para continuar...")

        return

    console.print("Subcomando /config desconocido. Usa /config show o /config menu.")

def _auto_detect_provider(api_key: str, base_url: str) -> str:
    """Detecta el proveedor basándose en el prefijo de la API Key o el dominio del Base URL."""
    api_key_clean = api_key.strip().lower()
    base_url_clean = base_url.strip().lower()

    # 1. Detectar por prefijo de API Key
    if api_key_clean.startswith("sk-or-"):
        return "openrouter"
    if api_key_clean.startswith("sk-proj-"):
        return "openai"

    # 2. Detectar por dominio del Base URL
    if "deepseek.com" in base_url_clean:
        return "deepseek"
    if "openrouter.ai" in base_url_clean:
        return "openrouter"
    if "api.openai.com" in base_url_clean:
        return "openai"
    if "dashscope.aliyuncs.com" in base_url_clean or "qwen" in base_url_clean:
        return "qwen"
    if "api.moonshot.cn" in base_url_clean or "kimi" in base_url_clean:
        return "kimi"
    if "open.bigmodel.cn" in base_url_clean or "zhipu" in base_url_clean:
        return "zhipu"
    if "generativelanguage.googleapis.com" in base_url_clean or "gemini" in base_url_clean:
        return "gemini"
    if "api.anthropic.com" in base_url_clean or "claude" in base_url_clean:
        return "claude"

    return "custom"


def _fetch_api_models(base_url: str, api_key: str) -> list[str]:
    """Obtiene la lista de modelos de un endpoint compatible con OpenAI o de la API de Gemini."""
    import httpx
    models = []
    if not base_url:
        return models
    try:
        base_url_lower = base_url.lower()
        if "generativelanguage.googleapis.com" in base_url_lower or "gemini" in base_url_lower:
            # Endpoint oficial de Gemini para listar modelos
            url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
            with httpx.Client(timeout=3.0) as client:
                resp = client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, dict) and "models" in data:
                        for item in data["models"]:
                            if isinstance(item, dict) and "name" in item:
                                name = item["name"]
                                # Google API devuelve "models/gemini-..."
                                if name.startswith("models/"):
                                    name = name[len("models/"):]
                                models.append(name)
        else:
            url = f"{base_url.rstrip('/')}/models"
            headers = {"Content-Type": "application/json"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            with httpx.Client(timeout=3.0) as client:
                resp = client.get(url, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, dict) and "data" in data:
                        for item in data["data"]:
                            if isinstance(item, dict) and "id" in item:
                                models.append(item["id"])
    except Exception:
        pass
    return sorted(list(set(models)))


def _handle_model_picker(state, display_header_func) -> None:
    """Permite seleccionar de forma interactiva el proveedor y el modelo, con autodetect de API/Endpoint."""
    import httpx
    from prompt_toolkit import PromptSession
    
    provider_options = [
        "Ollama (Local)",
        "Gemini (Google)",
        "Claude (Anthropic)",
        "[➕ Configurar API Key / Endpoint de cualquier otra IA (DeepSeek, OpenAI, etc.)]",
    ]
    
    selected_prov = interactive_picker("SELECCIONAR PROVEEDOR", provider_options)
    if not selected_prov:
        return
        
    prov_map = {
        "Ollama (Local)": "ollama",
        "Gemini (Google)": "gemini",
        "Claude (Anthropic)": "claude",
    }
    
    session = PromptSession()
    target_prov = None
    api_key = None
    base_url = None
    
    if selected_prov == "[➕ Configurar API Key / Endpoint de cualquier otra IA (DeepSeek, OpenAI, etc.)]":
        console.print("\n[bold cyan]Configuración Directa de API Key / Endpoint[/bold cyan]")
        api_key = session.prompt("Ingresa tu API Key (ej. sk-...): ").strip()
        base_url = session.prompt("Ingresa la Base URL / Endpoint (ej. https://api.deepseek.com/v1): ").strip()
        
        target_prov = _auto_detect_provider(api_key, base_url)
        console.print(f"\n[green]✓ Proveedor detectado:[/green] {target_prov.upper()}")
        
        if target_prov == "custom":
            choose_prov = session.prompt(
                "No se pudo autodetectar. Elige el proveedor (ollama, openai, deepseek, openrouter, gemini, qwen, kimi, zhipu, custom, claude) [custom]: "
            ).strip().lower()
            if choose_prov in PROVIDER_CONFIGS:
                target_prov = choose_prov
            else:
                target_prov = "custom"
    else:
        target_prov = prov_map[selected_prov]
        
    # Verificar y solicitar API Key si no está configurada para proveedores cloud
    if target_prov != "ollama":
        current_key = state.api_keys.get(target_prov, "")
        if not current_key and not api_key:
            console.print(f"\n[yellow]No tienes una API Key configurada para {target_prov.upper()}.[/yellow]")
            api_key = session.prompt(f"Ingresa tu API Key para {target_prov.upper()}: ").strip()
            
        current_url = state.base_urls.get(target_prov, "")
        if not current_url and not base_url:
            meta = PROVIDER_CONFIGS.get(target_prov, {})
            default_url = meta.get("default_base_url", "")
            base_url = session.prompt(f"Base URL [default: {default_url}]: ").strip() or default_url

    # Guardar credenciales de forma preliminar para poder realizar el listado de modelos
    config_to_save = {"provider": target_prov}
    if api_key:
        config_to_save[f"{target_prov}_key"] = api_key
        state.api_keys[target_prov] = api_key
    if base_url:
        config_to_save[f"{target_prov}_base_url"] = base_url
        state.base_urls[target_prov] = base_url
    
    state.save_config(**config_to_save)

    # Determinar el base_url y api_key finales para el fetch de modelos
    final_url = base_url or state.base_urls.get(target_prov, "")
    final_key = api_key or state.api_keys.get(target_prov, "")

    models = []
    
    # Intentar obtener modelos dinámicamente si es compatible con OpenAI
    if target_prov != "ollama" and target_prov != "claude":
        console.print("[dim]Intentando obtener listado de modelos desde el endpoint...[/dim]")
        models = _fetch_api_models(final_url, final_key)
        if models:
            console.print(f"[green]✓ Listados {len(models)} modelos disponibles en el endpoint.[/green]")
    
    # Caer a presets si falla o es ollama/claude/gemini
    if not models:
        if target_prov == "ollama":
            from urllib.parse import urlparse
            parsed = urlparse(final_url or "http://localhost:11434")
            tags_url = f"{parsed.scheme}://{parsed.netloc}/api/tags" if parsed.netloc else "http://localhost:11434/api/tags"
            try:
                with httpx.Client(timeout=2.0) as client:
                    resp = client.get(tags_url)
                    if resp.status_code == 200:
                        data = resp.json()
                        models = [m["name"] for m in data.get("models", [])]
            except Exception:
                pass
            if not models:
                models = ["llama3", "mistral", "codellama", "qwen2.5-coder"]
            models.insert(0, "[➕ Descargar nuevo modelo de Ollama]")
            
        elif target_prov == "gemini":
            models = [
                "gemini-3.5-flash-medium",
                "gemini-3.5-flash-high",
                "gemini-3.5-flash-low",
                "gemini-3.1-pro-low",
                "gemini-3.1-pro-high",
            ]
        elif target_prov == "claude":
            models = [
                "claude-3-5-sonnet-20241022",
                "claude-3-5-haiku-20241022",
                "claude-3-opus-20240229",
            ]
        elif target_prov == "openai":
            models = ["gpt-4o", "gpt-4o-mini", "o1-mini", "o1-preview"]
        elif target_prov == "deepseek":
            models = ["deepseek-chat", "deepseek-coder"]
        elif target_prov == "openrouter":
            models = ["meta-llama/llama-3.1-8b-instruct:free", "google/gemini-flash-1.5"]
        elif target_prov == "qwen":
            models = ["qwen-turbo", "qwen-plus", "qwen-max"]
        elif target_prov == "kimi":
            models = ["moonshot-v1-8k", "moonshot-v1-32k"]
        elif target_prov == "zhipu":
            models = ["glm-4", "glm-4-flash"]
        else:
            models = []
            
    # Añadir siempre la opción de ingresar el nombre de forma manual
    models.append("[✍ Ingresar nombre de modelo personalizado]")
    
    selected_model = interactive_picker(f"SELECCIONAR MODELO ({target_prov.upper()})", models)
    if not selected_model:
        return
        
    if selected_model == "[➕ Descargar nuevo modelo de Ollama]":
        model_to_pull = session.prompt("Nombre del modelo a descargar (ej. llama3, qwen2.5-coder:7b): ").strip()
        if not model_to_pull:
            return
        console.print(f"📥 Descargando modelo '{model_to_pull}' mediante Ollama... (esto puede tardar varios minutos)")
        import subprocess
        try:
            subprocess.run(["ollama", "pull", model_to_pull], check=True)
            selected_model = model_to_pull
            console.print(f"✓ Modelo '{model_to_pull}' descargado exitosamente.")
        except Exception as e:
            console.print(f"❌ Error al descargar el modelo: {e}")
            input("\nPresiona Enter para volver...")
            return
            
    elif selected_model == "[✍ Ingresar nombre de modelo personalizado]":
        custom_model = session.prompt("Escribe el nombre del modelo a utilizar: ").strip()
        if not custom_model:
            return
        selected_model = custom_model

    state.save_config(provider=target_prov, model=selected_model)
    console.print(f"✓ Proveedor cambiado a: {target_prov}")
    console.print(f"✓ Modelo cambiado a: {selected_model}")
    
    display_header_func()
    input("\nPresiona Enter para continuar...")
