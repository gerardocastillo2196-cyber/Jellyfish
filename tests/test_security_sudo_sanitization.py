import unittest
from unittest.mock import patch, MagicMock
import re
from core.terminal import _is_destructive, run_terminal_command
from core.llm_engine import _BASH_REGEX


class TestSecuritySudoSanitization(unittest.TestCase):

    def test_sudo_blocking(self):
        # 1. Comandos con sudo deben ser detectados como destructivos/peligrosos
        dangerous_cmd = "sudo apt-get update"
        is_dan, pat = _is_destructive(dangerous_cmd)
        self.assertTrue(is_dan)
        self.assertIn("sudo", pat.lower())

        # 2. Comandos su o doas
        is_dan_su, _ = _is_destructive("su - root")
        self.assertTrue(is_dan_su)

        is_dan_doas, _ = _is_destructive("doas pacman -Syu")
        self.assertTrue(is_dan_doas)

    def test_system_directories_blocking(self):
        # Intentos de reorientar/escribir en /root o /etc
        is_dan, _ = _is_destructive("echo 'test' > /root/test.txt")
        self.assertTrue(is_dan)

    def test_bash_regex_strict_labeling(self):
        # Bloques con etiqueta explícita bash/sh deben matchear
        valid_bash = "```bash\nls -la\n```"
        self.assertEqual(_BASH_REGEX.findall(valid_bash), ["ls -la"])

        valid_sh = "```sh\necho hello\n```"
        self.assertEqual(_BASH_REGEX.findall(valid_sh), ["echo hello"])

        # Bloques de texto plano o sin etiqueta NO deben matchear
        plain_text_block = "```\nmi-proyecto/\n├── src/\n└── README.md\n```"
        self.assertEqual(_BASH_REGEX.findall(plain_text_block), [])

        text_label_block = "```text\nEstructura de archivos:\n- main.py\n```"
        self.assertEqual(_BASH_REGEX.findall(text_label_block), [])

    def test_run_terminal_command_sudo_rejected_immediately(self):
        mock_state = MagicMock()
        mock_state.is_project_auto_approved.return_value = False
        mock_state.active_project = ""
        mock_state.denied_commands = set()

        result = run_terminal_command("sudo systemctl restart nginx", mock_state)
        self.assertIn("INCIDENTE DE SEGURIDAD", result)
        self.assertIn("destructivo", result)


if __name__ == "__main__":
    unittest.main()
