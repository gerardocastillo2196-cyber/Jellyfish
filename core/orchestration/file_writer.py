"""core/orchestration/file_writer.py — Lógica desacoplada de extracción y escritura de archivos."""

import os
import re
import logging
from rich.console import Console

logger = logging.getLogger("jellyfish.orchestration.file_writer")
console = Console()

def extract_and_write_files(project_path: str, content: str) -> list[str]:
    """Extrae y escribe en disco los archivos de código real desde el contenido generado."""
    created_files = []
    
    xml_matches = re.findall(r'<write_file\s+path="([^"]+)">\s*\n?(.*?)\s*\n?</write_file>', content, re.DOTALL)
    for rel_path, file_content in xml_matches:
        clean_rel_path = rel_path.strip().replace("`", "")
        full_path = os.path.join(project_path, clean_rel_path)
        try:
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(file_content)
            created_files.append(clean_rel_path)
        except Exception as e:
            console.print(f"       ✗ Error creando archivo {clean_rel_path}: {e}")
            logger.error("Error al escribir archivo real de agente: %s", e)

    md_matches = re.findall(r'\[WRITE_FILE:\s*([^\]\s]+)\]\s*\n*```[a-zA-Z0-9_-]*\n(.*?)\n```', content, re.DOTALL)
    for rel_path, file_content in md_matches:
        rel_clean = rel_path.strip().replace("`", "")
        if rel_clean in created_files:
            continue
        full_path = os.path.join(project_path, rel_clean)
        try:
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(file_content)
            created_files.append(rel_clean)
        except Exception as e:
            console.print(f"       ✗ Error creando archivo {rel_clean}: {e}")
            logger.error("Error al escribir archivo real de agente: %s", e)
            
    return created_files
