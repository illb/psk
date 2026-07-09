"""
Questionary-based prompt utilities
Common error handling and consistent interface
"""
from typing import Optional, List, Any
import questionary
from .exceptions import CancelledError


def select_yes_no(
    message: str,
    default: bool = False,
    raise_on_cancel: bool = True
) -> Optional[bool]:
    """
    Yes/No question (questionary.select wrapper)
    
    Args:
        message: Question message
        default: Default value (True/False)
        raise_on_cancel: Whether to raise exception on cancel (False returns None)
    
    Returns:
        True/False or None (on cancel)
    
    Raises:
        KeyboardInterrupt: When Ctrl+C is pressed
        CancelledError: When cancelled with ESC (if raise_on_cancel=True)
    """
    try:
        choices = [
            questionary.Choice(title="Yes", value=True),
            questionary.Choice(title="No", value=False)
        ]
        
        # questionary.select's default must receive value (not title)
        result = questionary.select(
            message,
            choices=choices,
            default=default
        ).ask()
        
        if result is None:
            if raise_on_cancel:
                raise CancelledError()
            return None
        
        return result
    except KeyboardInterrupt:
        raise
    except CancelledError:
        if raise_on_cancel:
            raise
        return None
    except Exception:
        # Return None in non-interactive environments
        return None


def select_single(
    title: str,
    choices: List[tuple],
    default: Optional[Any] = None
) -> Optional[Any]:
    """
    Single selection (questionary.select wrapper)
    
    Args:
        title: Prompt title
        choices: List of (value, label) tuples
        default: Default selected value
    
    Returns:
        Selected value or None (on cancel)
    
    Raises:
        KeyboardInterrupt: When Ctrl+C is pressed
        CancelledError: When cancelled with ESC
    """
    try:
        # Convert to questionary.Choice objects
        questionary_choices = [
            questionary.Choice(
                title=label,
                value=value
            )
            for value, label in choices
        ]

        result = questionary.select(
            title,
            choices=questionary_choices,
            default=default,
            instruction="↑↓ Move, Enter Confirm, / Search"
        ).ask()

        if result is None:
            # Cancelled with ESC
            raise CancelledError()

        return result
    except KeyboardInterrupt:
        # Ctrl+C: propagate to parent
        raise
    except CancelledError:
        # Cancelled with ESC
        raise


def select_checkbox(
    title: str,
    choices: List[tuple],
    checked_values: Optional[List[Any]] = None,
) -> List[Any]:
    """
    Multi-selection (questionary.checkbox wrapper)

    Args:
        title: Prompt title
        choices: List of (value, label) tuples
        checked_values: Values that start pre-checked

    Returns:
        List of selected values (may be empty)

    Raises:
        KeyboardInterrupt: When Ctrl+C is pressed
        CancelledError: When cancelled with ESC
    """
    checked_values = checked_values or []
    try:
        questionary_choices = [
            questionary.Choice(
                title=label,
                value=value,
                checked=value in checked_values,
            )
            for value, label in choices
        ]

        result = questionary.checkbox(
            title,
            choices=questionary_choices,
            instruction="↑↓ Move, Space Toggle, Enter Confirm",
        ).ask()

        if result is None:
            # Cancelled with ESC
            raise CancelledError()

        return result
    except KeyboardInterrupt:
        raise
    except CancelledError:
        raise
