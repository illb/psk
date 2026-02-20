"""
CLI initialization utilities
"""
import os


def initialize_cli():
    """
    Initialize CLI environment
    Called at application startup to configure environment variables and settings
    """
    # Disable CPR (Cursor Position Request) for terminals that don't support it
    # This fixes arrow key issues in some terminals
    os.environ.setdefault('PROMPT_TOOLKIT_DISABLE_CPR', '1')
