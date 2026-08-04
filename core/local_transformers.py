"""core/local_transformers.py — Módulo de Modelos Especializados Locales (Task Routing & FinOps).

Provee carga perezosa (lazy loading), ejecución 100% offline y enrutamiento en CPU/GPU para tareas
atómicas de NLP sin consumir tokens ni invocar al LLM principal.
"""

import os
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
        """Detecta aceleración por GPU (CUDA/MPS); usa CPU (-1 o 'cpu') por defecto para portabilidad."""
        try:
            import torch
            if torch.cuda.is_available():
                return 0  # Primer GPU CUDA
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


# Singleton global exportado para consumo en el OS
local_ai_manager = LocalTransformersManager()
