# --- __init__.py ---

# Import the main public API facade
from .participant_assigner_api import ParticipantAssignerAPI

# Import custom exceptions for client error handling
from .config_loader import ConfigError
from .participant_repository import RepositoryError
from .assignment_service import AssignmentError
from .participant_data_logger import FileSystemError

# Define __all__ to specify public-facing components
# This controls `from package_name import *`
__all__ = [
    "ParticipantAssignerAPI",
    "ConfigError",
    "RepositoryError",
    "AssignmentError",
    "FileSystemError"
]