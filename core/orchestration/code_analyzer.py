"""core.orchestration.code_analyzer — Análisis programático de código sin LLM.

Extrae metadatos estructurados (clases, funciones, imports, endpoints)
de archivos de código usando ast (Python) y expresiones regulares
(JS, TS, Dart, Java, Go, HTML, CSS, etc.).

Beneficio: Genera resúmenes técnicos para DEVELOPMENT_LOG.md sin
consumir un solo token del LLM.

Referencia de acoplamiento:
    - core/orchestration/task_runner.py → llama analyze_file() tras cada tarea
    - DEVELOPMENT_LOG.md → recibe la estructura extraída como bitácora
"""

import ast
import os
import re
import logging
from typing import Optional

logger = logging.getLogger("jellyfish.orchestration.code_analyzer")


def analyze_file(filepath: str) -> dict:
    """Extrae metadatos estructurados de un archivo de código.

    Usa ast.parse() para Python y expresiones regulares para otros
    lenguajes. No consume tokens del LLM.

    Args:
        filepath: Ruta absoluta al archivo de código.

    Returns:
        Diccionario con claves:
        - language: str (python, javascript, typescript, dart, java, etc.)
        - classes: list[str] — nombres de clases definidas
        - functions: list[str] — nombres de funciones/métodos definidos
        - imports: list[str] — módulos importados
        - endpoints: list[str] — rutas de API detectadas
        - error: Optional[str] — mensaje de error si el análisis falla
    """
    result = {
        "language": "unknown",
        "classes": [],
        "functions": [],
        "imports": [],
        "endpoints": [],
        "error": None,
    }

    if not os.path.isfile(filepath):
        result["error"] = f"Archivo no encontrado: {filepath}"
        return result

    ext = os.path.splitext(filepath)[1].lower()

    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except (OSError, IOError) as e:
        result["error"] = str(e)
        return result

    if not content.strip():
        result["error"] = "Archivo vacío"
        return result

    if ext == ".py":
        return _analyze_python(content, result)
    elif ext in (".js", ".jsx", ".mjs"):
        return _analyze_javascript(content, result, "javascript")
    elif ext in (".ts", ".tsx"):
        return _analyze_javascript(content, result, "typescript")
    elif ext == ".dart":
        return _analyze_dart(content, result)
    elif ext in (".java", ".kt"):
        return _analyze_java_kotlin(content, result, "java" if ext == ".java" else "kotlin")
    elif ext == ".go":
        return _analyze_go(content, result)
    elif ext in (".html", ".htm"):
        return _analyze_html(content, result)
    elif ext == ".css":
        return _analyze_css(content, result)
    else:
        # Fallback genérico: intentar detectar definiciones
        return _analyze_generic(content, result, ext)


def _analyze_python(content: str, result: dict) -> dict:
    """Análisis de Python usando la biblioteca estándar ast."""
    result["language"] = "python"
    try:
        tree = ast.parse(content)
    except SyntaxError as e:
        result["error"] = f"SyntaxError: {e}"
        # Intentar extraer algo por regex incluso con errores de sintaxis
        result["classes"] = re.findall(r'^class\s+(\w+)', content, re.MULTILINE)
        result["functions"] = re.findall(r'^def\s+(\w+)', content, re.MULTILINE)
        return result

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            result["classes"].append(node.name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Solo funciones top-level y métodos de primer nivel
            result["functions"].append(node.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                result["imports"].append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                result["imports"].append(node.module)

    # Detectar endpoints Flask/FastAPI/Django
    endpoint_patterns = [
        r'@app\.\w+\(["\']([^"\']+)',        # Flask/FastAPI: @app.get("/path")
        r'@router\.\w+\(["\']([^"\']+)',      # FastAPI router
        r"path\(['\"]([^'\"]+)",              # Django: path("url/")
        r"url\(['\"]([^'\"]+)",              # Django legacy
    ]
    for pattern in endpoint_patterns:
        result["endpoints"].extend(re.findall(pattern, content))

    # Deduplicar
    result["imports"] = list(dict.fromkeys(result["imports"]))
    return result


def _analyze_javascript(content: str, result: dict, lang: str) -> dict:
    """Análisis de JavaScript/TypeScript con regex."""
    result["language"] = lang

    # Clases
    result["classes"] = re.findall(r'class\s+(\w+)', content)

    # Funciones (declaraciones, exports, arrow functions con nombre)
    func_patterns = [
        r'function\s+(\w+)',                          # function name()
        r'(?:export\s+)?(?:async\s+)?function\s+(\w+)',  # export function
        r'(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\(',  # const name = (
        r'(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\w*\s*=>\s*',  # const name = () =>
    ]
    all_funcs = set()
    for pattern in func_patterns:
        all_funcs.update(re.findall(pattern, content))
    result["functions"] = list(all_funcs)

    # Imports
    import_patterns = [
        r'import\s+.*?from\s+["\']([^"\']+)',   # import X from 'module'
        r'require\(["\']([^"\']+)',               # require('module')
    ]
    all_imports = set()
    for pattern in import_patterns:
        all_imports.update(re.findall(pattern, content))
    result["imports"] = list(all_imports)

    # Endpoints (Express, Koa, Hono, etc.)
    endpoint_patterns = [
        r'(?:app|router)\.(get|post|put|patch|delete)\(["\']([^"\']+)',
    ]
    for pattern in endpoint_patterns:
        matches = re.findall(pattern, content)
        result["endpoints"].extend(f"{method.upper()} {path}" for method, path in matches)

    return result


def _analyze_dart(content: str, result: dict) -> dict:
    """Análisis de Dart con regex."""
    result["language"] = "dart"

    result["classes"] = re.findall(r'class\s+(\w+)', content)

    # Funciones y métodos Dart
    func_pattern = r'(?:(?:static|async|Future|void|String|int|double|bool|List|Map|dynamic)\s+)+(\w+)\s*\('
    result["functions"] = re.findall(func_pattern, content)

    # Imports
    result["imports"] = re.findall(r"import\s+['\"]([^'\"]+)", content)

    return result


def _analyze_java_kotlin(content: str, result: dict, lang: str) -> dict:
    """Análisis de Java/Kotlin con regex."""
    result["language"] = lang

    result["classes"] = re.findall(r'(?:class|interface|enum)\s+(\w+)', content)

    # Métodos
    method_pattern = r'(?:public|private|protected|internal|static|suspend|override|fun|void|String|int|boolean|long|double)\s+(?:\w+\s+)*(\w+)\s*\('
    result["functions"] = re.findall(method_pattern, content)

    # Imports
    result["imports"] = re.findall(r'import\s+([\w.]+)', content)

    # Endpoints Spring Boot
    endpoint_patterns = [
        r'@(?:Get|Post|Put|Delete|Patch)Mapping\(["\']([^"\']+)',
        r'@RequestMapping\(["\']([^"\']+)',
    ]
    for pattern in endpoint_patterns:
        result["endpoints"].extend(re.findall(pattern, content))

    return result


def _analyze_go(content: str, result: dict) -> dict:
    """Análisis de Go con regex."""
    result["language"] = "go"

    # Structs (equivalente a clases en Go)
    result["classes"] = re.findall(r'type\s+(\w+)\s+struct', content)

    # Funciones
    result["functions"] = re.findall(r'func\s+(?:\(\w+\s+\*?\w+\)\s+)?(\w+)\s*\(', content)

    # Imports
    result["imports"] = re.findall(r'"([\w/.-]+)"', content)

    # Endpoints (net/http, Gin, Echo, Fiber)
    endpoint_patterns = [
        r'\.(?:GET|POST|PUT|DELETE|PATCH)\(["\']([^"\']+)',
        r'HandleFunc\(["\']([^"\']+)',
        r'\.Handle\(["\']([^"\']+)',
    ]
    for pattern in endpoint_patterns:
        result["endpoints"].extend(re.findall(pattern, content))

    return result


def _analyze_html(content: str, result: dict) -> dict:
    """Análisis de HTML con regex."""
    result["language"] = "html"

    # Tags principales
    result["classes"] = re.findall(r'id=["\']([^"\']+)', content)
    # Clases CSS usadas
    css_classes = re.findall(r'class=["\']([^"\']+)', content)
    result["functions"] = list(set(
        cls for classes_str in css_classes
        for cls in classes_str.split()
    ))[:20]  # Limitar para no sobrecargar

    # Scripts y stylesheets importados
    result["imports"] = re.findall(r'(?:src|href)=["\']([^"\']+)', content)

    return result


def _analyze_css(content: str, result: dict) -> dict:
    """Análisis de CSS con regex."""
    result["language"] = "css"

    # Selectores de clase
    result["classes"] = list(set(re.findall(r'\.([a-zA-Z_][\w-]*)\s*\{', content)))[:30]

    # IDs
    result["functions"] = list(set(re.findall(r'#([a-zA-Z_][\w-]*)\s*\{', content)))[:20]

    # @imports
    result["imports"] = re.findall(r'@import\s+["\']([^"\']+)', content)

    return result


def _analyze_generic(content: str, result: dict, ext: str) -> dict:
    """Análisis genérico con heurísticas para archivos de tipo desconocido."""
    result["language"] = ext.lstrip(".")

    # Intentar encontrar definiciones tipo class/function/def
    result["classes"] = re.findall(r'(?:class|struct|interface|type)\s+(\w+)', content)
    result["functions"] = re.findall(r'(?:function|func|def|fn|sub|proc)\s+(\w+)', content)
    result["imports"] = re.findall(r'(?:import|require|include|use)\s+["\']?([^\s"\';\n]+)', content)

    return result


def format_analysis_for_log(
    task_id: str,
    agent_name: str,
    task_desc: str,
    created_files: list[str],
    project_path: str,
    semantic_summary: str = "",
) -> str:
    """Formatea los resultados del análisis de código para DEVELOPMENT_LOG.md.

    Analiza cada archivo creado/modificado y genera una entrada Markdown
    estructurada lista para agregar a la bitácora.

    Args:
        task_id: ID de la tarea (ej: "T-003").
        agent_name: Nombre del agente que ejecutó la tarea.
        task_desc: Descripción de la tarea.
        created_files: Lista de rutas relativas de archivos creados.
        project_path: Ruta absoluta del proyecto.
        semantic_summary: Resumen semántico opcional del LLM (1 oración).

    Returns:
        Bloque Markdown listo para append a DEVELOPMENT_LOG.md.
    """
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    parts = [
        f"### [{timestamp}] {task_id} — @{agent_name}",
        f"**Tarea:** {task_desc}",
    ]

    if created_files:
        files_str = ", ".join(f"`{f}`" for f in created_files[:10])
        parts.append(f"**Archivos:** {files_str}")

    # Analizar cada archivo
    all_classes = []
    all_functions = []
    all_imports = []
    all_endpoints = []

    for rel_path in created_files:
        abs_path = os.path.join(project_path, rel_path)
        analysis = analyze_file(abs_path)

        if analysis.get("error"):
            continue

        all_classes.extend(analysis.get("classes", []))
        all_functions.extend(analysis.get("functions", []))
        all_imports.extend(analysis.get("imports", []))
        all_endpoints.extend(analysis.get("endpoints", []))

    # Deduplicar
    all_classes = list(dict.fromkeys(all_classes))
    all_functions = list(dict.fromkeys(all_functions))
    all_imports = list(dict.fromkeys(all_imports))
    all_endpoints = list(dict.fromkeys(all_endpoints))

    if all_classes or all_functions or all_imports:
        parts.append("**Estructura detectada (análisis programático):**")
        if all_classes:
            parts.append(f"- Clases: {', '.join(f'`{c}`' for c in all_classes[:15])}")
        if all_functions:
            parts.append(f"- Funciones: {', '.join(f'`{f}`' for f in all_functions[:20])}")
        if all_imports:
            parts.append(f"- Imports: {', '.join(f'`{i}`' for i in all_imports[:15])}")
        if all_endpoints:
            parts.append(f"- Endpoints: {', '.join(f'`{e}`' for e in all_endpoints[:10])}")

    if semantic_summary:
        parts.append(f"**Resumen:** {semantic_summary}")

    parts.append("")  # línea vacía al final
    return "\n".join(parts)
