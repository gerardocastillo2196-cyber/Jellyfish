import unittest
import threading
import tempfile
import os
import shutil
from core.state import JellyfishState
from core.plugin_manager import PluginManager


class TestArchitecturalRefactoring(unittest.TestCase):

    def test_state_concurrent_access(self):
        """Verifica que el acceso concurrente a JellyfishState sea thread-safe."""
        state = JellyfishState()
        threads = []
        errors = []

        def worker(idx):
            try:
                for i in range(100):
                    state.history.append({"role": "user", "content": f"msg_{idx}_{i}"})
                    state.add_session_tokens(10)
                    state.blackboard.set(f"key_{idx}", i)
            except Exception as e:
                errors.append(e)

        for t_idx in range(10):
            t = threading.Thread(target=worker, args=(t_idx,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"Excepciones durante acceso concurrente: {errors}")
        self.assertEqual(state.session_tokens, 10000)

    def test_plugin_fault_isolation(self):
        """Verifica que un plugin corrupto o faliante no derribe el PluginManager."""
        tmp_plugins = tempfile.mkdtemp()
        try:
            # Plugin con error de ejecución intencional al cargarse
            bad_plugin_path = os.path.join(tmp_plugins, "corrupt_plugin.py")
            with open(bad_plugin_path, "w", encoding="utf-8") as f:
                f.write("raise RuntimeError('Error fatal intencional al importar plugin')\n")

            manager = PluginManager(plugins_dir=tmp_plugins)
            # El manager no debe lanzar RuntimeError y debe inicializarse limpiamente
            self.assertNotIn("corrupt_plugin", manager.plugins)

            # Ejecutar plugin inexistente o fallido retorna mensaje seguro de error
            res = manager.run_plugin("corrupt_plugin", "test")
            self.assertIn("Error", res)

        finally:
            shutil.rmtree(tmp_plugins)


if __name__ == "__main__":
    unittest.main()
