"""
Prompt utility functions using prompt_toolkit
"""
from typing import List, Optional, Any
from prompt_toolkit import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout, HSplit, Window, FormattedTextControl
from rich.console import Console

from .models import ProcessInfo
from ..common.exceptions import CancelledError
from ..common.process_utils import is_system_process

console = Console()


def select_multiple_custom(
    title: str,
    choices: List[tuple],
    default_values: Optional[List[Any]] = None,
    hide_system_processes: bool = True,
    process_data: Optional[List[dict]] = None,
    exclude_list: Optional[List[str]] = None
) -> Optional[List[Any]]:
    """
    Custom multi-select checkbox (fzf style)
    - Fn + ↑/↓: Page navigation
    - d: Show detail information
    - e: Toggle system process and exclusion list filter

    Args:
        title: Prompt title
        choices: List of (value, label) tuples
        default_values: List of default selected values
        hide_system_processes: Whether to hide system processes
        process_data: Process data list (for full title view)
        exclude_list: List of process names to exclude

    Returns:
        List of selected values or None (on cancel)
    """
    if not choices:
        return []
    
    # Selection state management
    selected_indices = set(default_values or [])
    
    # Current cursor position
    current_index = [0]
    
    # Page size (number of items to display per screen)
    page_size = [20]
    
    # System process filter state
    filter_system = [hide_system_processes]

    # Search mode and search query
    search_mode = [False]
    search_query = [""]

    # Exclusion list check function
    def is_excluded_process(proc):
        if not exclude_list:
            return False
        proc_name_lower = proc.name.lower()
        for exclude_keyword in exclude_list:
            if exclude_keyword.lower() in proc_name_lower:
                return True
        return False

    # Filtered choices (always return latest values)
    def get_filtered_choices():
        filtered = []

        for idx, (value, label) in enumerate(choices):
            # System process filtering
            if filter_system[0] and process_data and idx < len(process_data):
                proc = process_data[idx]
                if is_system_process(proc) or is_excluded_process(proc):
                    continue

            # Search query filtering
            if search_mode[0] and search_query[0]:
                if search_query[0].lower() not in label.lower():
                    continue

            filtered.append((value, label))

        return filtered
    
    # Title detail view state
    show_title_detail = [False]
    title_detail_index = [0]
    
    # Page calculation
    def get_page_start():
        return (current_index[0] // page_size[0]) * page_size[0]
    
    def get_page_end():
        filtered = get_filtered_choices()
        return min(get_page_start() + page_size[0], len(filtered))
    
    # UI rendering
    def get_current_command():
        """Return full command of current cursor in two lines"""
        import shutil
        # Get terminal width
        terminal_width = shutil.get_terminal_size().columns

        filtered = get_filtered_choices()
        if current_index[0] < len(filtered):
            value, label = filtered[current_index[0]]
            original_idx = value
            if process_data and original_idx < len(process_data):
                proc = process_data[original_idx]
                command = proc.command
                # Split into two lines (terminal width * 2)
                max_length = terminal_width * 2
                if len(command) > max_length:
                    command = command[:max_length-3] + "..."
                # Split into two lines of terminal width
                line1 = command[:terminal_width] if len(command) > terminal_width else command
                line2 = command[terminal_width:terminal_width*2] if len(command) > terminal_width else ""
                return [
                    ("bg:#004060", line1.ljust(terminal_width)),
                    ("", "\n"),
                    ("bg:#004060", line2.ljust(terminal_width))
                ]
        return [("bg:#004060", " " * terminal_width), ("", "\n"), ("bg:#004060", " " * terminal_width)]

    def get_status_text():
        filtered = get_filtered_choices()
        total = len(filtered)
        selected_count = len(selected_indices)

        # If in search mode
        if search_mode[0]:
            return [("bg:#005f87 bold", f"Search: {search_query[0]}_ | [{total} results] | ESC: Exit search")]

        # Filter status message
        if filter_system[0]:
            if exclude_list:
                filter_status = f"Excluded processes hidden ({len(exclude_list)})"
            else:
                filter_status = "Excluded processes hidden"
        else:
            filter_status = "All processes shown"

        return [("bg:#005f87 bold", f"[{current_index[0] + 1}/{total}] Selected: {selected_count} | {filter_status} | ↑↓ Move, Space Select, Enter Confirm, / Search, d Detail, e Exclude Filter, q Cancel")]
    
    def render_content():
        filtered = get_filtered_choices()
        page_start = get_page_start()
        page_end = get_page_end()
        
        result = []
        for i in range(page_start, page_end):
            if i >= len(filtered):
                break
            
            value, label = filtered[i]
            original_idx = value  # value is already original index
            is_selected = original_idx in selected_indices
            is_cursor = (i == current_index[0])
            
            # Selection indicator
            checkbox = "[X]" if is_selected else "[ ]"
            
            # Cursor indicator
            prefix = "> " if is_cursor else "  "
            
            # Style (using empty string)
            style = ""
            if is_selected and is_cursor:
                style = "bold cyan reverse"
            elif is_cursor:
                style = "bold cyan"
            elif is_selected:
                style = "reverse"

            text = prefix + checkbox + " " + label
            result.append((style, text))
            if i < page_end - 1:  # Add newline if not last line
                result.append(("", "\n"))
        
        # Return at least one item if list is empty
        if not result:
            result = [("", "(No items to display)")]

        return result
    
    # Title detail view rendering
    def render_title_detail():
        if not show_title_detail[0] or process_data is None:
            return []

        idx = title_detail_index[0]
        if idx < len(process_data):
            import shutil
            # Get terminal width
            terminal_width = shutil.get_terminal_size().columns

            proc = process_data[idx]
            command = proc.command

            # Split long command into multiple lines to fit terminal width
            max_width = terminal_width - 4  # Consider margin
            command_lines = []
            if command:
                # Split command into max_width chunks for display
                i = 0
                while i < len(command):
                    command_lines.append(command[i:i+max_width])
                    i += max_width
            else:
                command_lines = ['(No command)']

            result = []
            # Center considering CJK character width
            import unicodedata
            header_text = "Process Detail Information"
            header_visual_len = sum(2 if unicodedata.east_asian_width(c) in ('F', 'W') else 1 for c in header_text)
            header_padding_left = (terminal_width - header_visual_len) // 2
            header_padding_right = terminal_width - header_visual_len - header_padding_left
            centered_header = " " * header_padding_left + header_text + " " * header_padding_right

            lines_data = [
                ("bg:#005f87 bold", centered_header),
                ("", ""),
                ("bold", f"Process Name: {proc.name}  |  Type: {proc.type}"),
                ("", f"PID: {proc.pid}  |  PPID: {proc.ppid}  |  User: {proc.user}  |  Status: {proc.stat}"),
                ("", f"CPU: {proc.cpu:.1f}%  |  Memory: {proc.mem:.1f}%  |  Start Time: {proc.start}  |  Uptime: {proc.uptime}"),
                ("", ""),
                ("bold yellow", "─" * terminal_width),
                ("bold yellow", "Full Command"),
                ("bold yellow", "─" * terminal_width),
            ]
            # Add command lines (cyan color, no margin)
            for cmd_line in command_lines:
                lines_data.append(("cyan", cmd_line))

            # Center footer message (considering CJK character width)
            footer_text = "Press ESC or d key to close"
            footer_visual_len = sum(2 if unicodedata.east_asian_width(c) in ('F', 'W') else 1 for c in footer_text)
            footer_padding_left = (terminal_width - footer_visual_len) // 2
            footer_padding_right = terminal_width - footer_visual_len - footer_padding_left
            centered_footer = " " * footer_padding_left + footer_text + " " * footer_padding_right

            lines_data.extend([
                ("", ""),
                ("dim", "─" * terminal_width),
                ("dim", centered_footer),
            ])

            # Connect with newline characters
            for i, (style, text) in enumerate(lines_data):
                result.append((style, text))
                if i < len(lines_data) - 1:
                    result.append(("", "\n"))

            return result
        return []
    
    # Key bindings
    kb = KeyBindings()
    
    @kb.add('up')
    def move_up(event):
        if show_title_detail[0]:
            show_title_detail[0] = False
            return
        if current_index[0] > 0:
            current_index[0] -= 1
    
    @kb.add('down')
    def move_down(event):
        if show_title_detail[0]:
            show_title_detail[0] = False
            return
        filtered = get_filtered_choices()
        if current_index[0] < len(filtered) - 1:
            current_index[0] += 1
    
    @kb.add('pageup')
    def page_up(event):
        if show_title_detail[0]:
            show_title_detail[0] = False
            return
        page_start = get_page_start()
        if page_start > 0:
            current_index[0] = max(0, page_start - page_size[0])
        else:
            current_index[0] = 0
    
    @kb.add('pagedown')
    def page_down(event):
        if show_title_detail[0]:
            show_title_detail[0] = False
            return
        filtered = get_filtered_choices()
        page_end = get_page_end()
        if page_end < len(filtered):
            current_index[0] = min(len(filtered) - 1, page_end)
        else:
            current_index[0] = len(filtered) - 1
    
    # On Mac, Fn+↑/↓ may also be mapped to Control+F/B
    @kb.add('c-f')  # Control+F (alternative to Fn+↑ on Mac)
    def page_up_alt(event):
        if not show_title_detail[0]:
            page_up(event)
    
    @kb.add('c-b')  # Control+B (alternative to Fn+↓ on Mac)
    def page_down_alt(event):
        if not show_title_detail[0]:
            page_down(event)
    
    @kb.add(' ')
    def toggle_selection(event):
        if show_title_detail[0]:
            show_title_detail[0] = False
            return
        # In search mode, treat Space as search query
        if search_mode[0]:
            search_query[0] += ' '
            current_index[0] = 0
            return
        filtered = get_filtered_choices()
        if current_index[0] < len(filtered):
            value, label = filtered[current_index[0]]
            original_idx = value  # value is already original index
            if original_idx in selected_indices:
                selected_indices.remove(original_idx)
            else:
                selected_indices.add(original_idx)
    
    @kb.add('d')
    def show_detail(event):
        if show_title_detail[0]:
            # If detail is open, close it
            show_title_detail[0] = False
        elif process_data is not None:
            # If detail is closed, open it
            filtered = get_filtered_choices()
            if current_index[0] < len(filtered):
                value, label = filtered[current_index[0]]
                original_idx = value  # value is already original index
                if original_idx < len(process_data):
                    show_title_detail[0] = True
                    title_detail_index[0] = original_idx
    
    @kb.add('e')
    def toggle_filter(event):
        if show_title_detail[0]:
            show_title_detail[0] = False
            return
        filter_system[0] = not filter_system[0]
        # Adjust cursor position when filter changes
        filtered = get_filtered_choices()
        if current_index[0] >= len(filtered):
            current_index[0] = max(0, len(filtered) - 1)
    
    @kb.add('enter')
    def confirm(event):
        if show_title_detail[0]:
            show_title_detail[0] = False
        else:
            event.app.exit(result=list(selected_indices))
    
    @kb.add('q')
    @kb.add('c-c')
    def cancel(event):
        if show_title_detail[0]:
            show_title_detail[0] = False
        else:
            event.app.exit(result=None)
    
    # Start search mode
    @kb.add('/')
    def start_search(event):
        if not show_title_detail[0] and not search_mode[0]:
            search_mode[0] = True
            search_query[0] = ""
            current_index[0] = 0
        elif search_mode[0]:
            # In search mode, add / character to search query
            search_query[0] += '/'
            current_index[0] = 0

    # Handle character input in search mode - exclude function keys like d, e and Space (separate handlers exist)
    import string
    # Only process characters excluding d, e, q, Space as search input
    excluded_keys = {'d', 'e', 'q'}
    allowed_chars = ''.join(c for c in string.ascii_lowercase + string.ascii_uppercase + string.digits + '.-_()[]{}@#$%^&*+=!?;:,<>\\|`~\'\\"' if c.lower() not in excluded_keys)

    for char in allowed_chars:
        @kb.add(char)
        def handle_char(event, c=char):
            if search_mode[0]:
                search_query[0] += c
                current_index[0] = 0

    @kb.add('backspace')
    def handle_backspace(event):
        if search_mode[0] and search_query[0]:
            search_query[0] = search_query[0][:-1]
            current_index[0] = 0

    # Close title detail view and exit search (ESC)
    @kb.add('escape')
    def close_or_exit_search(event):
        if show_title_detail[0]:
            show_title_detail[0] = False
        elif search_mode[0]:
            # Exit search
            search_mode[0] = False
            search_query[0] = ""
            current_index[0] = 0
    
    # Layout configuration
    content_control = FormattedTextControl(
        lambda: render_content(),
        focusable=True
    )

    current_command_control = FormattedTextControl(lambda: get_current_command())
    status_control = FormattedTextControl(lambda: get_status_text())

    title_detail_control = FormattedTextControl(
        lambda: render_title_detail(),
        focusable=False
    )

    content_window = Window(content=content_control, height=page_size[0] + 2)
    current_command_window = Window(content=current_command_control, height=2)
    status_window = Window(content=status_control, height=1)

    title_detail_window = Window(content=title_detail_control, wrap_lines=True)

    # Convert title to FormattedText format (without style)
    def render_title():
        return [("", title)]

    # Use different layout depending on detail view display
    def get_container():
        if show_title_detail[0]:
            # Use full screen when showing detail
            return HSplit([title_detail_window])
        else:
            # Normal mode
            return HSplit([
                Window(content=FormattedTextControl(render_title), height=1),
                current_command_window,
                status_window,
                content_window,
            ])

    from prompt_toolkit.layout import DynamicContainer
    root_container = DynamicContainer(get_container)
    
    layout = Layout(root_container)
    layout.focus(content_window)
    
    # Run Application
    app = Application(
        layout=layout,
        key_bindings=kb,
        full_screen=False,
        mouse_support=False
    )
    
    try:
        result = app.run()
        return result
    except (KeyboardInterrupt, EOFError):
        return None


