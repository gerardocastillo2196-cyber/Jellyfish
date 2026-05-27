import sys
import os
import pytest
from unittest.mock import MagicMock, patch

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core.command_dispatcher import handle_slash_command

class TestCommandDispatcher:
    def setup_method(self):
        self.state = MagicMock()
        self.rag = MagicMock()
        self.plugins = MagicMock()
        self.display_header_func = MagicMock()

    @patch("core.commands.system.handle_system_command")
    def test_system_commands(self, mock_system):
        handle_slash_command("/help", self.state, self.rag, self.plugins, self.display_header_func)
        mock_system.assert_called_once_with("/help", "", self.state, self.plugins, self.display_header_func)

    @patch("core.commands.rag.handle_rag_command")
    def test_rag_commands(self, mock_rag):
        handle_slash_command("/add file.py", self.state, self.rag, self.plugins, self.display_header_func)
        mock_rag.assert_called_once_with("/add", "file.py", self.state, self.rag, self.display_header_func)

    @patch("core.commands.project.handle_project_command")
    def test_project_commands(self, mock_project):
        handle_slash_command("/project info", self.state, self.rag, self.plugins, self.display_header_func)
        mock_project.assert_called_once_with("/project", "info", self.state, self.rag, self.display_header_func)

    @patch("core.commands.config.handle_config_command")
    def test_config_commands(self, mock_config):
        handle_slash_command("/config menu", self.state, self.rag, self.plugins, self.display_header_func)
        mock_config.assert_called_once_with("/config", "menu", self.state, self.display_header_func)

    @patch("core.commands.entity.handle_entity_command")
    def test_entity_commands(self, mock_entity):
        handle_slash_command("/agent load", self.state, self.rag, self.plugins, self.display_header_func)
        mock_entity.assert_called_once_with("/agent", "load", self.state, self.display_header_func)

    @patch("core.commands.orchestration.handle_orchestration_command")
    def test_orchestration_commands(self, mock_orch):
        handle_slash_command("/auto webapp", self.state, self.rag, self.plugins, self.display_header_func)
        mock_orch.assert_called_once_with("/auto", "webapp", self.state, self.rag, self.display_header_func)

    @patch("core.command_dispatcher.sys.exit")
    def test_exit_command(self, mock_exit):
        handle_slash_command("/exit", self.state, self.rag, self.plugins, self.display_header_func)
        mock_exit.assert_called_once_with(0)

    @patch("core.commands.system.handle_system_command")
    def test_aliases(self, mock_system):
        # /h should map to /help
        handle_slash_command("/h", self.state, self.rag, self.plugins, self.display_header_func)
        mock_system.assert_called_once_with("/help", "", self.state, self.plugins, self.display_header_func)
