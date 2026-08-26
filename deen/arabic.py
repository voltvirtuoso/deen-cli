"""Arabic text normalization for reliable terminal rendering.

The APIs return Arabic in logical Unicode order.  Terminals that render an
LTR table or card need Arabic joining/shaping followed by bidi reordering.
Keeping this in one module prevents individual commands from displaying raw
Arabic differently.
"""

from __future__ import annotations

from typing import Optional

import arabic_reshaper
from bidi.algorithm import get_display


def prepare_arabic(text: Optional[str]) -> str:
    """Shape and reorder Arabic text for display in an LTR terminal.

    ``None`` is treated as an empty value so callers can safely pass optional
    API fields.  The input is not mutated; it is converted to ``str`` so the
    helper is also safe for values returned by loosely typed APIs.
    """
    if not text:
        return ""
    return get_display(arabic_reshaper.reshape(str(text)))
