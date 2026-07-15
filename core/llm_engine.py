import os
import time
import json
import re
import logging
import threading
import httpx
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.live import Live
from rich.prompt import Confirm

from core.terminal import run_terminal_command, is_readonly_command
from core.state import normalize_provider, estimate_tokens
import core.state as _state_module

# Timeout en segundos para la confirmación interactiva del Action Loop (Sprint 1.4)
_CONFIRM_TIMEOUT_S = 60

logger = logging.getLogger("jellyfish.llm")
console = Console()

# Máximo de iteraciones Auto-ReAct (evitar bucles infinitos)
MAX_REACT_LOOPS = 3

# Auditoría — Caché L1 por turno para evitar llamadas LLM duplicadas.
# Se limpia al inicio de cada turno con clear_llm_cache().
_llm_call_cache: dict[str, str] = {}

# Control de procesos para limpiar Ollama al salir
_ollama_process = None

def _cleanup_ollama():
    global _ollama_process
    import subprocess
    # 1. Terminar el subproceso directo que levantamos nosotros
    if _ollama_process is not None:
        try:
            logger.info("Terminando proceso Ollama iniciado por Jellyfish (PID: %d)", _ollama_process.pid)
            _ollama_process.terminate()
            _ollama_process.wait(timeout=2)
        except Exception:
            try:
                _ollama_process.kill()
            except Exception:
                pass
    # 2. Asegurar que no quedan huérfanos del usuario actual
    try:
        user = os.getenv("USER", "")
        if user:
            subprocess.run(["pkill", "-u", user, "-f", "ollama serve"], capture_output=True)
    except Exception:
        pass

import atexit
atexit.register(_cleanup_ollama)


class LocalLLMTimeoutError(RuntimeError):
    """Excepción lanzada cuando el modelo local (Ollama) sufre un timeout de GPU/memoria saturada."""
    pass


def _truncate_messages_to_budget(messages: list, limit: int) -> list:
    """Trunca el historial de mensajes de forma segura para no exceder el límite de tokens.

    Mantiene siempre el mensaje de sistema original (si existe) y va agregando los
    mensajes más recientes de atrás hacia adelante hasta agotar el presupuesto de tokens.
    """
    if not messages:
        return []

    # Dejar un margen de seguridad de 1000 tokens para la respuesta del modelo
    safety_margin = 1000
    budget = max(1024, limit - safety_margin)

    system_msgs = [m for m in messages if m.get("role") == "system"]
    other_msgs = [m for m in messages if m.get("role") != "system"]

    system_tokens = sum(estimate_tokens(m.get("content", "")) for m in system_msgs)
    available_budget = budget - system_tokens

    if not other_msgs:
        return system_msgs

    selected_other = []
    other_tokens_sum = 0
    
    # Siempre forzar la inclusión del último mensaje (prompt actual del usuario).
    # Si omitimos esto (ej. por presupuesto agotado), el LLM solo recibe el System Prompt
    # y empieza a alucinar texto basura tratando de autocompletarlo.
    last_msg = other_msgs[-1]
    selected_other.insert(0, last_msg)
    other_tokens_sum += estimate_tokens(last_msg.get("content", ""))

    # Recorrer del penúltimo al más viejo
    for msg in reversed(other_msgs[:-1]):
        msg_tokens = estimate_tokens(msg.get("content", ""))
        if other_tokens_sum + msg_tokens <= available_budget:
            selected_other.insert(0, msg)
            other_tokens_sum += msg_tokens
        else:
            break

    return system_msgs + selected_other

def clear_llm_cache() -> None:
    """Limpia la caché L1 de llamadas LLM. Llamar al inicio de cada turno."""
    _llm_call_cache.clear()

# Regex para detectar bloques de código bash/sh/shell
_BASH_REGEX = re.compile(
    r"```(?:bash|sh|shell|zsh)?\s*\n(.*?)\n```",
    re.DOTALL
)

# Sprint 8.0 — Cliente HTTP persistente (singleton) para reutilizar conexiones
_http_client: httpx.Client | None = None
_http_client_lock = threading.Lock()

def _get_sync_client() -> httpx.Client:
    global _http_client
    with _http_client_lock:
        if _http_client is None:
            _http_client = httpx.Client(
                timeout=httpx.Timeout(300.0, connect=30.0),
                limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
                follow_redirects=True,
            )
        return _http_client

import atexit
def _close_http_client():
    global _http_client
    with _http_client_lock:
        if _http_client is not None:
            _http_client.close()
            _http_client = None

atexit.register(_close_http_client)


def ensure_ollama_running(ollama_url: str = "http://localhost:11434") -> bool:
    """Verifica si Ollama está activo. Si no, intenta levantarlo en segundo plano.

    Sprint 11 — Levantamiento automático de Ollama.
    """
    import subprocess
    from urllib.parse import urlparse
    parsed = urlparse(ollama_url)
    if parsed.scheme and parsed.netloc:
        base_url = f"{parsed.scheme}://{parsed.netloc}"
    else:
        base_url = ollama_url.rstrip("/")
    api_url = f"{base_url}/api/tags"
    
    try:
        # Intentar una petición rápida con timeout corto
        with httpx.Client(timeout=1.5) as client:
            resp = client.get(api_url)
            if resp.status_code == 200:
                logger.info("Ollama ya se encuentra activo en %s", base_url)
                return True
    except (httpx.ConnectError, httpx.TimeoutException, httpx.RequestError):
        pass
        
    # Si no responde, intentar levantarlo
    logger.info("Ollama no responde. Intentando iniciar servicio 'ollama serve'...")
    console.print(f"⚠ Ollama no responde en {base_url}. Intentando iniciar 'ollama serve' en segundo plano...")
    
    try:
        # Ejecutar ollama serve en segundo plano
        global _ollama_process
        _ollama_process = subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            preexec_fn=os.setpgrp if hasattr(os, "setpgrp") else None
        )
        
        # Esperar y verificar hasta 3 veces si responde (cada 2 segundos)
        for i in range(3):
            time.sleep(2.0)
            try:
                with httpx.Client(timeout=1.5) as client:
                    resp = client.get(api_url)
                    if resp.status_code == 200:
                        console.print("✓ Ollama iniciado correctamente en segundo plano.")
                        logger.info("Ollama iniciado exitosamente en el intento %d", i+1)
                        return True
            except (httpx.ConnectError, httpx.TimeoutException, httpx.RequestError):
                pass
    except FileNotFoundError:
        console.print("⚠ Alerta: El comando 'ollama' no está instalado en el sistema.")
        logger.warning("El ejecutable 'ollama' no fue encontrado.")
        return False
    except Exception as e:
        console.print(f"⚠ Alerta: No se pudo iniciar Ollama automáticamente: {e}")
        logger.error("Error al levantar Ollama: %s", e)
        return False
        
    console.print("⚠ Advertencia: Se ejecutó 'ollama serve' pero no responde. Es posible que debas iniciarlo manualmente.")
    logger.warning("Ollama se ejecutó pero no responde en %s", base_url)
    return False


def _chat_completions_url(base_url: str) -> str:
    """Construye el endpoint Chat Completions sin duplicar el sufijo."""
    base = (base_url or "").rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    return f"{base}/chat/completions"


def _get_provider_config(state, provider: str | None = None) -> tuple[str, dict]:
    """Retorna (url, headers) para el proveedor activo u override.

    Ollama usa su endpoint nativo. Los demas proveedores pasan por endpoints
    compatibles con OpenAI Chat Completions, a menos que sea el proveedor native Claude.
    """
    provider_name = normalize_provider(provider or state.provider)
    if provider_name == "ollama":
        base_url = state.ollama_base_url.rstrip("/")
        if not base_url.endswith("/api/chat"):
            url = f"{base_url}/api/chat"
        else:
            url = base_url
        return url, {"Content-Type": "application/json"}

    base_url = state.base_urls.get(provider_name) or getattr(state, f"{provider_name}_base_url", "")
    if not base_url:
        raise ValueError(f"Proveedor '{provider_name}' requiere configurar base_url.")

    api_key = state.api_keys.get(provider_name) or getattr(state, f"{provider_name}_api_key", "")
    
    # Soporte nativo para Anthropic si el base_url apunta a su endpoint oficial
    if provider_name == "claude" and "api.anthropic.com" in base_url:
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        url = f"{base_url.rstrip('/')}/messages"
        return url, headers

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    if provider_name == "openrouter":
        headers["HTTP-Referer"] = "https://github.com/jellyfish-os"
        headers["X-Title"] = "Jellyfish OS"

    return _chat_completions_url(base_url), headers


def _parse_sse_line(line_bytes: bytes, provider: str) -> str:
    """Parsea una línea del stream SSE (OpenAI/Anthropic compatible) y retorna el contenido delta."""
    decoded = line_bytes.decode("utf-8").strip()
    if not decoded.startswith("data: "):
        return ""
    payload = decoded[6:]
    if payload == "[DONE]":
        return ""
    try:
        data = json.loads(payload)
        choices = data.get("choices", [])
        if choices:
            return choices[0].get("delta", {}).get("content", "") or ""
        
        # Formato Anthropic SSE
        if data.get("type") == "content_block_delta":
            return data.get("delta", {}).get("text", "") or ""
            
    except json.JSONDecodeError:
        pass
    return ""


def _parse_ollama_line(line_bytes: bytes) -> str:
    """Parsea una línea del stream nativo de Ollama."""
    try:
        data = json.loads(line_bytes.decode("utf-8"))
        if "message" in data:
            return data["message"].get("content", "")
    except json.JSONDecodeError:
        pass
    return ""


def _prepare_payload(provider_name: str, url: str, model_name: str, messages: list, attempt: int = 1, state = None) -> dict:
    is_cloud = provider_name != "ollama"
    is_native_anthropic = (provider_name == "claude" and "api.anthropic.com" in url)

    # Mapeo de modelos locales/antigravity de Gemini a IDs oficiales de la API de Google
    if provider_name == "gemini":
        gemini_mapping = {
            "gemini-2.5-flash": "gemini-2.5-flash",
            "gemini-2.5-pro": "gemini-2.5-pro",
            "gemini-2.0-flash": "gemini-2.0-flash",
            "gemini-1.5-flash": "gemini-1.5-flash",
            "gemini-1.5-pro": "gemini-1.5-pro",
        }
        model_name = gemini_mapping.get(model_name, model_name)

    if provider_name == "ollama":
        limit = getattr(state, "local_context_limit", 4096) if state is not None else 4096
        if not isinstance(limit, int):
            limit = 4096
        messages = _truncate_messages_to_budget(messages, limit)

    payload = {
        "model": model_name,
        "stream": True,
    }
    if is_cloud:
        payload["temperature"] = max(0.0, 0.2 - 0.05 * (attempt - 1))
    else:
        limit = getattr(state, "local_context_limit", 4096) if state is not None else 4096
        if not isinstance(limit, int):
            limit = 4096
            
        actual_tokens = sum(estimate_tokens(m.get("content", "")) for m in messages)
        actual_num_ctx = max(limit, actual_tokens + 1024)
        
        payload["options"] = {
            "num_ctx": actual_num_ctx,
            "temperature": max(0.0, 0.2 - 0.05 * (attempt - 1)),
        }

    # Consolidar todos los mensajes de sistema en uno solo para evitar alucinaciones
    # y confusión en modelos locales/sencillos
    system_content = []
    other_messages = []
    for msg in messages:
        if msg.get("role") == "system":
            system_content.append(msg.get("content", "").strip())
        else:
            other_messages.append(msg)

    consolidated_system = "\n\n".join(filter(None, system_content))

    if is_native_anthropic:
        payload["max_tokens"] = 4096
        filtered_messages = []
        for msg in other_messages:
            role = msg.get("role")
            if role not in ("user", "assistant"):
                role = "user"
            filtered_messages.append({"role": role, "content": msg.get("content", "")})
        payload["messages"] = filtered_messages
        if consolidated_system:
            payload["system"] = consolidated_system
    else:
        # Para Ollama, OpenAI, Gemini, etc. -> enviar un solo mensaje "system" al inicio
        cleaned_messages = []
        if consolidated_system:
            cleaned_messages.append({"role": "system", "content": consolidated_system})
        for msg in other_messages:
            role = msg.get("role")
            if role not in ("user", "assistant"):
                role = "user"
            cleaned_messages.append({"role": role, "content": msg.get("content", "")})
        payload["messages"] = cleaned_messages

    return payload


def _call_llm_silent(
    state,
    messages: list,
    provider: str | None = None,
    model: str | None = None,
    timeout: float | None = None,
) -> str | None:
    """Llama al LLM sin mostrar streaming en pantalla (para subagentes internos).

    Sprint 1.2 — Usa httpx en modo síncrono con streaming silencioso.
    Sprint 3.1 — Migrado de requests a httpx.
    Auditoría — Reestructurado el bucle de reintento: el bug anterior hacía
    que el `continue` dentro del `with client.stream(...)` no escapara al
    loop de reintentos, causando ráfagas masivas de 429 sin backoff real.
    Auditoría — Añadida caché L1 por turno para evitar llamadas duplicadas.
    """
    provider_name = normalize_provider(provider or state.provider)
    url, headers = _get_provider_config(state, provider_name)
    is_cloud = provider_name != "ollama"
    model_name = model or state.model

    # --- Caché L1 por turno: evitar llamadas duplicadas con los mismos mensajes ---
    import hashlib as _hashlib
    cache_key = _hashlib.sha256(
        f"{provider_name}:{model_name}:{json.dumps(messages, ensure_ascii=False, sort_keys=True)}".encode()
    ).hexdigest()
    if cache_key in _llm_call_cache:
        logger.debug("Cache hit para _call_llm_silent (hash=%s…)", cache_key[:12])
        return _llm_call_cache[cache_key]

    max_attempts = 5
    initial_delay = 2.0
    backoff_factor = 2.0

    if provider_name == "ollama":
        actual_timeout = timeout if isinstance(timeout, httpx.Timeout) else (
            httpx.Timeout(timeout, connect=10.0) if timeout is not None
            else httpx.Timeout(180.0, connect=10.0)
        )
    else:
        actual_timeout = timeout

    for attempt in range(1, max_attempts + 1):
        payload = _prepare_payload(provider_name, url, model_name, messages, attempt, state=state)
        try:
            full = ""
            parse_fn = (
                (lambda line: _parse_sse_line(line, provider_name))
                if is_cloud
                else _parse_ollama_line
            )
            
            client = _get_sync_client()
            # Auditoría: usamos request() sin streaming primero para verificar
            # el status code, y luego procesamos el stream solo si es 200.
            # Esto evita el bug donde `continue` no escapaba del context manager.
            should_retry = False
            with client.stream("POST", url, headers=headers, json=payload, timeout=actual_timeout) as response:
                if response.status_code == 429 or (500 <= response.status_code < 600):
                    should_retry = True
                    # Consumir el body para liberar la conexión
                    try:
                        response.read()
                    except Exception:
                        pass
                elif response.status_code != 200:
                    logger.warning(
                        "_call_llm_silent HTTP %s de %s", response.status_code, provider_name
                    )
                    return None
                else:
                    # Status 200 — procesar stream normalmente
                    for line in response.iter_lines():
                        if not line:
                            continue
                        chunk = parse_fn(line.encode("utf-8"))
                        if chunk:
                            full += chunk

            # Evaluar resultado FUERA del context manager del stream
            if should_retry:
                delay = initial_delay * (backoff_factor ** (attempt - 1))
                logger.warning(
                    "_call_llm_silent HTTP retryable de %s. Reintentando en %.1fs (Intento %d/%d)...",
                    provider_name, delay, attempt, max_attempts
                )
                time.sleep(delay)
                continue

            if full:
                tokens_input = sum(estimate_tokens(m.get("content", "")) for m in messages)
                tokens_output = estimate_tokens(full)
                total_tokens = tokens_input + tokens_output
                if hasattr(state, "add_session_tokens"):
                    state.add_session_tokens(total_tokens)
                # Guardar en caché L1
                _llm_call_cache[cache_key] = full
                return full
            else:
                # Output vacío sin error HTTP — reintentar
                if attempt < max_attempts:
                    delay = initial_delay * (backoff_factor ** (attempt - 1))
                    logger.warning(
                        "_call_llm_silent retornó output vacío de %s. Reintentando en %.1fs...",
                        provider_name, delay
                    )
                    time.sleep(delay)
                    continue
                return None

        except (httpx.ConnectError, httpx.TimeoutException, httpx.RequestError) as e:
            if provider_name == "ollama" and isinstance(e, httpx.TimeoutException):
                console.print("\n[red]⚠ El modelo local superó el tiempo de espera (Timeout). Memoria saturada.[/red]\n")
                logger.error("Timeout del modelo local (GPU saturada) en _call_llm_silent: %s", e)
                raise LocalLLMTimeoutError("El modelo local superó el tiempo de espera (Timeout). Memoria saturada.") from e

            if attempt < max_attempts:
                delay = initial_delay * (backoff_factor ** (attempt - 1))
                logger.warning(
                    "Error de conexión/red en _call_llm_silent: %s. Reintentando en %.1fs...",
                    e, delay
                )
                time.sleep(delay)
            else:
                logger.error("Error definitivo en _call_llm_silent tras %d intentos: %s", max_attempts, e)
                return None

    return None


def _get_models_list_url_and_headers(state, provider_name: str) -> tuple[str, dict]:
    """Retorna (url, headers) para consultar la lista de modelos del proveedor."""
    provider_name = normalize_provider(provider_name)
    if provider_name == "ollama":
        from urllib.parse import urlparse
        parsed = urlparse(state.ollama_base_url)
        if parsed.scheme and parsed.netloc:
            base_url = f"{parsed.scheme}://{parsed.netloc}"
        else:
            base_url = state.ollama_base_url.rstrip("/")
        return f"{base_url}/api/tags", {"Content-Type": "application/json"}

    base_url = state.base_urls.get(provider_name) or getattr(state, f"{provider_name}_base_url", "")
    if not base_url:
        from core.config import PROVIDER_CONFIGS
        base_url = PROVIDER_CONFIGS.get(provider_name, {}).get("default_base_url", "")
        if not base_url:
            raise ValueError(f"Proveedor '{provider_name}' no tiene base_url configurado.")

    api_key = state.api_keys.get(provider_name) or getattr(state, f"{provider_name}_api_key", "")

    headers = {"Content-Type": "application/json"}
    if api_key:
        if provider_name == "claude" and "api.anthropic.com" in base_url:
            headers = {
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            }
        else:
            headers["Authorization"] = f"Bearer {api_key}"

    if provider_name == "openrouter":
        headers["HTTP-Referer"] = "https://github.com/jellyfish-os"
        headers["X-Title"] = "Jellyfish OS"

    url = base_url.rstrip("/")
    return f"{url}/models", headers


def _fetch_provider_models_dynamic(state, provider_name: str) -> list[str]:
    """Obtiene la lista de modelos de un endpoint compatible con OpenAI o de la API de Gemini."""
    provider_name = normalize_provider(provider_name)
    url, headers = _get_provider_config(state, provider_name)
    base_url = state.base_urls.get(provider_name) or getattr(state, f"{provider_name}_base_url", "")
    api_key = state.api_keys.get(provider_name) or getattr(state, f"{provider_name}_api_key", "")
    
    models = []
    if not base_url:
        return models
    try:
        base_url_lower = base_url.lower()
        if "generativelanguage.googleapis.com" in base_url_lower or "gemini" in base_url_lower:
            models_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
            client = _get_sync_client()
            resp = client.get(models_url, timeout=5.0)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, dict) and "models" in data:
                    for item in data["models"]:
                        if isinstance(item, dict) and "name" in item:
                            name = item["name"]
                            if name.startswith("models/"):
                                name = name[len("models/"):]
                            models.append(name)
        else:
            models_url = f"{base_url.rstrip('/')}/models"
            client = _get_sync_client()
            resp = client.get(models_url, headers=headers, timeout=5.0)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, dict) and "data" in data:
                    for item in data["data"]:
                        if isinstance(item, dict) and "id" in item:
                            models.append(item["id"])
    except Exception as e:
        logger.warning("Error fetching models dynamically from %s: %s", provider_name, e)
        raise e
    return sorted(list(set(models)))


def _fetch_ollama_models_local(state) -> list[str]:
    base_url = state.ollama_base_url
    from urllib.parse import urlparse
    parsed = urlparse(base_url or "http://localhost:11434")
    tags_url = f"{parsed.scheme}://{parsed.netloc}/api/tags" if parsed.netloc else "http://localhost:11434/api/tags"
    try:
        client = _get_sync_client()
        resp = client.get(tags_url, timeout=3.0)
        if resp.status_code == 200:
            data = resp.json()
            return [m["name"] for m in data.get("models", [])]
    except Exception:
        pass
    return ["llama3", "mistral", "codellama", "qwen2.5-coder"]


def _select_fallback_model(provider_name: str, available_models: list[str], failed_models: set[str]) -> str | None:
    priorities = {
        "gemini": ["gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"],
        "claude": ["claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022", "claude-3-opus-20240229"],
        "openai": ["gpt-4o", "gpt-4o-mini", "o1-preview", "o1-mini"],
        "deepseek": ["deepseek-coder", "deepseek-chat"],
        "qwen": ["qwen-max", "qwen-plus", "qwen-turbo"],
        "kimi": ["moonshot-v1-32k", "moonshot-v1-8k"],
        "zhipu": ["glm-4", "glm-4-flash"],
    }
    
    provider_priorities = priorities.get(provider_name, [])
    
    clean_avail = [m.lower() for m in available_models]
    clean_failed = [m.lower() for m in failed_models]
    
    for model_name in provider_priorities:
        if model_name.lower() in clean_avail and model_name.lower() not in clean_failed:
            idx = clean_avail.index(model_name.lower())
            return available_models[idx]
            
    for m in available_models:
        m_lower = m.lower()
        if m_lower not in clean_failed:
            if not any(k in m_lower for k in ["embed", "moderation", "similarity", "whisper", "tts", "dall-e", "preview", "experimental", "antigravity", "vision"]):
                return m
                
    for m in available_models:
        if m.lower() not in clean_failed:
            return m
            
    return None


def _fallback_to_local_ollama(state) -> tuple[str, str]:
    new_provider = "ollama"
    ensure_ollama_running(state.ollama_base_url)
    
    local_models = _fetch_ollama_models_local(state)
    local_priorities = [
        "qwen2.5-coder:7b",
        "qwen2.5-coder",
        "llama3.1",
        "llama3",
        "mistral",
        "codellama"
    ]
    
    new_model = "llama3"
    clean_local = [m.lower() for m in local_models]
    
    for p_model in local_priorities:
        for idx, m in enumerate(clean_local):
            if p_model in m or m in p_model:
                new_model = local_models[idx]
                break
        if new_model != "llama3":
            break
            
    if new_model == "llama3" and local_models:
        valid_models = [m for m in local_models if "embed" not in m.lower()]
        new_model = valid_models[0] if valid_models else local_models[0]
        
    state.save_config(provider=new_provider, model=new_model)
    return new_provider, new_model


def _stream_request(
    state,
    messages: list,
    agent_name: str,
    _aborted: list | None = None,
    provider: str | None = None,
    model: str | None = None,
) -> str | None:
    """Realiza la petición HTTP con streaming al proveedor configurado en el estado.

    Sprint 3.1 — Migrado de requests a httpx (mejor soporte para cancelación).
    Sprint 3.3 — Soporta interrupción grácil via Ctrl+C: aborta solo el stream
                  HTTP sin matar el proceso completo. Señal via lista _aborted mutable.
    Sprint 13  — Fallback y auto-switching resiliente de modelos y proveedores.
    """
    failed_models = set()
    max_fallbacks = 3
    fallback_attempt = 0

    while fallback_attempt <= max_fallbacks:
        provider_name = normalize_provider(provider or state.provider)
        model_name = model or state.model
        url, headers = _get_provider_config(state, provider_name)
        is_cloud = provider_name != "ollama"

        payload = _prepare_payload(provider_name, url, model_name, messages, state=state)

        full = ""
        parse_fn = (
            (lambda line: _parse_sse_line(line, provider_name))
            if is_cloud
            else _parse_ollama_line
        )

        status_code = None
        error_msg = ""

        actual_timeout = (
            httpx.Timeout(180.0, connect=15.0)
            if provider_name == "ollama"
            else httpx.Timeout(300.0, connect=30.0)
        )

        try:
            import asyncio

            from core.tui import tui_engine
            tui_active = getattr(tui_engine, "_initialized", False)

            async def _run_stream():
                nonlocal full, status_code, error_msg
                async with httpx.AsyncClient(
                    timeout=actual_timeout,
                    limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
                    follow_redirects=True,
                ) as client:
                    # En modo TUI, NO usar console.status() (el spinner de Rich
                    # genera secuencias ANSI que contaminan el Output Panel).
                    # El header ya muestra ESTADO: PROCESS como indicador visual.
                    status = None
                    if not tui_active:
                        status = console.status(f"[cyan]Pensando ({provider_name})...[/cyan]")
                        status.start()
                    else:
                        tui_engine.append_log(f"⏳ Pensando ({provider_name})...\n")
                    try:
                        async with client.stream("POST", url, headers=headers, json=payload) as response:
                            if status:
                                status.stop()
                            if response.status_code != 200:
                                status_code = response.status_code
                                error_body = (await response.aread())[:500].decode("utf-8", errors="replace")
                                error_msg = error_body
                                response.raise_for_status()
                                return

                            if tui_active:
                                try:
                                    async for line in response.aiter_lines():
                                        if _aborted and _aborted[0]:
                                            tui_engine.append_log("\n⚡ Stream interrumpido — respuesta parcial conservada.\n")
                                            break
                                        if not line:
                                            continue
                                        chunk = parse_fn(line.encode("utf-8"))
                                        if chunk:
                                            full += chunk
                                            tui_engine.append_log(chunk)
                                except KeyboardInterrupt:
                                    tui_engine.append_log("\n⚡ Stream interrumpido — respuesta parcial conservada.\n")
                                    if _aborted is not None:
                                        _aborted[0] = True
                            else:
                                with Live(
                                    "",
                                    refresh_per_second=12,
                                    console=console,
                                ) as live:
                                    try:
                                        async for line in response.aiter_lines():
                                            if _aborted and _aborted[0]:
                                                print("\n⚡ Stream interrumpido — respuesta parcial conservada.")
                                                break
                                            if not line:
                                                continue
                                            chunk = parse_fn(line.encode("utf-8"))
                                            if chunk:
                                                full += chunk
                                                live.update(Markdown(full))
                                    except KeyboardInterrupt:
                                        print("\n⚡ Stream interrumpido — respuesta parcial conservada.")
                                        if _aborted is not None:
                                            _aborted[0] = True
                    finally:
                        if status:
                            status.stop()

            asyncio.run(_run_stream())

            if full:
                tokens_input = sum(estimate_tokens(m.get("content", "")) for m in messages)
                tokens_output = estimate_tokens(full)
                total_tokens = tokens_input + tokens_output
                if hasattr(state, "add_session_tokens"):
                    state.add_session_tokens(total_tokens)
                
                if not hasattr(state, "_turn_stats"):
                    state._turn_stats = []
                state._turn_stats.append({
                    "input": tokens_input,
                    "output": tokens_output,
                    "total": total_tokens
                })
                logger.info("Respuesta: %d tokens (Input: %d | Output: %d)", total_tokens, tokens_input, tokens_output)
                return full
            else:
                return None

        except (httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException, httpx.RequestError) as e:
            if provider_name == "ollama" and isinstance(e, httpx.TimeoutException):
                msg = "\n⚠ El modelo local superó el tiempo de espera (Timeout). Memoria saturada.\n"
                if getattr(tui_engine, "_initialized", False):
                    tui_engine.append_log(msg)
                else:
                    console.print(f"[red]{msg.strip()}[/red]")
                logger.error("Timeout del modelo local (GPU saturada) en _stream_request: %s", e)
                raise LocalLLMTimeoutError("El modelo local superó el tiempo de espera (Timeout). Memoria saturada.") from e

            code = status_code or (e.response.status_code if hasattr(e, "response") and e.response else None)
            failed_models.add(model_name)

            def log_msg(msg):
                if getattr(tui_engine, "_initialized", False):
                    tui_engine.append_log(msg + "\n")
                else:
                    console.print(msg)

            if provider_name == "ollama" and code == 404:
                error_alert = f"❌ El modelo '{model_name}' no está instalado en Ollama.\n\nPor favor, abre otra terminal y ejecuta:\n    ollama pull {model_name}\n\nLuego vuelve a intentarlo."
                log_msg(f"\n{error_alert}\n")
                logger.error("Ollama model not found: %s", model_name)
                return error_alert

            if code in (429, 503):
                log_msg(f"⚠ El modelo {model_name} está saturado (Error {code}). Buscando alternativas...")
            else:
                extra_details = f" - Details: {error_msg}" if error_msg else ""
                log_msg(f"⚠ Error al invocar {model_name} (Status: {code}, Error: {e}{extra_details}). Buscando alternativas...")
            
            logger.warning("Fallo en _stream_request: %s (status_code=%s) con modelo %s. Iniciando fallback... Detalles: %s", e, code, model_name, error_msg)

            if fallback_attempt >= max_fallbacks:
                if provider_name != "ollama":
                    log_msg(f"⚠ Límite de fallbacks cloud excedido. Ejecutando Plan C (Fallback a Local)...")
                    try:
                        new_prov, new_model = _fallback_to_local_ollama(state)
                        log_msg(f"✓ Cambiando a proveedor local: {new_prov} (Modelo: {new_model})")
                        max_fallbacks += 1
                        fallback_attempt += 1
                        continue
                    except Exception as local_err:
                        log_msg(f"❌ Falló el fallback local a Ollama: {local_err}")
                        return None
                else:
                    log_msg(f"❌ Se excedió el límite de fallbacks ({max_fallbacks}).")
                    return None

            # Intentar fallback dinámico
            try:
                available_models = _fetch_provider_models_dynamic(state, provider_name)
                new_model = _select_fallback_model(provider_name, available_models, failed_models)
                
                if new_model:
                    state.save_config(model=new_model)
                    log_msg(f"✓ Cambiando a modelo de respaldo dinámico: {new_model}")
                    fallback_attempt += 1
                    continue
                else:
                    raise ValueError("No se encontraron modelos de respaldo viables en este proveedor.")
            except Exception as fe:
                logger.warning("Fallo al obtener modelos dinámicos de %s: %s.", provider_name, fe)
                
                if provider_name == "ollama":
                    log_msg(f"❌ No hay modelos locales viables restantes en Ollama. Abortando.")
                    return None
                    
                log_msg(f"⚠ Proveedor {provider_name} no disponible o sin modelos. Ejecutando Plan C (Fallback a Local)...")
                
                try:
                    new_prov, new_model = _fallback_to_local_ollama(state)
                    log_msg(f"✓ Cambiando a proveedor local: {new_prov} (Modelo: {new_model})")
                    fallback_attempt += 1
                    continue
                except Exception as local_err:
                    log_msg(f"❌ Falló el fallback local a Ollama: {local_err}")
                    return None


def stream_ollama(state, rag_context: str = "") -> str | None:
    """Envía los mensajes al LLM y hace streaming de la respuesta.

    Implementa un bucle Auto-ReAct: si el modelo sugiere comandos bash
    y el usuario los aprueba, el output del terminal se envía de vuelta
    al modelo para que pueda razonar sobre el resultado.

    Sprint 3.1 — Migrado a httpx.
    Sprint 3.3 — Ctrl+C aborta solo el stream, no el proceso.

    Args:
        state: Instancia de JellyfishState con el historial completo.
        rag_context: Contexto RAG pre-recuperado para inyectar.

    Returns:
        La respuesta completa del modelo (última iteración), o None si hay error.
    """
    t_start = time.perf_counter()
    
    # Auditoría — Limpiar caché L1 al inicio de cada turno
    clear_llm_cache()
    # Esto asegura que el agente conversacional lea las últimas escrituras de
    # los tableros (DEV_BOARD.md) que hayan ocurrido durante ejecuciones en 2do plano.
    if hasattr(state, "refresh_static_context"):
        state.refresh_static_context()
        
    state._turn_stats = []
    react_iteration = 0
    final_response = None
    _aborted = [False]  # Sprint 3.3 — señal mutable de cancelación

    # Limpiar comandos denegados en este turno para prevenir prompts y ejecuciones duplicadas
    state.denied_commands = set()

    while react_iteration < MAX_REACT_LOOPS:
        react_iteration += 1

        messages = state.get_full_history()

        # Inyectar contexto RAG como mensaje de sistema justo antes del final
        if rag_context:
            messages = messages.copy()
            messages.insert(-1, {
                "role": "system",
                "content": (
                    "[INSTRUCCIÓN: El siguiente contexto fue recuperado automáticamente "
                    "del código fuente indexado. Úsalo para fundamentar tu respuesta "
                    "cuando sea relevante, pero no lo cites textualmente a menos que "
                    "el usuario lo solicite.]\n" + rag_context
                )
            })

        # Sprint 8.0 — Activar flag de spinner en TUI
        _state_module._llm_busy = True
        try:
            full = _stream_request(state, messages, state.active_agent, _aborted=_aborted)
        finally:
            _state_module._llm_busy = False

        # Si fue cancelado por Ctrl+C, conservar lo que llegó y salir del ReAct
        if _aborted[0]:
            final_response = full or final_response
            break

        if not full:
            if react_iteration == 1:
                console.print("⚠ El modelo no generó respuesta.")
            return final_response

        final_response = full

        # --- Action Loop: Interceptor de comandos bash ---
        matches = _BASH_REGEX.findall(full)
        if not matches:
            break

        executed_any = False
        for cmd in matches:
            cmd_clean = cmd.strip()
            if not cmd_clean:
                continue

            cmd_display = cmd_clean[:200] + "..." if len(cmd_clean) > 200 else cmd_clean

            # Sprint 8.0 — Auto-aprobación para comandos de solo lectura
            if is_readonly_command(cmd_clean):
                cmd_display = cmd_clean[:200] + "..." if len(cmd_clean) > 200 else cmd_clean
                console.print(
                    f"\n⚡ Auto-ejecutando comando de lectura:\n"
                    f"{cmd_display}"
                )
                output = run_terminal_command(cmd_clean, state, force_confirm=False)
            else:
                # La confirmación, validación y [y/n/a] se manejan centralizadamente en terminal.py
                output = run_terminal_command(cmd_clean, state, force_confirm=True)

            executed_any = True

            state.history.append({"role": "assistant", "content": full})
            state.history.append({
                "role": "user",
                "content": (
                    f"El comando se ejecutó. Aquí está el resultado:\n"
                    f"<terminal_output>\n{output[:3000]}\n</terminal_output>\n"
                    f"Analiza el resultado y continúa."
                )
            })

        if not executed_any:
            break

        console.print(f"[dim]🔄 Auto-ReAct: iteración {react_iteration}/{MAX_REACT_LOOPS}...[/dim]")

    # --- Citador Heurístico (Sprint 1 Quick Win) ---
    if final_response and rag_context:
        from core.rag_coder import _FRAG_OPEN
        import re as _re
        _frag_prefix = _re.escape(_FRAG_OPEN.split(" ")[0])
        sources = set(_re.findall(
            rf'{_frag_prefix}\s+source="([^"]+)"', rag_context
        ))
        actual_citations: set = set()
        for source in sources:
            basename = source.split("/")[-1]
            if basename in final_response or source in final_response:
                actual_citations.add(source)

        if actual_citations:
            citation_block = "\n\n---\n**📚 Fuentes Citadas:**\n"
            for src in sorted(actual_citations):
                abs_path = os.path.abspath(src)
                citation_block += f"- [{src}](file://{abs_path})\n"
            final_response += citation_block
            console.print(Markdown(citation_block))

    # --- Resumen Consolidado de Métricas del Turno ---
    if hasattr(state, "_turn_stats") and state._turn_stats:
        total_in = sum(s["input"] for s in state._turn_stats)
        total_out = sum(s["output"] for s in state._turn_stats)
        total_tok = total_in + total_out
        elapsed = time.perf_counter() - t_start
        print(f"\n[{total_in:,} → {total_out:,} tok | total {total_tok:,} | {elapsed:.1f}s]")

    return final_response


def is_ollama_running(url: str = "http://localhost:11434") -> bool:
    """Verifica de forma ultra-rápida si Ollama está respondiendo en localhost."""
    import httpx
    try:
        with httpx.Client(timeout=0.5) as client:
            resp = client.get(url)
            return resp.status_code == 200 or resp.status_code == 404
    except Exception:
        return False


def is_model_available_locally(model_name: str, url: str = "http://localhost:11434") -> bool:
    """Verifica de forma ultra-rápida si el modelo de Ollama está descargado localmente."""
    import httpx
    try:
        with httpx.Client(timeout=1.0) as client:
            resp = client.get(f"{url.rstrip('/')}/api/tags")
            if resp.status_code == 200:
                models = [m["name"] for m in resp.json().get("models", [])]
                if model_name in models:
                    return True
                # También buscar por nombre base sin tag/versión
                model_base = model_name.split(":")[0]
                for m in models:
                    if m.split(":")[0] == model_base:
                        return True
    except Exception:
        pass
    return False
