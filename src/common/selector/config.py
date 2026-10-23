"""
Selector configuration
"""
from typing import Optional, Any
from pydantic import BaseModel, ConfigDict, Field


class SelectorConfig(BaseModel):
    """Selector configuration"""
    model_config = ConfigDict(frozen=False, extra="forbid", arbitrary_types_allowed=True)

    # UI settings
    show_preview: bool = Field(default=False, description="Show preview in status bar")
    preview_lines: int = Field(default=2, ge=1, le=5, description="Number of preview lines to display")
    message: str = Field(default="Select:", description="Prompt message")

    # Feature settings
    enable_multi_select: bool = Field(default=False, description="Enable multi-select mode")
    require_selection: bool = Field(default=True, description="Require at least one selection in multi-select mode")

    # Selection settings
    default: Optional[Any] = Field(default=None, description="Default selection value(s)")
    raise_on_cancel: bool = Field(default=True, description="Raise exception on cancel")

    # Style
    style: Optional[Any] = Field(default=None, description="PromptStyle instance for visual rendering")

    # Message settings
    require_selection_message: str = Field(
        default="Please select at least one item",
        description="Message to show when no selection in multi-select mode"
    )
