import os
import logging

logger = logging.getLogger("jellyfish.state")

AGENCY_DIR = os.path.expanduser("~/MisModelosIA/agencia")

# --- Bootstrap directories ---
for _folder in ["agents", "skills", "memory", "plugins"]:
    os.makedirs(os.path.join(AGENCY_DIR, _folder), exist_ok=True)

# System constants
DB_PATH = os.path.join(AGENCY_DIR, "code_vector_db")
PLUGINS_DIR = os.path.join(AGENCY_DIR, "plugins")

# Sprint 2.1 — Token budget para historial dinámico.
# Aproximación: 1 token ≈ 4 caracteres (inglés/código mixto).
# Se reserva el 80% del límite máximo del modelo para el historial activo.
# El 20% restante se reserva para el prompt del sistema y la respuesta del modelo.
_CHARS_PER_TOKEN = 4
_MODEL_TOKEN_LIMIT = int(os.getenv("JELLYFISH_CONTEXT_LIMIT", "8192"))
_HISTORY_CHAR_BUDGET = int(_MODEL_TOKEN_LIMIT * 0.80 * _CHARS_PER_TOKEN)


def get_term_width() -> int:
    """Obtiene el ancho de la terminal de forma segura.
    
    Retorna 120 como fallback si no se puede determinar (ej. entorno sin TTY).
    """
    try:
        return os.get_terminal_size().columns
    except (OSError, ValueError):
        return 120


def _safe_read(filepath: str) -> str:
    """Lee un archivo de texto de forma segura con encoding UTF-8."""
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except (OSError, IOError) as e:
        logger.warning("No se pudo leer %s: %s", filepath, e)
        return ""


class JellyfishState:
    """Estado central del sistema Jellyfish.
    
    Administra: agente activo, skills cargadas, archivos de contexto,
    historial de conversación, prompt del sistema y configuración de IA.
    """

    # Límite de caracteres totales para archivos de contexto (~25K tokens)
    MAX_CONTEXT_CHARS = 100_000
    # Límite de caracteres por archivo individual
    MAX_FILE_CHARS = 15_000

    def __init__(self):
        self.active_agent: str = "default"
        self.active_skills: set = set()
        self.context_files: set = set()
        self.history: list = []          # Charla activa (Sliding Window)
        self.static_history: list = []   # Core Context (system prompts)
        self.system_prompt: str = ""
        
        # Cargar configuración dinámica
        self.load_config()
        self.load_agent("default")

    def load_config(self) -> None:
        """Carga y recarga de forma caliente la configuración de proveedores desde .env."""
        try:
            from dotenv import load_dotenv
            load_dotenv(os.path.join(AGENCY_DIR, ".env"), override=True)
        except ImportError:
            pass

        self.provider = os.getenv("JELLYFISH_PROVIDER", "ollama").lower()
        self.model = os.getenv("JELLYFISH_MODEL", "qwen2.5-agent:latest")
        
        # Base URLs
        self.ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434/api/chat")
        self.openai_base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        self.deepseek_base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        self.openrouter_base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        
        # API Keys
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "")
        self.deepseek_api_key = os.getenv("DEEPSEEK_API_KEY", "")
        self.openrouter_api_key = os.getenv("OPENROUTER_API_KEY", "")
        
        # RAG Threshold and Embed Model
        self.relevance_threshold = float(os.getenv("JELLYFISH_RAG_THRESHOLD", "1.2"))
        self.embed_model = os.getenv("JELLYFISH_EMBED_MODEL", "nomic-embed-text")

        # Sprint 2.5 — Modelo híbrido: subagentes pueden usar un modelo/proveedor diferente
        # Si no se configura, los subagentes heredan el modelo/proveedor del Lead Agent.
        self.subagent_model = os.getenv("JELLYFISH_SUBAGENT_MODEL", "") or self.model
        self.subagent_provider = os.getenv("JELLYFISH_SUBAGENT_PROVIDER", "") or self.provider
        self.agency_dir = AGENCY_DIR

    def save_config(self, **kwargs) -> None:
        """Guarda configuraciones en el archivo .env y las recarga en memoria.
        
        Soporta argumentos:
            provider: nuevo proveedor
            model: nuevo modelo
            openai_key: clave de OpenAI
            deepseek_key: clave de DeepSeek
            openrouter_key: clave de OpenRouter
        """
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
            # Sprint 2.5 — Modelo/proveedor asimétrico para subagentes
            "subagent_model": "JELLYFISH_SUBAGENT_MODEL",
            "subagent_provider": "JELLYFISH_SUBAGENT_PROVIDER",
            "context_limit": "JELLYFISH_CONTEXT_LIMIT",
        }

        updated = set()
        new_lines = []
        for line in lines:
            stripped = line.strip()
            # Saltar líneas vacías o comentarios puros si coinciden con nuestras variables
            matched = False
            for key, env_var in config_map.items():
                if stripped.startswith(f"{env_var}="):
                    if key in kwargs and kwargs[key] is not None:
                        new_lines.append(f'{env_var}="{kwargs[key]}"\n')
                        updated.add(key)
                    else:
                        new_lines.append(line)
                    matched = True
                    break
            if not matched:
                new_lines.append(line)

        # Agregar variables que no estaban en el .env original
        for key, env_var in config_map.items():
            if key not in updated and key in kwargs and kwargs[key] is not None:
                new_lines.append(f'{env_var}="{kwargs[key]}"\n')

        # Si el archivo no existe, crearlo
        os.makedirs(AGENCY_DIR, exist_ok=True)
        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)

        # Sprint 4.3 — Proteger el archivo .env con permisos 600 tras escribir keys.
        # Esto evita que otros usuarios del sistema lean las API keys.
        try:
            os.chmod(env_path, 0o600)
        except OSError as e:
            logger.warning("No se pudo aplicar chmod 600 a .env: %s", e)

        # Recargar de inmediato en memoria
        self.load_config()

    def load_agent(self, agent_name: str) -> None:
        """Carga un perfil de agente y reinicia el historial de conversación."""
        self.active_agent = agent_name.lower().strip()
        template_file = os.path.join(AGENCY_DIR, "agents", "template.md")
        agent_file = os.path.join(AGENCY_DIR, "agents", f"{self.active_agent}.md")

        # 1. Cargar Protocolo Maestro (Herencia)
        self.system_prompt = ""
        template_content = _safe_read(template_file)
        if template_content:
            self.system_prompt = f"[PROTOCOLO MAESTRO]\n{template_content}\n\n"

        # 2. Cargar Perfil Específico
        if self.active_agent == "default":
            self.system_prompt += (
                "Eres Jellyfish, un asistente técnico avanzado. "
                "Tienes acceso a la terminal y puedes analizar resultados de comandos. "
                "Cuando el usuario te pida analizar código, utiliza el contexto RAG proporcionado."
            )
        else:
            agent_content = _safe_read(agent_file)
            if agent_content:
                self.system_prompt += f"[PERFIL ESPECÍFICO DE @{self.active_agent.upper()}]\n{agent_content}"
            else:
                logger.warning("Agente '%s' no encontrado, usando default.", self.active_agent)
                self.active_agent = "default"
                self.system_prompt += "Eres Jellyfish, un asistente técnico avanzado."

        self.history = []
        self.refresh_static_context()

    def refresh_static_context(self) -> None:
        """Reconstruye el contexto estático (system prompt + skills + docs).
        
        Los archivos de contexto se envuelven en etiquetas XML <context_file> para
        separación semántica limpia. Se aplica un límite de tamaño total para evitar
        desbordamiento de la ventana de contexto del modelo.
        """
        self.static_history = [{"role": "system", "content": self.system_prompt}]

        # Cargar Protocolo Maestro de Habilidades
        skill_template = os.path.join(AGENCY_DIR, "skills", "template.md")
        skill_template_content = _safe_read(skill_template)
        if skill_template_content:
            self.static_history.append({
                "role": "system",
                "content": f"[PROTOCOLO DE HABILIDADES]\n{skill_template_content}"
            })

        # Cargar habilidades activas
        for skill_path in self.active_skills:
            if "template.md" in skill_path:
                continue
            content = _safe_read(skill_path)
            if content:
                self.static_history.append({
                    "role": "system",
                    "content": f"[SKILL]\n{content}"
                })

        # Cargar archivos de contexto (con límite de tamaño)
        total_ctx_chars = 0
        for filepath in sorted(self.context_files):
            if total_ctx_chars >= self.MAX_CONTEXT_CHARS:
                logger.warning(
                    "Límite de contexto alcanzado (%d chars), omitiendo archivos restantes.",
                    self.MAX_CONTEXT_CHARS
                )
                break
            if os.path.isfile(filepath):
                content = _safe_read(filepath)
                if content:
                    # Truncar archivos individuales muy grandes
                    if len(content) > self.MAX_FILE_CHARS:
                        content = content[:self.MAX_FILE_CHARS] + "\n\n... [TRUNCADO]"
                    total_ctx_chars += len(content)
                    self.static_history.append({
                        "role": "system",
                        "content": (
                            f'<context_file path="{os.path.basename(filepath)}">\n'
                            f'{content}\n'
                            f'</context_file>'
                        )
                    })

    def get_full_history(self) -> list:
        """Retorna el contexto completo: estático + historial recortado por presupuesto de tokens.

        Sprint 2.1 — En lugar de un número fijo de mensajes, aplica un presupuesto de caracteres
        (proxy de tokens) calculado al 80% del límite del modelo configurado. Preserva los mensajes
        más recientes y descarta los más antiguos cuando se supera el presupuesto.
        """
        # Calcular el tamaño del contexto estático primero
        static_chars = sum(len(m.get("content", "")) for m in self.static_history)
        available_chars = max(_HISTORY_CHAR_BUDGET - static_chars, 0)

        # Seleccionar los mensajes más recientes que quepan en el presupuesto
        selected: list = []
        used_chars = 0
        for msg in reversed(self.history):
            msg_chars = len(msg.get("content", ""))
            if used_chars + msg_chars > available_chars:
                break
            selected.insert(0, msg)
            used_chars += msg_chars

        if len(selected) < len(self.history):
            dropped = len(self.history) - len(selected)
            logger.debug(
                "Token budget: %d mensajes descartados del historial (presupuesto: %d chars).",
                dropped, available_chars
            )

        return self.static_history + selected

    def reset_history(self) -> None:
        """Limpia el historial de conversación manteniendo el contexto estático."""
        self.history = []
        self.refresh_static_context()

    def add_context_file(self, filepath: str) -> None:
        """Agrega un archivo al contexto de forma segura."""
        abs_path = os.path.abspath(filepath)
        if os.path.exists(abs_path):
            self.context_files.add(abs_path)
        else:
            logger.warning("Archivo no encontrado: %s", abs_path)

    def add_context_directory(self, dirpath: str) -> None:
        """Agrega todos los archivos de texto de un directorio al contexto."""
        binary_ext = {'.pyc', '.png', '.jpg', '.jpeg', '.gif', '.exe', '.bin',
                      '.so', '.dll', '.o', '.ico', '.woff', '.woff2', '.ttf',
                      '.eot', '.mp3', '.mp4', '.zip', '.tar', '.gz'}
        ignore_dirs = {"venv", ".git", "__pycache__", "node_modules", "code_vector_db", "test_db"}

        for root, dirs, files in os.walk(dirpath):
            # Filtrar directorios in-place para no descender a ellos
            dirs[:] = [d for d in dirs if d not in ignore_dirs and not d.startswith(".")]
            for f in files:
                if not f.startswith(".") and os.path.splitext(f)[1].lower() not in binary_ext:
                    self.context_files.add(os.path.join(root, f))



# ---------------------------------------------------------------------------
# Sprint 4.1 — Constantes de compatibilidad sin instancia global _temp_state.
# En lugar de crear un JellyfishState() completo (que carga agente, skills y
# llama a carga de .env dos veces), leemos directamente desde el entorno.
# Los módulos que importan estas constantes las reciben como strings estáticos
# al momento de importación; el estado dinámico SIEMPRE viene de la instancia
# JellyfishState inyectada en cada función del core.
# ---------------------------------------------------------------------------
try:
    from dotenv import load_dotenv as _load_dotenv
    _load_dotenv(os.path.join(AGENCY_DIR, ".env"), override=False)
except ImportError:
    pass

PROVIDER            = os.getenv("JELLYFISH_PROVIDER", "ollama")
MODEL               = os.getenv("JELLYFISH_MODEL", "qwen2.5-agent:latest")
OLLAMA_URL          = os.getenv("OLLAMA_URL", "http://localhost:11434/api/chat")
OPENAI_BASE_URL     = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
DEEPSEEK_BASE_URL   = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENAI_API_KEY      = os.getenv("OPENAI_API_KEY", "")
DEEPSEEK_API_KEY    = os.getenv("DEEPSEEK_API_KEY", "")
OPENROUTER_API_KEY  = os.getenv("OPENROUTER_API_KEY", "")
RELEVANCE_THRESHOLD = float(os.getenv("JELLYFISH_RAG_THRESHOLD", "1.2"))
EMBED_MODEL         = os.getenv("JELLYFISH_EMBED_MODEL", "nomic-embed-text")

