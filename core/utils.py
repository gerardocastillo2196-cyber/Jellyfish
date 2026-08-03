"""core/utils.py — Utilidades comunes para Jellyfish OS."""

import logging

logger = logging.getLogger("jellyfish.utils")


def _safe_read(filepath: str) -> str:
    """Lee un archivo de forma segura con codificación UTF-8, ignorando errores."""
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except (OSError, IOError) as e:
        logger.warning("No se pudo leer %s: %s", filepath, e)
        return ""
