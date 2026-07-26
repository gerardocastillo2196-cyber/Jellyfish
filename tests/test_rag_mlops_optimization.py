import unittest
from unittest.mock import MagicMock
from core.state import JellyfishState
from core.rag_coder import CodeKnowledgeBase, _split_file


class TestRagMlopsOptimization(unittest.TestCase):

    def test_chunk_size_optimization(self):
        """Verifica que el tamaño de chunk optimizado a 800 caracteres divida adecuadamente."""
        large_code = "def sample_function():\n    pass\n\n" * 100
        chunks = _split_file(large_code, ".py", "test.py")
        self.assertTrue(len(chunks) > 1)
        for chunk in chunks:
            self.assertTrue(len(chunk) <= 1600)

    def test_evicted_history_vectorization(self):
        """Verifica que al truncar el historial se invoque la vectorización de memoria en el RAG."""
        state = JellyfishState()
        mock_rag = MagicMock()
        state.rag = mock_rag

        # Configurar tamaño máximo de historial pequeno para forzar expulsión
        import os
        os.environ["JELLYFISH_MAX_HISTORY_SIZE"] = "3"

        state.history.append({"role": "user", "content": "msg 1"})
        state.history.append({"role": "assistant", "content": "msg 2"})
        state.history.append({"role": "user", "content": "msg 3"})
        state.history.append({"role": "assistant", "content": "msg 4"})

        # Al superar el límite 3, se expulsa el msg 1 y se llama a index_history_memory
        mock_rag.index_history_memory.assert_called()
        call_args = mock_rag.index_history_memory.call_args[0][0]
        self.assertEqual(len(call_args), 1)
        self.assertEqual(call_args[0]["content"], "msg 1")


if __name__ == "__main__":
    unittest.main()
