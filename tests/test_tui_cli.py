import unittest
from unittest.mock import patch
import sys
from core.tui import TUIEngine

class TestTUIEngineCli(unittest.TestCase):
    def test_cli_mode_defaults_to_true(self):
        engine = TUIEngine()
        self.assertTrue(engine.cli_mode)

    def test_init_terminal(self):
        engine = TUIEngine()
        engine.init_terminal()
        self.assertTrue(engine._initialized)
        engine.restore_terminal()
        self.assertFalse(engine._initialized)

    def test_append_log(self):
        engine = TUIEngine()
        with patch('sys.stdout.write') as mock_write, patch('sys.stdout.flush') as mock_flush:
            engine.append_log("hello")
            mock_write.assert_called_once_with("hello")
            mock_flush.assert_called_once()

if __name__ == '__main__':
    unittest.main()
