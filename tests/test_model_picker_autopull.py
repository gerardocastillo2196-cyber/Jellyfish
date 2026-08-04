import sys
import os
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core.commands.config import _detect_provider_from_name, _get_installed_ollama_models, _pull_ollama_model, _handle_model_picker

class TestModelPickerAutopull:
    def test_detect_provider_from_name(self):
        assert _detect_provider_from_name("gemini-2.5-flash") == "gemini"
        assert _detect_provider_from_name("claude-3-5-sonnet") == "claude"
        assert _detect_provider_from_name("gpt-4o") == "openai"
        assert _detect_provider_from_name("deepseek-chat") == "deepseek"
        assert _detect_provider_from_name("qwen2.5-coder:latest") == "ollama"
        assert _detect_provider_from_name("some-custom-local-model") == "ollama"

    @patch("httpx.Client")
    def test_get_installed_ollama_models(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [
                {"name": "qwen2.5-coder:latest"},
                {"name": "llama3:latest"},
                {"name": "nomic-embed-text:latest"} # Debería ser filtrado
            ]
        }
        mock_client.get.return_value = mock_response
        
        state = MagicMock()
        state.ollama_base_url = "http://localhost:11434"
        models = _get_installed_ollama_models(state)
        
        assert "qwen2.5-coder:latest" in models
        assert "llama3:latest" in models
        assert "nomic-embed-text:latest" not in models

    @patch("httpx.stream")
    def test_pull_ollama_model_success(self, mock_stream):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.iter_lines.return_value = [
            b'{"status": "pulling manifest"}',
            b'{"status": "downloading layer", "digest": "sha256:123", "total": 100, "completed": 50}',
            b'{"status": "success"}'
        ]
        mock_stream.return_value.__enter__.return_value = mock_response
        
        state = MagicMock()
        state.ollama_base_url = "http://localhost:11434"
        
        with patch("core.ui.console.print") as mock_print:
            success = _pull_ollama_model(state, "qwen2.5-coder:latest")
            assert success is True

    @patch("core.ui.interactive_picker")
    @patch("core.commands.config._get_installed_ollama_models")
    @patch("core.commands.config._pull_ollama_model")
    def test_handle_model_picker_arg_pull_local(self, mock_pull, mock_get_installed, mock_picker):
        mock_get_installed.return_value = ["llama3:latest"]
        # Simular que el usuario aprueba la descarga y selecciona el rol como Local
        mock_picker.side_effect = [
            "Sí, descargar automáticamente (Auto-Pull)",
            "🏠 Configurar como modelo LOCAL (solo para Ejecución de Código)"
        ]
        mock_pull.return_value = True
        
        state = MagicMock()
        state.api_keys = {}
        display_header_func = MagicMock()
        
        with patch("builtins.input", return_value=""):
            _handle_model_picker(state, display_header_func, "qwen2.5-coder:latest")
            
        mock_pull.assert_called_once_with(state, "qwen2.5-coder:latest")
        state.save_config.assert_called_once_with(
            executor_provider="ollama",
            executor_model="qwen2.5-coder:latest",
            subagent_provider="ollama",
            subagent_model="qwen2.5-coder:latest"
        )
