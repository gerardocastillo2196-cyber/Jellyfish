"""core/orchestration/file_writer.py — Lógica desacoplada de extracción y escritura de archivos."""

import os
import re
import logging
from rich.console import Console

logger = logging.getLogger("jellyfish.orchestration.file_writer")
console = Console()

def apply_patches_from_content(project_path: str, content: str) -> list[str]:
    """Busca bloques de parche SEARCH/REPLACE en el contenido y los aplica en el disco duro."""
    patched_files = []
    
    # 1. Buscar etiquetas <patch_file path="...">
    patch_matches = re.findall(r'<patch_file\s+path="([^"]+)">\s*\n?(.*?)\s*\n?</patch_file>', content, re.DOTALL)
    
    # 2. Buscar formato [PATCH_FILE: ...]
    md_patch_matches = re.findall(r'\[PATCH_FILE:\s*([^\]\s]+)\]\s*\n*```[a-zA-Z0-9_-]*\n(.*?)\n```', content, re.DOTALL)
    
    all_patches = patch_matches + md_patch_matches
    
    for rel_path, patch_block in all_patches:
        clean_rel_path = rel_path.strip().replace("`", "")
        full_path = os.path.join(project_path, clean_rel_path)
        
        if not os.path.exists(full_path):
            console.print(f"       ✗ Error al aplicar parche: El archivo {clean_rel_path} no existe.")
            continue
            
        try:
            with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                file_text = f.read()
        except Exception as e:
            console.print(f"       ✗ Error leyendo {clean_rel_path}: {e}")
            continue
            
        blocks = re.findall(r'<<<<<<< SEARCH\n?(.*?)\n?=======\n?(.*?)\n?>>>>>>> REPLACE', patch_block, re.DOTALL)
        if not blocks:
            blocks = re.findall(r'<<<<<<< SEARCH(.*?)=======(.*?)>>>>>>> REPLACE', patch_block, re.DOTALL)
            
        if not blocks:
            console.print(f"       ✗ No se encontraron bloques SEARCH/REPLACE válidos para {clean_rel_path}.")
            continue
            
        modified = False
        temp_text = file_text
        for search_text, replace_text in blocks:
            search_clean = search_text.strip()
            if search_clean in temp_text:
                temp_text = temp_text.replace(search_clean, replace_text.strip())
                modified = True
            elif search_text in temp_text:
                temp_text = temp_text.replace(search_text, replace_text)
                modified = True
            else:
                console.print(f"       ⚠ Coincidencia SEARCH no encontrada en {clean_rel_path}.")
                
        if modified:
            try:
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(temp_text)
                patched_files.append(clean_rel_path)
                console.print(f"       [bold green]✓[/bold green] [green]Parche aplicado exitosamente en {clean_rel_path}[/green]")
            except Exception as e:
                console.print(f"       ✗ Error escribiendo {clean_rel_path}: {e}")
                
    return patched_files

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
            
    # Integrar aplicación de parches parciales
    patched = apply_patches_from_content(project_path, content)
    created_files.extend(patched)
            
    return created_files
