"""Browser/client action tools."""

from .registry import (
    fill_current_form,
    highlight_page_item,
    navigate_to,
    open_entity,
    request_user_confirmation,
    show_action_preview,
    submit_current_form,
)

__all__ = [
    "navigate_to",
    "open_entity",
    "fill_current_form",
    "submit_current_form",
    "highlight_page_item",
    "show_action_preview",
    "request_user_confirmation",
]
