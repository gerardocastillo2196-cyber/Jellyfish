# Jellyfish Core Module
# Exporta los componentes principales del framework.

from core.state import (
    JellyfishState, AGENCY_DIR, MODEL, OLLAMA_URL, DB_PATH, PLUGINS_DIR,
    PROVIDER, OPENAI_API_KEY, DEEPSEEK_API_KEY, OPENROUTER_API_KEY,
    GEMINI_API_KEY, DASHSCOPE_API_KEY, KIMI_API_KEY, ZHIPU_API_KEY,
    RELEVANCE_THRESHOLD, EMBED_MODEL, get_term_width, get_term_height,
    PROVIDER_CONFIGS, normalize_provider, supported_provider_names,
)
from core.rag_coder import CodeKnowledgeBase
from core.llm_engine import stream_ollama
from core.terminal import run_terminal_command
from core.plugin_manager import PluginManager
from core.ui import (
    display_header, interactive_picker, file_browser,
    print_panel, print_code, claude_style, console, osc8_link,
    handle_exit_flow
)
from core.crud import handle_crud, handle_slash_command, detailed_interview
from core.tui import TUIEngine, TaskProgress, tui_engine
 
__all__ = [
    # State
    "JellyfishState", "AGENCY_DIR", "MODEL", "OLLAMA_URL", "DB_PATH", "PLUGINS_DIR",
    "PROVIDER", "OPENAI_API_KEY", "DEEPSEEK_API_KEY", "OPENROUTER_API_KEY",
    "GEMINI_API_KEY", "DASHSCOPE_API_KEY", "KIMI_API_KEY", "ZHIPU_API_KEY",
    "RELEVANCE_THRESHOLD", "EMBED_MODEL", "get_term_width", "get_term_height",
    "PROVIDER_CONFIGS", "normalize_provider", "supported_provider_names",
    # RAG
    "CodeKnowledgeBase",
    # LLM
    "stream_ollama",
    # Terminal
    "run_terminal_command",
    # Plugins
    "PluginManager",
    # UI
    "display_header", "interactive_picker", "file_browser",
    "print_panel", "print_code", "claude_style", "console", "osc8_link",
    "handle_exit_flow",
    # CRUD
    "handle_crud", "handle_slash_command", "detailed_interview",
    # TUI Engine
    "TUIEngine", "TaskProgress", "tui_engine",
]
