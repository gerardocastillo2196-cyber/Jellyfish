import pytest
from unittest.mock import MagicMock, patch
from core.local_transformers import local_ai_manager, LocalTransformersManager
from core.orchestration.product_owner import ProductOwnerPhase

def test_tag_backlog_item_heuristics():
    # Cuando el pipeline zero-shot no está cargado en RAM/offline, actúa la heurística ultra rápida
    tags_sec = local_ai_manager.tag_backlog_item("Implementar sistema de seguridad y tokens JWT en el login")
    assert "Security" in tags_sec

    tags_front = local_ai_manager.tag_backlog_item("Diseñar interfaz UI y modal en React para el frontend")
    assert "Frontend" in tags_front

    tags_db = local_ai_manager.tag_backlog_item("Optimizar query SQL e indexar tablas en Postgres")
    assert "Database" in tags_db

def test_tag_markdown_backlog():
    sample_backlog = (
        "## 📋 POR HACER (TODO)\n"
        "| ID | Tarea | Asignado |\n"
        "|---|---|---|\n"
        "| T-001 | [US-001] Diseñar la interfaz UI en Vue | @frontend |\n"
        "| T-002 | [US-002] Configurar docker y pipeline CI/CD | @devops |\n"
    )
    enriched = local_ai_manager.tag_markdown_backlog(sample_backlog)
    assert "**[Frontend]**" in enriched
    assert "**[DevOps]**" in enriched

def test_translate_markdown_structured_preserves_code_and_links():
    raw_md = (
        "# Welcome to the guide\n\n"
        "Please read our official [documentation](file:///home/user/doc.md).\n\n"
        "Here is the command line:\n"
        "```python\n"
        "def run_server():\n"
        "    print('Hello World')\n"
        "```\n"
        "Do not touch `const key = 'secret';` inline.\n"
    )

    # Mock de translate_text para simular traducción sin requerir descarga de modelos
    with patch.object(LocalTransformersManager, 'translate_text', side_effect=lambda text, model_key='translator_en_es': f"[TRADUCIDO] {text}"):
        translated = local_ai_manager.translate_markdown_structured(raw_md)

    # Verificar que el bloque de código de Python se mantuvo 100% intacto y no fue traducido
    assert "```python\ndef run_server():\n    print('Hello World')\n```" in translated
    # Verificar que el código inline se mantuvo intacto
    assert "`const key = 'secret';`" in translated
    # Verificar que el destino del enlace no se vio alterado en absoluto
    assert "(file:///home/user/doc.md)" in translated
    # Verificar que el texto sí se envió al traductor
    assert "[TRADUCIDO]" in translated

def test_product_owner_build_md_backlog_includes_tags():
    mock_orch = MagicMock()
    po = ProductOwnerPhase(mock_orch)
    backlog_dict = {
        "proyecto": "Prueba",
        "vision": "Sistema seguro",
        "user_stories": [
            {
                "id": "US-001",
                "titulo": "Autenticación segura JWT",
                "como": "usuario",
                "quiero": "iniciar sesión con tokens",
                "para": "proteger mis datos",
                "criterios_aceptacion": ["Token válido"],
                "contexto_rag_necesario": [],
                "definition_of_done": []
            }
        ]
    }
    md_output = po._build_md_backlog(backlog_dict)
    assert "### US-001: **[Security]** Autenticación segura JWT" in md_output
