# --- Parche de compatibilidad para sqlite3 en entornos con versión antigua ---
try:
    import sys
    import pysqlite3
    sys.modules["sqlite3"] = pysqlite3
except ImportError:
    pass

import os
import ast
import uuid
import shutil
import hashlib
import logging
from typing import Optional, List, Tuple
from fnmatch import fnmatch

from langchain_text_splitters import RecursiveCharacterTextSplitter, Language
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings
from rich.console import Console

from core.state import RELEVANCE_THRESHOLD, EMBED_MODEL, ACTIVE_PROJECT

logger = logging.getLogger("jellyfish.rag")
console = Console()

# Mapa de extensiones soportadas → Language de LangChain
_EXT_MAP = {
    # Python
    ".py": Language.PYTHON,
    # JavaScript / TypeScript
    ".js": Language.JS,
    ".ts": Language.TS,
    ".tsx": Language.TS,
    ".jsx": Language.JS,
    # Web
    ".html": Language.HTML,
    ".css": Language.HTML,
    # Markup / Config
    ".md": Language.MARKDOWN,
    ".sh": Language.MARKDOWN,
    ".bash": Language.MARKDOWN,
    ".yaml": Language.MARKDOWN,
    ".yml": Language.MARKDOWN,
    ".json": Language.MARKDOWN,
    ".toml": Language.MARKDOWN,
    # Go
    ".go": Language.GO,
    # Rust
    ".rs": Language.RUST,
    # Java / Kotlin
    ".java": Language.JAVA,
    ".kt": Language.KOTLIN,
    # C / C++
    ".c": Language.C,
    ".h": Language.C,
    ".cpp": Language.CPP,
    ".hpp": Language.CPP,
    ".cc": Language.CPP,
    # C#
    ".cs": Language.CSHARP,
    # Ruby
    ".rb": Language.RUBY,
    # PHP
    ".php": Language.PHP,
    # Scala
    ".scala": Language.SCALA,
    # Swift
    ".swift": Language.SWIFT,
    # Lua
    ".lua": Language.LUA,
}

# Directorios que nunca se deben indexar
_IGNORE_DIRS = {
    "venv", ".git", "__pycache__", "node_modules", "code_vector_db",
    "test_db", ".next", "dist", "build", ".venv", "env", ".tox",
    "htmlcov", ".mypy_cache", ".pytest_cache", "eggs", "*.egg-info",
}


# ---------------------------------------------------------------------------
# Sprint 2.4 — UUID blindado para delimitadores RAG
# Usamos un prefijo UUID fijo por sesión que el código fuente de usuario
# jamás puede adivinar ni reproducir, previniendo inyecciones de prompt.
# ---------------------------------------------------------------------------
_RAG_SESSION_UUID = uuid.uuid4().hex[:12].upper()
_RAG_OPEN  = f"<RAG_CTX_{_RAG_SESSION_UUID}>"
_RAG_CLOSE = f"</RAG_CTX_{_RAG_SESSION_UUID}>"
_FRAG_OPEN = f"<FRAG_{_RAG_SESSION_UUID}"
_FRAG_CLOSE = f"</FRAG_{_RAG_SESSION_UUID}>"


def refresh_session_uuid() -> None:
    """Regenera los delimitadores RAG con un nuevo UUID.

    Sprint 8.0 — Llamar antes de cada consulta para que el UUID
    cambie criptográficamente en cada interacción, haciendo imposible
    que código fuente malicioso prediga los delimitadores.
    """
    global _RAG_SESSION_UUID, _RAG_OPEN, _RAG_CLOSE, _FRAG_OPEN, _FRAG_CLOSE
    _RAG_SESSION_UUID = uuid.uuid4().hex[:12].upper()
    _RAG_OPEN  = f"<RAG_CTX_{_RAG_SESSION_UUID}>"
    _RAG_CLOSE = f"</RAG_CTX_{_RAG_SESSION_UUID}>"
    _FRAG_OPEN = f"<FRAG_{_RAG_SESSION_UUID}"
    _FRAG_CLOSE = f"</FRAG_{_RAG_SESSION_UUID}>"


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
            logger.info("Cargados %d patrones desde .jellyfishignore", len(patterns))
        except (OSError, IOError) as e:
            logger.warning("Error leyendo .jellyfishignore: %s", e)
    return patterns


def _should_ignore(path: str, patterns: List[str]) -> bool:
    """Verifica si una ruta coincide con algún patrón de ignorar."""
    basename = os.path.basename(path)
    for pattern in patterns:
        if fnmatch(basename, pattern) or fnmatch(path, pattern):
            return True
    return False


def _file_hash(filepath: str) -> str:
    """Genera un hash MD5 del contenido de un archivo para deduplicación."""
    hasher = hashlib.md5()
    try:
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
    except (OSError, IOError):
        return ""
    return hasher.hexdigest()


def _dir_hash(dirpath: str) -> str:
    """Genera un hash SHA1 corto basado en la ruta absoluta del directorio.

    Sprint 2.3 — Permite generar un DB_PATH único por proyecto indexado,
    evitando que proyectos distintos mezclen sus vectores en la misma base.
    """
    return hashlib.sha1(os.path.abspath(dirpath).encode()).hexdigest()[:10]


# ---------------------------------------------------------------------------
# Sprint 2.2 — Splitter inteligente con fallback AST para Python
# ---------------------------------------------------------------------------

def _split_python_ast(text: str, filepath: str) -> List[str]:
    """Divide código Python respetando límites de funciones/clases mediante AST.

    Si el parseo AST falla (código inválido), cae al splitter de LangChain estándar.

    Sprint 2.2 — Garantiza que nunca se parta una función por la mitad.
    """
    try:
        tree = ast.parse(text)
    except SyntaxError:
        logger.debug("AST parse falló en %s, usando splitter estándar.", filepath)
        return None  # señal de fallback

    lines = text.splitlines(keepends=True)
    chunks: List[str] = []
    last_end = 0

    top_level = [
        node for node in ast.iter_child_nodes(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    ]

    for node in top_level:
        start = node.lineno - 1
        end = node.end_lineno

        # Capturar cualquier texto suelto antes de este nodo
        interstitial = "".join(lines[last_end:start]).strip()
        if len(interstitial) > 2400:
            sub_splitter = RecursiveCharacterTextSplitter.from_language(
                language=Language.PYTHON, chunk_size=1200, chunk_overlap=150
            )
            chunks.extend(sub_splitter.split_text(interstitial))
        elif interstitial:
            chunks.append(interstitial)

        block = "".join(lines[start:end])
        # Si el bloque es muy grande, sub-dividir con el splitter estándar
        if len(block) > 2400:
            sub_splitter = RecursiveCharacterTextSplitter.from_language(
                language=Language.PYTHON, chunk_size=1200, chunk_overlap=150
            )
            chunks.extend(sub_splitter.split_text(block))
        elif block.strip():
            chunks.append(block)

        last_end = end

    # Capturar código restante después del último nodo
    tail = "".join(lines[last_end:]).strip()
    if len(tail) > 2400:
        sub_splitter = RecursiveCharacterTextSplitter.from_language(
            language=Language.PYTHON, chunk_size=1200, chunk_overlap=150
        )
        chunks.extend(sub_splitter.split_text(tail))
    elif tail:
        chunks.append(tail)

    return chunks if chunks else None


def _split_file(text: str, ext: str, filepath: str) -> List[str]:
    """Selecciona el mejor splitter para la extensión dada.

    Sprint 2.2 — Python usa el splitter AST-aware; otros lenguajes usan
    el splitter semántico de LangChain (que respeta delimitadores del lenguaje).
    """
    if ext == ".py":
        ast_chunks = _split_python_ast(text, filepath)
        if ast_chunks:
            return ast_chunks

    # Fallback universal: LangChain RecursiveCharacterTextSplitter
    splitter = RecursiveCharacterTextSplitter.from_language(
        language=_EXT_MAP[ext],
        chunk_size=1200,
        chunk_overlap=150,
    )
    return splitter.split_text(text)


class CodeKnowledgeBase:
    """Motor RAG para análisis de código fuente.

    Sprint 2.2: Splitter AST-aware para Python.
    Sprint 2.3: DB_PATH aislado por proyecto (hash de directorio).
    Sprint 2.4: Delimitadores UUID blindados anti-inyección de prompt.
    """

    def __init__(self, db_path: str, active_project: str = "", ollama_connected: bool = True):
        self.db_base_path = db_path   # Ruta base; la DB real incluirá el hash del proyecto
        self.db_path = db_path        # Se actualiza en index_codebase() o al cargar proyecto activo
        self.ollama_connected = ollama_connected
        self.vector_db: Optional[Chroma] = None
        self.indexed_file_count: int = 0
        self.indexed_chunk_count: int = 0
        self.indexed_dir: str = ""    # Directorio actualmente indexado
        self.enabled: bool = True     # Permite apagar el RAG sin borrar la base de datos

        if self.ollama_connected:
            try:
                self.embeddings = OllamaEmbeddings(model=EMBED_MODEL)
            except Exception as e:
                logger.warning("Error inicializando embeddings de Ollama: %s", e)
                self.ollama_connected = False
                self.embeddings = None
        else:
            self.embeddings = None

        project_path = active_project or ACTIVE_PROJECT
        if project_path:
            self.indexed_dir = os.path.abspath(os.path.expanduser(project_path))
            self.db_path = f"{self.db_base_path}_{_dir_hash(self.indexed_dir)}"

        # Intentar cargar base existente con auto-recovery
        if self.ollama_connected:
            self._try_load_existing_db()
        else:
            logger.warning("RAG inactivo debido a que Ollama está desconectado.")

    def set_active_project(self, project_path: str) -> None:
        """Cambia el proyecto activo del RAG, recargando o limpiando la base de datos según corresponda."""
        self._close_db()
        if project_path:
            self.indexed_dir = os.path.abspath(os.path.expanduser(project_path))
            self.db_path = f"{self.db_base_path}_{_dir_hash(self.indexed_dir)}"
            if self.ollama_connected:
                self._try_load_existing_db()
        else:
            self.indexed_dir = ""
            self.db_path = self.db_base_path
            self.vector_db = None
            self.indexed_file_count = 0
            self.indexed_chunk_count = 0

    def _try_load_existing_db(self) -> None:
        """Intenta cargar la base de datos vectorial existente."""
        if not os.path.exists(self.db_path) or not os.listdir(self.db_path):
            return

        try:
            self.vector_db = Chroma(
                persist_directory=self.db_path,
                embedding_function=self.embeddings
            )
            collection = self.vector_db._collection
            self.indexed_chunk_count = collection.count()
            try:
                data = collection.get(include=["metadatas"])
                sources = {
                    meta.get("source") or meta.get("relative_path")
                    for meta in data.get("metadatas", [])
                    if meta
                }
                self.indexed_file_count = len(sources)
            except Exception:
                self.indexed_file_count = 0
            logger.info("RAG cargado: %d chunks en la base vectorial.", self.indexed_chunk_count)
        except Exception as e:
            logger.warning("Base RAG corrupta, eliminando automáticamente: %s", e)
            self._close_db()
            try:
                shutil.rmtree(self.db_path)
                console.print(
                    "⚠ Base RAG corrupta detectada y eliminada. "
                    "Usa /add para reindexar."
                )
            except (OSError, IOError) as rm_err:
                logger.error("Error eliminando base corrupta: %s", rm_err)

    def _close_db(self) -> None:
        """Cierra de forma limpia la conexión de ChromaDB y libera recursos."""
        if self.vector_db:
            try:
                if hasattr(self.vector_db, "_client") and hasattr(self.vector_db._client, "close"):
                    self.vector_db._client.close()
            except Exception as e:
                logger.warning("Error cerrando cliente RAG: %s", e)
            self.vector_db = None
            import gc
            gc.collect()

    def index_codebase(self, path: str) -> int:
        """Indexa un directorio de código fuente completo.

        Sprint 2.3 — La base de datos vectorial se crea en una ruta única
        derivada del hash SHA1 del directorio raíz, aislando proyectos distintos.

        Args:
            path: Ruta al directorio a indexar.

        Returns:
            Número de chunks procesados.
        """
        if not self.ollama_connected:
            console.print("⚠ Error: RAG no disponible. Ollama está desconectado.")
            return 0
        abs_path = os.path.abspath(path)
        project_hash = _dir_hash(abs_path)

        # Sprint 2.3: DB aislada por proyecto
        self.db_path = f"{self.db_base_path}_{project_hash}"
        self.indexed_dir = abs_path

        console.print(
            f"🔍 Indexando código en: {path} "
            f"[dim](DB: {os.path.basename(self.db_path)})[/dim]"
        )

        ignore_patterns = _load_jellyfishignore(path)
        all_chunks: List[str] = []
        all_metadatas: List[dict] = []
        files_processed = 0

        for root, dirs, files in os.walk(path):
            dirs[:] = [
                d for d in dirs
                if d not in _IGNORE_DIRS
                and not d.startswith(".")
                and not _should_ignore(d, ignore_patterns)
            ]

            for filename in files:
                ext = os.path.splitext(filename)[1].lower()
                if ext not in _EXT_MAP:
                    continue

                file_path = os.path.join(root, filename)
                rel_path = os.path.relpath(file_path, path)

                if _should_ignore(rel_path, ignore_patterns):
                    continue

                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        text = f.read()

                    if not text.strip():
                        continue

                    # Sprint 2.2: Splitter inteligente (AST para Python, estándar para el resto)
                    chunks = _split_file(text, ext, file_path)

                    fhash = _file_hash(file_path)
                    for chunk in chunks:
                        all_chunks.append(chunk)
                        all_metadatas.append({
                            "source": file_path,
                            "relative_path": rel_path,
                            "extension": ext,
                            "filename": filename,
                            "file_hash": fhash,
                        })

                    files_processed += 1
                    logger.info("✓ %s (%d chunks)", rel_path, len(chunks))

                except Exception as e:
                    logger.warning("Error indexando %s: %s", filename, e)

        if not all_chunks:
            console.print("⚠ No se encontraron archivos compatibles para indexar.")
            return 0

        try:
            batch_size = 15
            total_chunks = len(all_chunks)

            logger.info("📦 Preparando %d fragmentos para indexación...", total_chunks)

            self._close_db()
            self.vector_db = Chroma(
                persist_directory=self.db_path,
                embedding_function=self.embeddings
            )

            from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeRemainingColumn
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                TimeRemainingColumn(),
                console=console
            ) as progress:
                task = progress.add_task("[cyan]Generando embeddings...", total=total_chunks)

                for i in range(0, total_chunks, batch_size):
                    batch_chunks = all_chunks[i:i + batch_size]
                    batch_metadatas = all_metadatas[i:i + batch_size]
                    self.vector_db.add_texts(texts=batch_chunks, metadatas=batch_metadatas)
    
                    current_count = min(i + batch_size, total_chunks)
                    percent = int((current_count / total_chunks) * 100)
                    logger.info(
                        "⚡ Generando embeddings: %d/%d (%d%%) ...",
                        current_count, total_chunks, percent
                    )
                    progress.update(task, advance=len(batch_chunks))

            collection = self.vector_db._collection
            self.indexed_chunk_count = collection.count()
            self.indexed_file_count = files_processed
            console.print(
                f"✓ Indexación completada: "
                f"{files_processed} archivos → {self.indexed_chunk_count} fragmentos"
            )
        except Exception as e:
            console.print(f"Error creando la base vectorial: {e}")
            logger.error("Error en Chroma.add_texts: %s", e)
            return 0

        return self.indexed_chunk_count

    def query_code(self, question: str, k: int = 4) -> str:
        """Busca fragmentos de código relevantes para una pregunta.

        Sprint 2.4 — Usa delimitadores UUID únicos por sesión en lugar de
        etiquetas XML genéricas, previniendo que código fuente malicioso
        dentro del proyecto pueda inyectar instrucciones al LLM.

        Args:
            question: La pregunta del usuario.
            k: Número máximo de resultados a recuperar.

        Returns:
            Contexto formateado con UUID blindado, o cadena vacía si no hay resultados.
        """
        if not self.vector_db:
            return ""

        # Sprint 8.0 — Refrescar UUID por consulta para máxima seguridad anti-inyección
        refresh_session_uuid()

        try:
            results_with_scores: List[Tuple] = self.vector_db.similarity_search_with_score(
                question, k=k
            )
        except Exception as e:
            logger.warning("Error en query RAG: %s", e)
            return ""

        if not results_with_scores:
            return ""

        try:
            threshold = float(os.getenv("JELLYFISH_RAG_THRESHOLD", str(RELEVANCE_THRESHOLD)))
        except ValueError:
            threshold = RELEVANCE_THRESHOLD

        relevant = [
            (doc, score) for doc, score in results_with_scores
            if score <= threshold
        ]

        if not relevant:
            return ""

        # Sprint 8.0 — Delimitadores UUID blindados (refrescados por consulta)
        context_parts = [_RAG_OPEN]
        seen_content: set = set()

        for doc, score in relevant:
            content_hash = hash(doc.page_content.strip())
            if content_hash in seen_content:
                continue
            seen_content.add(content_hash)

            source = doc.metadata.get("relative_path", doc.metadata.get("source", "desconocido"))
            # Sprint 8.0 — Calcular porcentaje de relevancia para visibilidad
            relevance_pct = max(0, int((1.0 - score / threshold) * 100))
            context_parts.append(
                f'  {_FRAG_OPEN} source="{source}" relevance="{score:.3f}" match="{relevance_pct}%">\n'
                f'{doc.page_content}\n'
                f'  {_FRAG_CLOSE}'
            )

        context_parts.append(_RAG_CLOSE)
        return "\n".join(context_parts)

    def remove_path(self, target_path: str) -> int:
        """Elimina documentos de una ruta específica de la base RAG."""
        if not self.vector_db:
            console.print("⚠ No hay índice RAG activo.")
            return 0

        try:
            collection = self.vector_db._collection
            results = collection.get(where={"source": {"$eq": os.path.abspath(target_path)}})

            if not results["ids"]:
                all_data = collection.get()
                ids_to_delete = []
                abs_target = os.path.abspath(target_path)
                for doc_id, metadata in zip(all_data["ids"], all_data["metadatas"]):
                    source = metadata.get("source", "")
                    if source.startswith(abs_target):
                        ids_to_delete.append(doc_id)

                if ids_to_delete:
                    collection.delete(ids=ids_to_delete)
                    self.indexed_chunk_count = collection.count()
                    console.print(f"✓ {len(ids_to_delete)} chunks eliminados de {target_path}")
                    return len(ids_to_delete)
                else:
                    console.print(f"No se encontraron documentos para: {target_path}")
                    return 0
            else:
                collection.delete(ids=results["ids"])
                self.indexed_chunk_count = collection.count()
                console.print(f"✓ {len(results['ids'])} chunks eliminados.")
                return len(results["ids"])

        except Exception as e:
            logger.error("Error eliminando de RAG: %s", e)
            console.print(f"Error eliminando de RAG: {e}")
            return 0

    def clear_index(self) -> None:
        """Elimina la base vectorial por completo."""
        self._close_db()
        if os.path.exists(self.db_path):
            try:
                shutil.rmtree(self.db_path)
                self.indexed_file_count = 0
                self.indexed_chunk_count = 0
                console.print("☢ Índice RAG eliminado.")
            except Exception as e:
                logger.error("Error eliminando índice RAG: %s", e)

    def reindex(self) -> None:
        """Reindexa el directorio actual de código fuente, limpiando previamente el índice."""
        target = self.indexed_dir
        if not target:
            from core.state import ACTIVE_PROJECT
            target = ACTIVE_PROJECT
        if not target:
            raise ValueError("No hay ningún proyecto o directorio activo para reindexar.")
        self.clear_index()
        self.index_codebase(target)

    @property
    def is_active(self) -> bool:
        """Indica si hay una base vectorial cargada y el RAG está habilitado."""
        return self.enabled and self.vector_db is not None and self.indexed_chunk_count > 0

    @property
    def status_text(self) -> str:
        """Texto de estado para la barra del header."""
        if not self.ollama_connected:
            return "RAG[ERR]"
        if not self.enabled:
            return "RAG[OFF]"
        if self.is_active:
            return f"RAG[{self.indexed_chunk_count}]"
        return "RAG[OFF]"
