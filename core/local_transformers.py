"""core/local_transformers.py — Módulo de Modelos Especializados Locales (Task Routing & FinOps).

Provee carga perezosa (lazy loading), ejecución 100% offline y enrutamiento en CPU/GPU para tareas
atómicas de NLP sin consumir tokens ni invocar al LLM principal.
"""

import os
import re
import logging
from typing import Any, Optional, List, Dict
from rich.console import Console

logger = logging.getLogger("jellyfish.local_transformers")
console = Console()

# Configurar directorio local de caché para garantizar operabilidad offline y aislamiento
DEFAULT_CACHE_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".cache", "models"))
os.makedirs(DEFAULT_CACHE_DIR, exist_ok=True)
os.environ["HF_HOME"] = DEFAULT_CACHE_DIR
os.environ["TRANSFORMERS_CACHE"] = DEFAULT_CACHE_DIR
os.environ["HF_DATASETS_CACHE"] = DEFAULT_CACHE_DIR


class LazyModelLoader:
    """Clase base para cargar modelos de Transformers de forma 'lazy' (solo en primera invocación)."""

    def __init__(self, task: str, model_name: str, cache_dir: str = DEFAULT_CACHE_DIR, **kwargs):
        self.task = task
        self.model_name = model_name
        self.cache_dir = cache_dir
        self.kwargs = kwargs
        self._pipeline = None
        self._device = self._detect_device()

    def _detect_device(self) -> int | str:
        """Detecta aceleración por GPU (CUDA/MPS); usa CPU (-1 o 'cpu') por defecto o si la GPU es incompatible."""
        try:
            import warnings
            import torch
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                if torch.cuda.is_available():
                    try:
                        # Verificar si la GPU (ej. CC 6.1) es realmente soportada por esta build de PyTorch
                        _ = torch.zeros(1, device="cuda:0")
                        return 0
                    except Exception:
                        logger.info("CUDA disponible pero incompatible con esta versión de PyTorch. Usando CPU por defecto.")
                elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                    return "mps"
        except ImportError:
            pass
        return -1  # CPU

    def get_pipeline(self) -> Any:
        """Carga el modelo y pipeline en memoria si aún no está cargado (Lazy Loading)."""
        if self._pipeline is None:
            try:
                from transformers import pipeline
                console.print(f"[dim]⚡ [FinOps] Cargando modelo local en memoria: {self.model_name} (Dispositivo: {'CPU' if self._device == -1 else 'GPU'})...[/dim]")
                self._pipeline = pipeline(
                    task=self.task,
                    model=self.model_name,
                    model_kwargs={"cache_dir": self.cache_dir},
                    device=self._device,
                    **self.kwargs
                )
            except Exception as e:
                logger.error("Error cargando modelo %s: %s", self.model_name, e)
                console.print(f"[bold yellow]⚠ Advertencia de carga local:[/bold yellow] No se pudo inicializar el modelo {self.model_name}: {e}")
                return None
        return self._pipeline


class LocalTransformersManager:
    """Gestor centralizado de enrutamiento de tareas para modelos locales de Inteligencia Artificial."""

    _instance = None
    _models: Dict[str, LazyModelLoader] = {}

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(LocalTransformersManager, cls).__new__(cls)
            cls._instance._init_default_models()
        return cls._instance

    def _init_default_models(self):
        # Modelos ligeros (<500MB) para optimizar RAM e inferencia en CPU según directriz FinOps
        # 1. Zero-Shot Classifier (Para etiquetado automático de Backlog sin LLM general)
        self._models["classifier"] = LazyModelLoader(
            task="zero-shot-classification",
            model_name="typeform/distilbert-base-uncased-mnli"
        )
        # 2. Traductor Estructurado (Encoder-Decoder rápido)
        self._models["translator_en_es"] = LazyModelLoader(
            task="translation_en_to_es",
            model_name="Helsinki-NLP/opus-mt-en-es"
        )

    def get_model(self, model_key: str) -> Optional[LazyModelLoader]:
        return self._models.get(model_key)

    def classify_zero_shot(self, text: str, candidate_labels: List[str]) -> Optional[Dict[str, Any]]:
        """Ejecuta clasificación zero-shot sobre un texto usando un modelo local ligero."""
        loader = self.get_model("classifier")
        if not loader:
            return None
        pipe = loader.get_pipeline()
        if pipe is None:
            return None
        try:
            return pipe(text, candidate_labels)
        except Exception as e:
            logger.error("Error en inferencia zero-shot: %s", e)
            return None

    def translate_text(self, text: str, model_key: str = "translator_en_es") -> Optional[str]:
        """Traduce texto plano de forma local sin usar tokens ni LLMs generalistas."""
        loader = self.get_model(model_key)
        if not loader:
            return None
        pipe = loader.get_pipeline()
        if pipe is None:
            return None
        try:
            res = pipe(text)
            if isinstance(res, list) and len(res) > 0 and "translation_text" in res[0]:
                return res[0]["translation_text"]
            return None
        except Exception as e:
            logger.error("Error en inferencia de traducción: %s", e)
            return None

    def tag_backlog_item(self, text: str, threshold: float = 0.35) -> List[str]:
        """Clasifica una historia o tarea y devuelve etiquetas como ['Frontend', 'Security']."""
        # 1. Enfoque FinOps ultrarrápido (heurístico basado en dominio, 0 ms y 0 tokens)
        lower_text = text.lower()
        tags = []
        if any(w in lower_text for w in ["seguridad", "auth", "login", "password", "jwt", "security", "xss", "csrf", "permiso", "token"]):
            tags.append("Security")
        if any(w in lower_text for w in ["bug", "error", "fix", "falla", "corregir", "exception", "crash", "roto"]):
            tags.append("Bug")
        if any(w in lower_text for w in ["sql", "db", "base de datos", "query", "sqlite", "postgres", "mongo", "tabla", "index"]):
            tags.append("Database")
        if any(w in lower_text for w in ["docker", "ci/cd", "deploy", "kubernetes", "nube", "cloud", "aws", "gce", "pipeline"]):
            tags.append("DevOps")
        if any(w in lower_text for w in ["doc", "readme", "guía", "manual", "comentario", "explicación"]):
            tags.append("Documentation")
        if any(w in lower_text for w in ["ui", "ux", "css", "html", "react", "vue", "frontend", "vista", "botón", "interfaz", "modal", "pantalla"]):
            tags.append("Frontend")
        if any(w in lower_text for w in ["api", "endpoint", "backend", "servidor", "server", "django", "fastapi", "flask", "node", "servicio"]):
            tags.append("Backend")
        
        if tags:
            return tags

        # 2. Fallback de Transformer Zero-Shot si la heurística no encuentra coincidencias claras
        candidate_labels = ["Frontend", "Backend", "Security", "Database", "Bug", "DevOps", "Documentation"]
        res = self.classify_zero_shot(text, candidate_labels)
        if res and "labels" in res and "scores" in res:
            labels = res["labels"]
            scores = res["scores"]
            top_tags = [l for l, s in zip(labels, scores) if s >= threshold]
            if not top_tags and len(labels) > 0 and scores[0] >= 0.2:
                top_tags = [labels[0]]
            return top_tags if top_tags else ["General"]
            
        return ["General"]

    def tag_markdown_backlog(self, markdown_content: str) -> str:
        """Enriquece un documento de Backlog en Markdown agregando etiquetas automáticas de categoría sin usar LLM."""
        lines = markdown_content.splitlines()
        enriched_lines = []
        for line in lines:
            # Detectar filas de tabla del backlog: | ID | Historia/Descripción | ...
            if line.strip().startswith("|") and ("US-" in line or "TASK-" in line or "Como usuario" in line or "Como desarrollador" in line):
                parts = [p.strip() for p in line.split("|")]
                if len(parts) >= 3 and not any(tag in parts[2] for tag in ["[Frontend]", "[Backend]", "[Security]", "[Database]", "[Bug]", "[DevOps]", "[Documentation]", "[General]"]):
                    desc = parts[2]
                    tags = self.tag_backlog_item(desc)
                    tag_str = " ".join([f"**[{t}]**" for t in tags])
                    parts[2] = f"{tag_str} {desc}"
                    line = " | ".join(parts)
            enriched_lines.append(line)
        return "\n".join(enriched_lines)

    def translate_markdown_structured(self, markdown_text: str, model_key: str = "translator_en_es") -> str:
        """Traduce texto de Markdown aislando bloques de código, enlaces, tablas y formato AST con expresiones regulares."""
        placeholders = {}
        counter = 0

        # 1. Proteger bloques de código delimitados por backticks triples
        def replace_code_block(match):
            nonlocal counter
            key = f"«CODE_BLOCK_{counter}»"
            placeholders[key] = match.group(0)
            counter += 1
            return key
        text = re.sub(r'```[\s\S]*?```', replace_code_block, markdown_text)

        # 2. Proteger código en línea delimitado por un backtick
        def replace_inline_code(match):
            nonlocal counter
            key = f"«INLINE_CODE_{counter}»"
            placeholders[key] = match.group(0)
            counter += 1
            return key
        text = re.sub(r'`[^`]*?`', replace_inline_code, text)

        # 3. Proteger destinos de enlace en Markdown: [texto](destino) -> dejamos texto, protegemos (destino)
        def replace_link_target(match):
            nonlocal counter
            target = match.group(1)
            key = f"«LINK_TARGET_{counter}»"
            placeholders[key] = f"({target})"
            counter += 1
            return key
        text = re.sub(r'\]\(([^)]+)\)', lambda m: f"]{replace_link_target(m)}", text)

        # 4. Procesar y traducir por líneas/segmentos conservando sintaxis de tablas y bordes
        lines = text.splitlines()
        translated_lines = []
        for line in lines:
            stripped = line.strip()
            # No traducir separadores de tabla, encabezados vacíos o separadores horizontales
            if not stripped or re.match(r'^[\s\|\-\:\*\+\#\>]+$', stripped) or stripped in placeholders:
                translated_lines.append(line)
                continue
            
            # Si es una fila de tabla, traducir celda por celda
            if stripped.startswith("|") and stripped.endswith("|"):
                cells = line.split("|")
                t_cells = []
                for idx, cell in enumerate(cells):
                    c_str = cell.strip()
                    if idx == 0 or idx == len(cells) - 1 or not c_str or c_str in placeholders:
                        t_cells.append(cell)
                    else:
                        t_res = self.translate_text(c_str, model_key=model_key)
                        t_cells.append(f" {t_res if t_res else c_str} ")
                translated_lines.append("|".join(t_cells))
            else:
                t_res = self.translate_text(line, model_key=model_key)
                translated_lines.append(t_res if t_res else line)

        result = "\n".join(translated_lines)

        # 5. Restaurar todos los placeholders intactos en su ubicación original (en orden inverso o por clave)
        for key, orig in reversed(list(placeholders.items())):
            result = result.replace(key, orig)

        return result


# Singleton global exportado para consumo en el OS
local_ai_manager = LocalTransformersManager()
