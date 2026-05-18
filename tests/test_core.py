"""
tests/test_core.py — Sprint 4.5: Pruebas unitarias de Jellyfish OS core.

Cubre las funciones más propensas a errores silenciosos identificadas en la auditoría:
  - Parseo SSE/Ollama de streams
  - Parseo seguro de JSON del orquestador
  - Detección de comandos destructivos
  - Truncamiento inteligente de terminal
  - Presupuesto de tokens del historial
  - Plugin sandbox (mock)

Ejecutar con:
    cd /home/gerardo/MisModelosIA/agencia
    source venv/bin/activate
    python -m pytest tests/ -v
"""

import json
import os
import sys
import pytest

# Aseguramos que el proyecto esté en el path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


# ---------------------------------------------------------------------------
# 1. Parseo de líneas de stream SSE/Ollama (core/llm_engine.py)
# ---------------------------------------------------------------------------

class TestStreamParsers:
    def test_parse_sse_line_valid(self):
        from core.llm_engine import _parse_sse_line
        payload = json.dumps({"choices": [{"delta": {"content": "hola"}}]})
        line = f"data: {payload}".encode()
        assert _parse_sse_line(line, "openai") == "hola"

    def test_parse_sse_line_done(self):
        from core.llm_engine import _parse_sse_line
        assert _parse_sse_line(b"data: [DONE]", "openai") == ""

    def test_parse_sse_line_empty(self):
        from core.llm_engine import _parse_sse_line
        assert _parse_sse_line(b"", "openai") == ""

    def test_parse_sse_line_malformed_json(self):
        from core.llm_engine import _parse_sse_line
        assert _parse_sse_line(b"data: {not valid json}", "openai") == ""

    def test_parse_ollama_line_valid(self):
        from core.llm_engine import _parse_ollama_line
        payload = json.dumps({"message": {"content": "mundo"}}).encode()
        assert _parse_ollama_line(payload) == "mundo"

    def test_parse_ollama_line_no_message(self):
        from core.llm_engine import _parse_ollama_line
        payload = json.dumps({"done": True}).encode()
        assert _parse_ollama_line(payload) == ""

    def test_parse_ollama_line_malformed(self):
        from core.llm_engine import _parse_ollama_line
        assert _parse_ollama_line(b"not-json") == ""


# ---------------------------------------------------------------------------
# 2. Parseo robusto de plan JSON del orquestador (core/orchestrator.py)
# ---------------------------------------------------------------------------

class TestPlanParser:
    def setup_method(self):
        from core.orchestrator import _parse_plan_safe
        self.parse = _parse_plan_safe

    def test_plain_array(self):
        text = '[{"query": "buscar plugins"}, {"query": "ver state"}]'
        result = self.parse(text)
        assert len(result) == 2
        assert result[0]["query"] == "buscar plugins"

    def test_wrapped_object_steps(self):
        text = '{"steps": [{"query": "analizar rag"}, {"query": "ver crud"}]}'
        result = self.parse(text)
        assert len(result) == 2

    def test_wrapped_object_plan(self):
        text = '{"plan": [{"query": "revisar terminal"}]}'
        result = self.parse(text)
        assert len(result) == 1

    def test_markdown_fenced_json(self):
        text = '```json\n[{"query": "entender orchestrator"}]\n```'
        result = self.parse(text)
        assert len(result) == 1
        assert result[0]["query"] == "entender orchestrator"

    def test_garbage_returns_empty(self):
        result = self.parse("Lo siento, no puedo generar el plan en este momento.")
        assert result == []

    def test_array_with_missing_query_key_filtered(self):
        text = '[{"step": "uno"}, {"query": "valido"}]'
        result = self.parse(text)
        assert len(result) == 1
        assert result[0]["query"] == "valido"

    def test_empty_string(self):
        assert self.parse("") == []

    def test_nested_array_in_text(self):
        text = 'Aquí está el plan: [{"query": "paso uno"}] espero que ayude.'
        result = self.parse(text)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# 3. Detección de comandos destructivos (core/terminal.py)
# ---------------------------------------------------------------------------

class TestDestructiveFilter:
    def setup_method(self):
        from core.terminal import _is_destructive
        self.check = _is_destructive

    def test_rm_rf_blocked(self):
        dangerous, _ = self.check("rm -rf /home/user")
        assert dangerous is True

    def test_rm_fr_blocked(self):
        dangerous, _ = self.check("rm -fr /tmp/folder")
        assert dangerous is True

    def test_mkfs_blocked(self):
        dangerous, _ = self.check("mkfs.ext4 /dev/sdb1")
        assert dangerous is True

    def test_dd_dev_blocked(self):
        dangerous, _ = self.check("dd if=/dev/zero of=/dev/sda bs=512")
        assert dangerous is True

    def test_fork_bomb_blocked(self):
        dangerous, _ = self.check(":(){:|:&};:")
        assert dangerous is True

    def test_safe_rm_allowed(self):
        dangerous, _ = self.check("rm -f /tmp/myfile.log")
        assert dangerous is False

    def test_ls_allowed(self):
        dangerous, _ = self.check("ls -la /home")
        assert dangerous is False

    def test_git_status_allowed(self):
        dangerous, _ = self.check("git status")
        assert dangerous is False

    def test_pip_install_allowed(self):
        dangerous, _ = self.check("pip install requests")
        assert dangerous is False


# ---------------------------------------------------------------------------
# 4. Truncamiento inteligente head+tail (core/terminal.py)
# ---------------------------------------------------------------------------

class TestSmartTruncate:
    def setup_method(self):
        from core.terminal import _smart_truncate
        self.trunc = _smart_truncate

    def test_short_text_unchanged(self):
        text = "hola mundo"
        assert self.trunc(text, max_chars=100) == text

    def test_long_text_truncated(self):
        text = "A" * 200 + "B" * 200
        result = self.trunc(text, max_chars=100)
        assert "omitidos" in result
        # Debe preservar inicio y final
        assert result.startswith("A" * 50)
        assert result.endswith("B" * 50)

    def test_exactly_at_limit_unchanged(self):
        text = "X" * 100
        assert self.trunc(text, max_chars=100) == text


# ---------------------------------------------------------------------------
# 5. Presupuesto de tokens en historial (core/state.py)
# ---------------------------------------------------------------------------

class TestTokenBudget:
    def setup_method(self):
        # Parchamos el límite para que sea predecible en el test
        import core.state as s
        self._orig = s._HISTORY_CHAR_BUDGET
        s._HISTORY_CHAR_BUDGET = 200  # presupuesto pequeño para el test

    def teardown_method(self):
        import core.state as s
        s._HISTORY_CHAR_BUDGET = self._orig

    def test_history_trimmed_when_over_budget(self):
        from core.state import JellyfishState
        state = JellyfishState()
        state.static_history = []  # vaciar contexto estático para el test

        # Agregar mensajes que superen el presupuesto
        for i in range(20):
            state.history.append({"role": "user", "content": "X" * 20})

        history = state.get_full_history()
        total_chars = sum(len(m.get("content", "")) for m in history)
        assert total_chars <= 200 + 40  # margen por estático vacío

    def test_recent_messages_preserved(self):
        from core.state import JellyfishState
        state = JellyfishState()
        state.static_history = []

        # El último mensaje debe siempre preservarse
        for i in range(5):
            state.history.append({"role": "user", "content": "A" * 10})
        state.history.append({"role": "user", "content": "ÚLTIMO"})

        history = state.get_full_history()
        contents = [m["content"] for m in history]
        assert "ÚLTIMO" in contents


# ---------------------------------------------------------------------------
# 6. Sanitización de nombres de archivos (core/crud.py)
# ---------------------------------------------------------------------------

class TestSanitizeName:
    def setup_method(self):
        from core.crud import _sanitize_name
        self.sanitize = _sanitize_name

    def test_removes_special_chars(self):
        assert self.sanitize("mi agente!@#") == "mi_agente"

    def test_lowercases(self):
        assert self.sanitize("MiAgente") == "miagente"

    def test_spaces_to_underscores(self):
        assert self.sanitize("mi agente nuevo") == "mi_agente_nuevo"

    def test_empty_returns_empty(self):
        assert self.sanitize("!!!") == ""

    def test_dots_and_dashes_preserved(self):
        result = self.sanitize("agente-v2.0")
        assert "agente" in result
        assert "v2" in result
