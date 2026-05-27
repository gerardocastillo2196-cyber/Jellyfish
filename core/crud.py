# Re-exports for backward compatibility after refactoring
from core.command_dispatcher import handle_slash_command
from core.commands.project import show_project_guide_if_needed
from core.commands.entity import handle_crud, detailed_interview, _sanitize_name
from core.commands.config import _handle_config
