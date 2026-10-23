"""
Selector item definition
"""
from typing import Any, Optional, Dict


class SelectorItem:
    """Item for selector selection"""

    def __init__(
        self,
        value: Any,
        label: str,
        preview: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize selector item

        Args:
            value: Item value (returned when selected)
            label: Display label
            preview: Preview text (shown in description)
            metadata: Additional metadata
        """
        self.value = value
        self.label = label
        self.preview = preview
        self.metadata = metadata or {}

    def __repr__(self) -> str:
        return f"SelectorItem(value={self.value!r}, label={self.label!r})"
