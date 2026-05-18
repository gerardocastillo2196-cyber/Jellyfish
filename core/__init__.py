# Jellyfish Core Module
# Exporta los componentes principales del framework.

from core.state import (
    JellyfishState, AGENCY_DIR, MODEL, OLLAMA_URL, DB_PATH, PLUGINS_DIR,
    PROVIDER, OPENAI_API_KEY, DEEPSEEK_API_KEY, OPENROUTER_API_KEY,
    RELEVANCE_THRESHOLD, EMBED_MODEL, get_term_width,
)
from core.rag_coder import CodeKnowledgeBase
from core.llm_engine import stream_ollama
from core.terminal import run_terminal_command
from core.plugin_manager import PluginManager
from core.ui import (
    display_header, interactive_picker, file_browser,
    print_panel, print_code, claude_style, console
)
from core.crud import handle_crud, handle_slash_command, detailed_interview

__all__ = [
    # State
    "JellyfishState", "AGENCY_DIR", "MODEL", "OLLAMA_URL", "DB_PATH", "PLUGINS_DIR",
    "PROVIDER", "OPENAI_API_KEY", "DEEPSEEK_API_KEY", "OPENROUTER_API_KEY",
    "RELEVANCE_THRESHOLD", "EMBED_MODEL", "get_term_width",
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
    "print_panel", "print_code", "claude_style", "console",
    # CRUD
    "handle_crud", "handle_slash_command", "detailed_interview",
]
