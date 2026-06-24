import os
import re
import logging
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger("jellyfish.config")

# Resolución dinámica del directorio base de la agencia.
# Prioridad: 1) variable de entorno, 2) directorio raíz del repositorio Jellyfish.
# Esto elimina la dependencia de rutas absolutas del usuario (~/ hardcodeado).
_REPO_ROOT = str(Path(__file__).resolve().parent.parent)
AGENCY_DIR = os.getenv("JELLYFISH_AGENCY_DIR", _REPO_ROOT)

PROVIDER_CONFIGS = {
    "ollama": {
        "label": "Ollama local",
        "api_key_env": None,
        "base_url_env": "OLLAMA_URL",
        "default_base_url": "http://localhost:11434/api/chat",
        "openai_compatible": False,
    },
    "openai": {
        "label": "OpenAI",
        "api_key_env": "OPENAI_API_KEY",
        "base_url_env": "OPENAI_BASE_URL",
        "default_base_url": "https://api.openai.com/v1",
        "openai_compatible": True,
    },
    "deepseek": {
        "label": "DeepSeek",
        "api_key_env": "DEEPSEEK_API_KEY",
        "base_url_env": "DEEPSEEK_BASE_URL",
        "default_base_url": "https://api.deepseek.com",
        "openai_compatible": True,
    },
    "openrouter": {
        "label": "OpenRouter",
        "api_key_env": "OPENROUTER_API_KEY",
        "base_url_env": "OPENROUTER_BASE_URL",
        "default_base_url": "https://openrouter.ai/api/v1",
        "openai_compatible": True,
    },
    "gemini": {
        "label": "Google Gemini",
        "api_key_env": "GEMINI_API_KEY",
        "base_url_env": "GEMINI_BASE_URL",
        "default_base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "openai_compatible": True,
    },
    "qwen": {
        "label": "Qwen / Alibaba DashScope",
        "api_key_env": "DASHSCOPE_API_KEY",
        "api_key_aliases": ("QWEN_API_KEY",),
        "base_url_env": "DASHSCOPE_BASE_URL",
        "base_url_aliases": ("QWEN_BASE_URL",),
        "default_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "openai_compatible": True,
    },
    "kimi": {
        "label": "Kimi / Moonshot AI",
        "api_key_env": "KIMI_API_KEY",
        "api_key_aliases": ("MOONSHOT_API_KEY",),
        "base_url_env": "KIMI_BASE_URL",
        "base_url_aliases": ("MOONSHOT_BASE_URL",),
        "default_base_url": "https://api.moonshot.ai/v1",
        "openai_compatible": True,
    },
    "zhipu": {
        "label": "Zhipu / GLM",
        "api_key_env": "ZHIPU_API_KEY",
        "base_url_env": "ZHIPU_BASE_URL",
        "default_base_url": "https://open.bigmodel.cn/api/paas/v4",
        "openai_compatible": True,
    },
    "custom": {
        "label": "OpenAI-compatible custom",
        "api_key_env": "CUSTOM_API_KEY",
        "base_url_env": "CUSTOM_BASE_URL",
        "default_base_url": "",
        "openai_compatible": True,
    },
    "claude": {
        "label": "Claude (Anthropic)",
        "api_key_env": "ANTHROPIC_API_KEY",
        "api_key_aliases": ("CLAUDE_API_KEY",),
        "base_url_env": "ANTHROPIC_BASE_URL",
        "base_url_aliases": ("CLAUDE_BASE_URL",),
        "default_base_url": "https://api.anthropic.com/v1",
        "openai_compatible": False,
    },
}

PROVIDER_ALIASES = {
    "local": "ollama",
    "google": "gemini",
    "dashscope": "qwen",
    "aliyun": "qwen",
    "alibaba": "qwen",
    "moonshot": "kimi",
    "kimi-k2": "kimi",
    "glm": "zhipu",
    "bigmodel": "zhipu",
    "zai": "zhipu",
}

def normalize_provider(provider: str) -> str:
    """Normaliza alias humanos al identificador interno del proveedor."""
    key = (provider or "ollama").strip().lower()
    key = PROVIDER_ALIASES.get(key, key)
    return key if key in PROVIDER_CONFIGS else "ollama"

def supported_provider_names() -> list[str]:
    """Lista estable de proveedores seleccionables desde /config."""
    return list(PROVIDER_CONFIGS.keys())

def _env_first(primary: str | None, aliases=(), default: str = "") -> str:
    """Lee la primera variable de entorno disponible."""
    names = [primary] if primary else []
    names.extend(aliases or [])
    for name in names:
        value = os.getenv(name, "")
        if value:
            return value
    return default

def _normalize_base_url(value: str, provider: str) -> str:
    value = (value or "").strip()
    if provider == "ollama":
        return value
    return value.rstrip("/")

def _format_env_line(env_var: str, value: str) -> str:
    """Serializa una variable .env sin permitir saltos de linea accidentales."""
    safe = str(value).replace("\n", "").replace("\r", "")
    safe = safe.replace("\\", "\\\\").replace('"', '\\"')
    return f'{env_var}="{safe}"\n'

def _xml_attr(value: str) -> str:
    """Escapa atributos para los envoltorios de contexto."""
    return str(value).replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")

def estimate_tokens(text: str) -> int:
    """Heurística avanzada para estimación de tokens en código y texto en español.
    
    Cuenta caracteres normales y otorga un factor especial a los símbolos
    de programación (puntuación/operadores) que suelen separarse en tokens individuales.
    """
    if not text:
        return 0
    special_chars = len(re.findall(r"[{}()\[\];.,:=+\-*/<>!&|%?~#@]", text))
    normal_chars = len(text) - special_chars
    est = int((normal_chars / 4.2) + (special_chars * 0.75))
    return max(1, est)

def load_config_from_env(state) -> None:
    """Carga y recarga de forma caliente la configuración de proveedores desde .env."""
    try:
        load_dotenv(os.path.join(AGENCY_DIR, ".env"), override=True)
    except Exception:
        pass

    state.provider = normalize_provider(os.getenv("JELLYFISH_PROVIDER", "ollama"))
    state.model = os.getenv("JELLYFISH_MODEL", "qwen2.5-agent:latest")
    # No auto-upgrading to non-existent models.

    state.provider_configs = PROVIDER_CONFIGS
    state.api_keys = {}
    state.base_urls = {}
    for name, meta in PROVIDER_CONFIGS.items():
        base_url = _env_first(
            meta.get("base_url_env"),
            meta.get("base_url_aliases", ()),
            meta.get("default_base_url", ""),
        )
        base_url = _normalize_base_url(base_url, name)
        api_key = _env_first(
            meta.get("api_key_env"),
            meta.get("api_key_aliases", ()),
            "",
        )

        state.base_urls[name] = base_url
        state.api_keys[name] = api_key
        setattr(state, f"{name}_base_url", base_url)
        setattr(state, f"{name}_api_key", api_key)

    state.relevance_threshold = float(os.getenv("JELLYFISH_RAG_THRESHOLD", "1.2"))
    state.show_guides = os.getenv("JELLYFISH_SHOW_GUIDES", "1") == "1"
    state.embed_model = os.getenv("JELLYFISH_EMBED_MODEL", "nomic-embed-text")

    state.subagent_model = os.getenv("JELLYFISH_SUBAGENT_MODEL", "") or state.model
    raw_subagent_provider = os.getenv("JELLYFISH_SUBAGENT_PROVIDER", "")
    state.subagent_provider = (
        normalize_provider(raw_subagent_provider)
        if raw_subagent_provider
        else state.provider
    )
    state.agency_dir = AGENCY_DIR

    old_project = getattr(state, "active_project", "")
    state.active_project = os.getenv("JELLYFISH_ACTIVE_PROJECT", "")
    state.project_methodology = os.getenv("JELLYFISH_PROJECT_METHODOLOGY", "scrum").lower()
    if old_project != state.active_project:
        # Limpiar archivos del proyecto anterior del contexto en memoria
        if old_project and hasattr(state, "context_files"):
            old_project_abs = os.path.abspath(old_project)
            files_to_discard = [
                fp for fp in state.context_files
                if os.path.abspath(fp).startswith(old_project_abs + os.sep) or os.path.abspath(fp) == old_project_abs
            ]
            for fp in files_to_discard:
                state.context_files.discard(fp)

        state._update_project_lock(old_project)

        # Cargar archivos de inteligencia/metodología del nuevo proyecto activo
        if hasattr(state, "_load_project_files_on_boot"):
            state._load_project_files_on_boot()

        # Cargar historial de conversación del nuevo proyecto activo
        if hasattr(state, "load_history_from_project"):
            state.load_history_from_project()

        # Actualizar base de datos RAG correspondiente al nuevo proyecto
        if hasattr(state, "rag") and state.rag:
            state.rag.set_active_project(state.active_project)

def save_config_to_env(state, **kwargs) -> None:
    """Guarda configuraciones en el archivo .env y las recarga en memoria."""
    env_path = os.path.join(AGENCY_DIR, ".env")
    lines = []
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

    config_map = {
        "provider": "JELLYFISH_PROVIDER",
        "model": "JELLYFISH_MODEL",
        "openai_key": "OPENAI_API_KEY",
        "deepseek_key": "DEEPSEEK_API_KEY",
        "openrouter_key": "OPENROUTER_API_KEY",
        "gemini_key": "GEMINI_API_KEY",
        "qwen_key": "DASHSCOPE_API_KEY",
        "kimi_key": "KIMI_API_KEY",
        "zhipu_key": "ZHIPU_API_KEY",
        "custom_key": "CUSTOM_API_KEY",
        "claude_key": "ANTHROPIC_API_KEY",
        "ollama_base_url": "OLLAMA_URL",
        "openai_base_url": "OPENAI_BASE_URL",
        "deepseek_base_url": "DEEPSEEK_BASE_URL",
        "openrouter_base_url": "OPENROUTER_BASE_URL",
        "gemini_base_url": "GEMINI_BASE_URL",
        "qwen_base_url": "DASHSCOPE_BASE_URL",
        "kimi_base_url": "KIMI_BASE_URL",
        "zhipu_base_url": "ZHIPU_BASE_URL",
        "custom_base_url": "CUSTOM_BASE_URL",
        "claude_base_url": "ANTHROPIC_BASE_URL",
        "subagent_model": "JELLYFISH_SUBAGENT_MODEL",
        "subagent_provider": "JELLYFISH_SUBAGENT_PROVIDER",
        "context_limit": "JELLYFISH_CONTEXT_LIMIT",
        "active_project": "JELLYFISH_ACTIVE_PROJECT",
        "project_methodology": "JELLYFISH_PROJECT_METHODOLOGY",
        "show_guides": "JELLYFISH_SHOW_GUIDES",
    }

    updated = set()
    new_lines = []
    for line in lines:
        stripped = line.strip()
        matched = False
        for key, env_var in config_map.items():
            if stripped.startswith(f"{env_var}="):
                if key in kwargs and kwargs[key] is not None:
                    value = normalize_provider(kwargs[key]) if key.endswith("provider") else kwargs[key]
                    new_lines.append(_format_env_line(env_var, value))
                    updated.add(key)
                else:
                    new_lines.append(line)
                matched = True
                break
        if not matched:
            new_lines.append(line)

    if new_lines and not new_lines[-1].endswith("\n"):
        new_lines[-1] = new_lines[-1] + "\n"

    for key, env_var in config_map.items():
        if key not in updated and key in kwargs and kwargs[key] is not None:
            value = normalize_provider(kwargs[key]) if key.endswith("provider") else kwargs[key]
            new_lines.append(_format_env_line(env_var, value))

    os.makedirs(AGENCY_DIR, exist_ok=True)
    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

    try:
        os.chmod(env_path, 0o600)
    except OSError as e:
        logger.warning("No se pudo aplicar chmod 600 a .env: %s", e)

    state.load_config()

# Carga estática inicial al importar config
try:
    load_dotenv(os.path.join(AGENCY_DIR, ".env"), override=False)
except Exception:
    pass

PROVIDER            = normalize_provider(os.getenv("JELLYFISH_PROVIDER", "ollama"))
MODEL               = os.getenv("JELLYFISH_MODEL", "qwen2.5-agent:latest")
OLLAMA_URL          = os.getenv("OLLAMA_URL", PROVIDER_CONFIGS["ollama"]["default_base_url"])
OPENAI_BASE_URL     = os.getenv("OPENAI_BASE_URL", PROVIDER_CONFIGS["openai"]["default_base_url"])
DEEPSEEK_BASE_URL   = os.getenv("DEEPSEEK_BASE_URL", PROVIDER_CONFIGS["deepseek"]["default_base_url"])
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", PROVIDER_CONFIGS["openrouter"]["default_base_url"])
GEMINI_BASE_URL     = os.getenv("GEMINI_BASE_URL", PROVIDER_CONFIGS["gemini"]["default_base_url"])
DASHSCOPE_BASE_URL  = os.getenv("DASHSCOPE_BASE_URL", PROVIDER_CONFIGS["qwen"]["default_base_url"])
KIMI_BASE_URL       = os.getenv("KIMI_BASE_URL", PROVIDER_CONFIGS["kimi"]["default_base_url"])
ZHIPU_BASE_URL      = os.getenv("ZHIPU_BASE_URL", PROVIDER_CONFIGS["zhipu"]["default_base_url"])
CUSTOM_BASE_URL     = os.getenv("CUSTOM_BASE_URL", PROVIDER_CONFIGS["custom"]["default_base_url"])
CLAUDE_BASE_URL     = os.getenv("ANTHROPIC_BASE_URL", os.getenv("CLAUDE_BASE_URL", PROVIDER_CONFIGS["claude"]["default_base_url"]))
OPENAI_API_KEY      = os.getenv("OPENAI_API_KEY", "")
DEEPSEEK_API_KEY    = os.getenv("DEEPSEEK_API_KEY", "")
OPENROUTER_API_KEY  = os.getenv("OPENROUTER_API_KEY", "")
GEMINI_API_KEY      = os.getenv("GEMINI_API_KEY", "")
DASHSCOPE_API_KEY   = os.getenv("DASHSCOPE_API_KEY", os.getenv("QWEN_API_KEY", ""))
KIMI_API_KEY        = os.getenv("KIMI_API_KEY", os.getenv("MOONSHOT_API_KEY", ""))
ZHIPU_API_KEY       = os.getenv("ZHIPU_API_KEY", "")
CUSTOM_API_KEY      = os.getenv("CUSTOM_API_KEY", "")
ANTHROPIC_API_KEY   = os.getenv("ANTHROPIC_API_KEY", os.getenv("CLAUDE_API_KEY", ""))
RELEVANCE_THRESHOLD = float(os.getenv("JELLYFISH_RAG_THRESHOLD", "1.2"))
EMBED_MODEL         = os.getenv("JELLYFISH_EMBED_MODEL", "nomic-embed-text")
ACTIVE_PROJECT      = os.getenv("JELLYFISH_ACTIVE_PROJECT", "")

# Rutas derivadas del AGENCY_DIR — single source of truth
DB_PATH    = os.path.join(AGENCY_DIR, "code_vector_db")
PLUGINS_DIR = os.path.join(AGENCY_DIR, "plugins")
