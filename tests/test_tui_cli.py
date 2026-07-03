import unittest
from unittest.mock import patch
import sys
from core.tui import TUIEngine

class TestTUIEngineCli(unittest.TestCase):
    def test_cli_mode_defaults_to_true(self):
        engine = TUIEngine()
        self.assertTrue(engine.cli_mode)

    def test_init_terminal_cli(self):
        engine = TUIEngine()
        engine.cli_mode = True
        with patch('core.tui.TUIRedirector.start') as mock_start:
            engine.init_terminal()
            mock_start.assert_not_called()
            self.assertTrue(engine._initialized)
        engine.restore_terminal()

    def test_init_terminal_tui(self):
        engine = TUIEngine()
        engine.cli_mode = False
        with patch('core.tui.TUIRedirector.start') as mock_start:
            engine.init_terminal()
            mock_start.assert_called_once()
            self.assertTrue(engine._initialized)
        with patch('core.tui.TUIRedirector.stop') as mock_stop:
            engine.restore_terminal()
            mock_stop.assert_called_once()
            self.assertFalse(engine._initialized)

    def test_append_log_cli(self):
        engine = TUIEngine()
        engine.cli_mode = True
        with patch('sys.stdout.write') as mock_write, patch('sys.stdout.flush') as mock_flush:
            engine.append_log("hello")
            mock_write.assert_called_once_with("hello")
            mock_flush.assert_called_once()

if __name__ == '__main__':
    unittest.main()
