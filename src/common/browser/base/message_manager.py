"""
Message manager

Manages error, warning, and info messages with priority handling
"""
import time
from typing import Optional, Tuple


class MessageManager:
    """Message management class for consistent error/warning/info display"""

    def __init__(self, auto_clear_timeout: float = 5.0):
        """
        Initialize message manager

        Args:
            auto_clear_timeout: Time in seconds before messages auto-clear (default: 5.0)
        """
        self.error_message: Optional[str] = None
        self.warning_message: Optional[str] = None
        self.info_message: Optional[str] = None

        # Timestamps for auto-clear
        self.error_timestamp: Optional[float] = None
        self.warning_timestamp: Optional[float] = None
        self.info_timestamp: Optional[float] = None

        self.auto_clear_timeout = auto_clear_timeout

    def set_error(self, message: str):
        """
        Set error message (highest priority)

        Args:
            message: Error message text
        """
        self.error_message = message
        self.error_timestamp = time.time()
        self.warning_message = None
        self.warning_timestamp = None
        self.info_message = None
        self.info_timestamp = None

    def set_warning(self, message: str):
        """
        Set warning message (medium priority)

        Args:
            message: Warning message text
        """
        if not self.error_message:
            self.warning_message = message
            self.warning_timestamp = time.time()
            self.info_message = None
            self.info_timestamp = None

    def set_info(self, message: str):
        """
        Set info message (lowest priority)

        Args:
            message: Info message text
        """
        if not self.error_message and not self.warning_message:
            self.info_message = message
            self.info_timestamp = time.time()

    def clear(self):
        """Clear all messages"""
        self.error_message = None
        self.error_timestamp = None
        self.warning_message = None
        self.warning_timestamp = None
        self.info_message = None
        self.info_timestamp = None

    def clear_error(self):
        """Clear error message only"""
        self.error_message = None
        self.error_timestamp = None

    def clear_warning(self):
        """Clear warning message only"""
        self.warning_message = None
        self.warning_timestamp = None

    def clear_info(self):
        """Clear info message only"""
        self.info_message = None
        self.info_timestamp = None

    def get_current_message(self) -> Optional[Tuple[str, str]]:
        """
        Get current message to display

        Returns:
            Tuple of (message_type, message_text) or None if no message
            message_type: 'error', 'warning', or 'info'
        """
        if self.error_message:
            return ("error", self.error_message)
        if self.warning_message:
            return ("warning", self.warning_message)
        if self.info_message:
            return ("info", self.info_message)
        return None

    def has_message(self) -> bool:
        """Check if there is any message"""
        return self.error_message is not None or \
               self.warning_message is not None or \
               self.info_message is not None

    def check_auto_clear(self) -> bool:
        """
        Check and clear expired messages

        Returns:
            True if any message was cleared, False otherwise
        """
        current_time = time.time()
        cleared = False

        # Check error message (errors auto-clear after timeout)
        if self.error_message and self.error_timestamp:
            if current_time - self.error_timestamp > self.auto_clear_timeout:
                self.clear_error()
                cleared = True

        # Check warning message
        if self.warning_message and self.warning_timestamp:
            if current_time - self.warning_timestamp > self.auto_clear_timeout:
                self.clear_warning()
                cleared = True

        # Check info message
        if self.info_message and self.info_timestamp:
            if current_time - self.info_timestamp > self.auto_clear_timeout:
                self.clear_info()
                cleared = True

        return cleared
