"""Arabic text normalization for reliable terminal rendering.

The APIs return Arabic in logical Unicode order.  Terminals that render an
LTR table or card need Arabic joining/shaping followed by bidi reordering.
Keeping this in one module prevents individual commands from displaying raw
Arabic differently.
"""

from __future__ import annotations

import re
from typing import Optional

import arabic_reshaper
from bidi.algorithm import get_display


_UNICODE_ESCAPE_RE = re.compile(r"\\u([0-9a-fA-F]{4})|\\U([0-9a-fA-F]{8})")


def _decode_unicode_escapes(text: str) -> str:
    """Decode literal ``\\uXXXX``/``\\UXXXXXXXX`` sequences if present."""
    return _UNICODE_ESCAPE_RE.sub(
        lambda match: chr(int(match.group(1) or match.group(2), 16)),
        text,
    )


def prepare_arabic(text: Optional[str]) -> str:
    """Shape and reorder Arabic text for display in an LTR terminal.

    ``None`` is treated as an empty value so callers can safely pass optional
    API fields. The helper also repairs literal Unicode escape sequences found
    in some cached/API payloads before shaping, without decoding unrelated
    backslash text.
    """
    if not text:
        return ""
    logical_text = _decode_unicode_escapes(str(text))
    return get_display(arabic_reshaper.reshape(logical_text))
