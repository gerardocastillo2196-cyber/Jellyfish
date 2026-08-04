import os
import logging
from typing import List
from fnmatch import fnmatch

from core.llm_engine import _call_llm_silent

logger = logging.getLogger("jellyfish.project_analyzer")

# Directorios globales a ignorar en el árbol
_IGNORE_DIRS = {
    "venv", ".git", "__pycache__", "node_modules", "code_vector_db",
    "test_db", ".next", "dist", "build", ".venv", "env", ".tox",
    "htmlcov", ".mypy_cache", ".pytest_cache", "eggs", "*.egg-info",
}

def _load_jellyfishignore(base_path: str) -> List[str]:
    """Carga patrones de exclusión desde un archivo .jellyfishignore."""
    ignore_file = os.path.join(base_path, ".jellyfishignore")
    patterns = []
    if os.path.exists(ignore_file):
        try:
            with open(ignore_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        patterns.append(line)
        except (OSError, IOError):
            pass
    return patterns

def _should_ignore(path: str, patterns: List[str]) -> bool:
    """Verifica si una ruta coincide con algún patrón de ignorar."""
    basename = os.path.basename(path)
    for pattern in patterns:
        if fnmatch(basename, pattern) or fnmatch(path, pattern):
            return True
    return False

def _generate_tree(dir_path: str, prefix: str = "", ignore_patterns: List[str] = None) -> str:
    """Genera una representación en texto del árbol de directorios recursivamente."""
    if ignore_patterns is None:
        ignore_patterns = []

    tree_str = ""
    try:
        entries = sorted(os.listdir(dir_path))
    except Exception:
        return ""

    # Filtrar entradas
    entries = [
        e for e in entries
        if e not in _IGNORE_DIRS
        and not e.startswith(".")
        and not _should_ignore(os.path.join(dir_path, e), ignore_patterns)
    ]

    for i, entry in enumerate(entries):
        is_last = (i == len(entries) - 1)
        connector = "└── " if is_last else "├── "
        tree_str += f"{prefix}{connector}{entry}\n"

        full_path = os.path.join(dir_path, entry)
        if os.path.isdir(full_path):
            extension = "    " if is_last else "│   "
            tree_str += _generate_tree(full_path, prefix + extension, ignore_patterns)

    return tree_str

def generate_architecture_document(state, project_path: str) -> bool:
    """Escanea el proyecto y pide al LLM planificador que genere el .jellyfish_architecture.md."""
    if not os.path.isdir(project_path):
        return False
        
    logger.info("Generando Project Map (Documento de Arquitectura) para %s", project_path)
    
    ignore_patterns = _load_jellyfishignore(project_path)
    project_name = os.path.basename(project_path)
    
    # 1. Generar Árbol de Directorios
    tree_text = _generate_tree(project_path, ignore_patterns=ignore_patterns)
    if not tree_text.strip():
        logger.warning("El árbol del proyecto está vacío, no se generará el documento.")
        return False

    # Truncar el árbol si es absurdamente grande
    if len(tree_text) > 12000:
        tree_text = tree_text[:12000] + "\n... (TRUNCADO)"

    # 2. Preparar el Prompt para el LLM Planificador
    system_prompt = (
        "Eres el Arquitecto de Software Principal (Planner) de Jellyfish OS. "
        "Tu tarea es analizar el árbol de directorios de un proyecto recién indexado "
        "y generar un 'Documento de Arquitectura Global' (Project Map) conciso pero altamente técnico.\n"
        "Este documento servirá como contexto base para otros agentes RAG.\n\n"
        "REGLAS OBLIGATORIAS:\n"
        "1. Mantén la respuesta por debajo de los 1000 tokens.\n"
        "2. Identifica el propósito principal del proyecto basándote en los nombres de las carpetas y archivos.\n"
        "3. Lista los módulos clave y su presunta responsabilidad.\n"
        "4. Usa formato Markdown limpio sin bloque de código envolvente (sin ```markdown).\n"
        "5. No hagas suposiciones sobre implementaciones internas; guíate estrictamente por la estructura."
    )
    
    user_prompt = (
        f"Analiza la siguiente estructura del proyecto '{project_name}' y genera el Documento de Arquitectura:\n\n"
        f"{tree_text}"
    )
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    # 3. Llamar al LLM en silencio usando el perfil del Planificador (Cloud)
    try:
        content = _call_llm_silent(state, messages, agent_name="planner")
    except Exception as e:
        logger.error("Error al generar el documento de arquitectura con el LLM: %s", e)
        return False
        
    if not content:
        logger.warning("El LLM retornó un documento de arquitectura vacío.")
        return False
        
    # Limpiar el bloque de código Markdown si el LLM lo incluye por accidente
    if content.startswith("```markdown\n"):
        content = content[12:]
    elif content.startswith("```\n"):
        content = content[4:]
    if content.endswith("\n```"):
        content = content[:-4]
        
    # 4. Escribir el archivo
    output_file = os.path.join(project_path, ".jellyfish_architecture.md")
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(content.strip())
        logger.info("Documento de arquitectura global guardado en %s", output_file)
        return True
    except Exception as e:
        logger.error("Error al escribir .jellyfish_architecture.md: %s", e)
        return False
