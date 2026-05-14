try:
    import sys
    import pysqlite3
    sys.modules["sqlite3"] = pysqlite3
except ImportError:
    pass

import os
from langchain_text_splitters import RecursiveCharacterTextSplitter, Language
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import OllamaEmbeddings
from rich.console import Console

console = Console()

class CodeKnowledgeBase:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.embeddings = OllamaEmbeddings(model="nomic-embed-text")
        self.vector_db = None
        # Intentar cargar si existe
        if os.path.exists(db_path):
            self.vector_db = Chroma(persist_directory=db_path, embedding_function=self.embeddings)

    def index_codebase(self, path: str) -> None:
        console.print(f"[bold blue]🔍 Iniciando indexación consciente de sintaxis en:[/bold blue] {path}")
        
        all_chunks = []
        all_metadatas = []
        
        # Extensiones soportadas y su mapeo a LangChain Language
        ext_map = {
            ".py": Language.PYTHON,
            ".js": Language.JS,
            ".html": Language.HTML,
            ".md": Language.MARKDOWN
        }

        for root, _, files in os.walk(path):
            if any(x in root for x in ["venv", ".git", "__pycache__", "code_vector_db"]): continue
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in ext_map:
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, "r", encoding='utf-8', errors='ignore') as f:
                            text = f.read()
                        
                        splitter = RecursiveCharacterTextSplitter.from_language(
                            language=ext_map[ext],
                            chunk_size=1000,
                            chunk_overlap=100
                        )
                        chunks = splitter.split_text(text)
                        all_chunks.extend(chunks)
                        all_metadatas.extend([{"source": file_path} for _ in chunks])
                        console.print(f"  [dim]Indexado: {file}[/dim]")
                    except Exception as e:
                        console.print(f"[red]Error indexando {file}: {e}[/red]")

        if all_chunks:
            self.vector_db = Chroma.from_texts(
                texts=all_chunks,
                metadatas=all_metadatas,
                embedding=self.embeddings,
                persist_directory=self.db_path
            )
            console.print(f"[bold green]✓ Indexación completada. {len(all_chunks)} fragmentos procesados.[/bold green]")
        else:
            console.print("[yellow]Aviso: No se encontraron archivos compatibles para indexar.[/yellow]")

    def query_code(self, question: str) -> str:
        if not self.vector_db:
            return ""
        
        results = self.vector_db.similarity_search(question, k=4)
        if not results:
            return ""

        context = "\n[CONTEXTO TÉCNICO RECUPERADO (RAG)]\n"
        for doc in results:
            source = doc.metadata.get("source", "Desconocido")
            context += f"--- Archivo: {source} ---\n{doc.page_content}\n\n"
        return context
