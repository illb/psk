"""
Custom prompt_toolkit prompt for selector with preview status bar
"""
from typing import List, Optional, Any
from prompt_toolkit import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.layout import (
    Layout,
    HSplit,
    Window,
    FormattedTextControl,
    ConditionalContainer,
)
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.filters import Condition
from prompt_toolkit.styles import Style

from .item import SelectorItem
from .config import SelectorConfig
from ..browser.base.message_manager import MessageManager
from ..exceptions import CancelledError
from ..policy import get_policy


class SelectorPrompt:
    """Custom prompt with preview status bar"""

    def __init__(
        self,
        items: List[SelectorItem],
        config: SelectorConfig,
    ):
        """
        Initialize selector prompt

        Args:
            items: List of SelectorItem
            config: SelectorConfig
        """
        self.items = items
        self.config = config
        self.current_index = 0
        self.selected_indices: set = set()

        # Message management
        self.message_manager = MessageManager()

        # Initialize default selection
        if self.config.default is not None:
            if isinstance(self.config.default, list):
                for i, item in enumerate(items):
                    if item.value in self.config.default:
                        self.selected_indices.add(i)
            else:
                for i, item in enumerate(items):
                    if item.value == self.config.default:
                        self.current_index = i
                        break

        self.confirming_exit = False
        self.buffer = Buffer()
        self.kb = KeyBindings()
        self._setup_key_bindings()

    def _setup_key_bindings(self):
        """Setup key bindings"""
        kb = self.kb

        @kb.add('up')
        @kb.add('k')
        def go_up(event):
            if self.current_index > 0:
                self.current_index -= 1
                # Force redraw
                event.app.invalidate()

        @kb.add('down')
        @kb.add('j')
        def go_down(event):
            if self.current_index < len(self.items) - 1:
                self.current_index += 1
                # Force redraw
                event.app.invalidate()

        @kb.add(' ')
        def toggle_selection(event):
            if self.config.enable_multi_select:
                if self.current_index in self.selected_indices:
                    self.selected_indices.remove(self.current_index)
                else:
                    self.selected_indices.add(self.current_index)
                # Clear warning when selection changes
                if self.message_manager.warning_message:
                    self.message_manager.clear_warning()
                # Force redraw
                event.app.invalidate()

        for numeric_key in ['1', '2', '3', '4', '5', '6', '7', '8', '9', '0']:

            @kb.add(numeric_key)
            def numeric_select(event, numeric_key=numeric_key):
                if self.confirming_exit:
                    return
                index = self._index_from_numeric_key(numeric_key)
                if index is None:
                    return
                self.current_index = index
                if self.config.enable_multi_select:
                    if index in self.selected_indices:
                        self.selected_indices.remove(index)
                    else:
                        self.selected_indices.add(index)
                    if self.message_manager.warning_message:
                        self.message_manager.clear_warning()
                    event.app.invalidate()
                    return
                self.message_manager.clear()
                event.app.exit(result=self.items[index].value)

        @kb.add('enter')
        def confirm(event):
            # Check if at least one item is selected in multi-select mode
            if self.config.enable_multi_select and self.config.require_selection:
                if len(self.selected_indices) == 0:
                    self.message_manager.set_warning(self.config.require_selection_message)
                    event.app.invalidate()
                    return

            # Clear messages if selection is valid
            self.message_manager.clear()
            event.app.exit(result=self._get_result())

        @kb.add('escape')
        @kb.add('q')
        def cancel(event):
            if get_policy().nav.confirm_on_exit:
                self.confirming_exit = True
                event.app.invalidate()
            else:
                event.app.exit(result=None)

        @kb.add('y')
        @kb.add('Y')
        def confirm_exit_yes(event):
            if self.confirming_exit:
                event.app.exit(result=None)

        @kb.add('n')
        @kb.add('N')
        def confirm_exit_no(event):
            if self.confirming_exit:
                self.confirming_exit = False
                event.app.invalidate()

        @kb.add('c-c')
        def interrupt(event):
            event.app.exit(exception=KeyboardInterrupt())

    def _index_from_numeric_key(self, numeric_key: str) -> Optional[int]:
        """숫자 키를 item index로 변환 (1..9, 0->10)"""
        index = 9 if numeric_key == '0' else int(numeric_key) - 1
        if index < 0 or index >= len(self.items):
            return None
        return index

    def _get_result(self) -> Optional[Any]:
        """Get selected result"""
        if self.config.enable_multi_select:
            return [self.items[i].value for i in sorted(self.selected_indices)]
        else:
            return self.items[self.current_index].value

    def _render_content(self) -> List[tuple]:
        """Render content list"""
        from ..style import DEFAULT_STYLE

        ps = self.config.style or DEFAULT_STYLE
        result = []

        for i, item in enumerate(self.items):
            is_selected = i in self.selected_indices if self.config.enable_multi_select else i == self.current_index
            is_cursor = i == self.current_index

            # Selection indicator
            if self.config.enable_multi_select:
                marker = ps.selected_marker.text if is_selected else ps.unselected_marker.text
                pointer = ps.cursor.text if is_cursor else " "
            else:
                pointer = ps.cursor.text if is_cursor else " "
                marker = ""

            # Color
            if self.config.enable_multi_select:
                if is_cursor and is_selected:
                    color = f"bold {ps.selected}"
                elif is_cursor:
                    color = ps.accent
                elif is_selected:
                    color = ps.selected
                else:
                    color = ps.dim
            else:
                color = ps.accent if is_cursor else ps.dim

            if self.config.enable_multi_select:
                text = f" {pointer} {marker} {i + 1}) {item.label}"
            else:
                text = f" {pointer} {i + 1}) {item.label}"
            result.append((color, text))
            if i < len(self.items) - 1:
                result.append(("", "\n"))

        return result

    def _render_status(self) -> List[tuple]:
        """Render status bar with preview"""
        import shutil
        terminal_width = shutil.get_terminal_size().columns

        # Check and auto-clear expired messages
        if self.message_manager.check_auto_clear():
            if hasattr(self, 'app') and self.app:
                self.app.invalidate()

        # Show message if present (overrides preview)
        current_message = self.message_manager.get_current_message()
        if current_message:
            msg_type, msg_text = current_message
            if msg_type == "error":
                style = "bg:#ff6b6b fg:#ffffff bold"
                icon = "✗"
            elif msg_type == "warning":
                style = "bg:#ffa500 fg:#000000 bold"
                icon = "⚠️"
            else:  # info
                style = "bg:#4a90e2 fg:#ffffff bold"
                icon = "ℹ️"

            message_text = f"{icon}  {msg_text}"

            # Format message lines (use preview_lines from config)
            preview_lines_count = self.config.preview_lines
            result_lines = []

            # Split message into lines
            words = msg_text.split()
            current_line = f"{icon}  "
            lines = []

            for word in words:
                if len(current_line) + len(word) + 1 <= terminal_width - 2:
                    current_line += word + " "
                else:
                    if current_line.strip():
                        lines.append(current_line.strip())
                    current_line = word + " "
            if current_line.strip():
                lines.append(current_line.strip())

            # Limit to preview_lines_count
            lines = lines[:preview_lines_count]

            # Fill remaining lines if needed
            while len(lines) < preview_lines_count:
                lines.append("")

            # Build result with full width
            for i, line in enumerate(lines):
                # Fill entire width with background
                padded_line = line.ljust(terminal_width)
                result_lines.append((style, padded_line))
                if i < len(lines) - 1:
                    result_lines.append(("", "\n"))

            return result_lines

        if not self.config.show_preview or not self.items:
            # Return empty lines matching preview_lines
            empty_lines = [("", "")] * self.config.preview_lines
            result = []
            for i, line in enumerate(empty_lines):
                result.append(line)
                if i < len(empty_lines) - 1:
                    result.append(("", "\n"))
            return result

        current_item = self.items[self.current_index]
        preview_lines_count = self.config.preview_lines

        # Light gray background color
        preview_style = "bg:#d3d3d3 fg:#000000"

        if current_item.preview:
            # Format preview lines
            preview_lines = current_item.preview.split('\n')

            # Take up to preview_lines_count lines
            display_lines = []
            for i in range(preview_lines_count):
                if i < len(preview_lines):
                    line = preview_lines[i]
                    # Truncate if too long
                    if len(line) > terminal_width:
                        line = line[:terminal_width-3] + "..."
                    display_lines.append(line)
                else:
                    display_lines.append("")
        else:
            # No preview, show label on first line
            display_lines = [current_item.label]
            while len(display_lines) < preview_lines_count:
                display_lines.append("")

        # Build result with full width
        result = []
        for i, line in enumerate(display_lines):
            # Fill entire width with background
            padded_line = line.ljust(terminal_width)
            result.append((preview_style, padded_line))
            if i < len(display_lines) - 1:
                result.append(("", "\n"))

        return result

    def _create_layout(self) -> Layout:
        """Create prompt_toolkit layout"""
        from ..style import DEFAULT_STYLE

        ps = self.config.style or DEFAULT_STYLE

        # Message control
        message_control = FormattedTextControl(
            text=lambda: [("bold", self.config.message)],
            focusable=False,
            show_cursor=False
        )
        message_window = Window(message_control, height=1)

        # Preview control (between message and content)
        preview_control = FormattedTextControl(
            text=lambda: self._render_status(),
            focusable=False,
            show_cursor=False
        )
        preview_window = Window(
            preview_control,
            height=self.config.preview_lines
        )

        # Content control
        content_control = FormattedTextControl(
            text=lambda: self._render_content(),
            focusable=True,
            show_cursor=False
        )
        content_window = Window(content_control, height=None)

        children = [
            message_window,
            ConditionalContainer(
                preview_window,
                filter=Condition(lambda: self.config.show_preview or self.message_manager.has_message())
            ),
            content_window,
        ]

        if ps.show_key_hints:
            if self.config.enable_multi_select:
                hints = [("↑/↓", "navigate"), ("space", "toggle"), ("1-9/0", "toggle #"), ("enter", "confirm"), ("esc", "cancel")]
            else:
                hints = [("↑/↓", "navigate"), ("1-9/0", "quick select"), ("enter", "select"), ("esc", "cancel")]
            hint_text = "  " + ps.key_hint_sep.join(f"{k}: {a}" for k, a in hints)
            children.append(
                Window(FormattedTextControl(lambda: [(ps.dim, hint_text)], show_cursor=False), height=1)
            )

        def _confirm_exit_fragments():
            if self.confirming_exit:
                return [("bold #ffa726", "  Exit? (y/n) ")]
            return []

        children.append(
            ConditionalContainer(
                Window(FormattedTextControl(_confirm_exit_fragments, show_cursor=False), height=1),
                filter=Condition(lambda: self.confirming_exit),
            )
        )

        return Layout(HSplit(children))

    def run(self) -> Optional[Any]:
        """Run the prompt"""
        layout = self._create_layout()

        style = Style.from_dict({
            '': '#ffffff',
        })

        self.app = Application(
            layout=layout,
            key_bindings=self.kb,
            style=style,
            full_screen=False,
            mouse_support=False,
            refresh_interval=0.1,  # Auto refresh for status bar updates
        )

        try:
            result = self.app.run()
            if result is None:
                if self.config.raise_on_cancel:
                    raise CancelledError()
                return None
            return result
        except KeyboardInterrupt:
            raise
        except CancelledError:
            if self.config.raise_on_cancel:
                raise
            return None
