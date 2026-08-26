"""Interactive terminal paging that preserves Unicode on Windows and Unix."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys


def _run_external(command: str, args: list[str], content: str) -> bool:
    """Send UTF-8 content directly to an installed pager."""
    try:
        env = os.environ.copy()
        env.setdefault("LESSCHARSET", "utf-8")
        completed = subprocess.run(
            [command, *args],
            input=content,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            check=False,
        )
        return completed.returncode == 0
    except (OSError, UnicodeError):
        return False


def _interactive_fallback(content: str) -> None:
    """Small less-like fallback when neither less nor bat is installed."""
    if os.name != "nt":
        sys.stdout.write(content)
        sys.stdout.flush()
        return

    import msvcrt

    lines = content.splitlines()
    height = max(5, shutil.get_terminal_size((100, 25)).lines - 2)
    offset = 0

    def draw() -> None:
        end = min(len(lines), offset + height)
        sys.stdout.write("\x1b[2J\x1b[H")
        sys.stdout.write("\n".join(lines[offset:end]))
        sys.stdout.write(
            f"\n\x1b[2m-- lines {offset + 1}-{end} of {len(lines)} | "
            "Space/Down next, b/Up previous, q quit --\x1b[0m"
        )
        sys.stdout.flush()

    while True:
        draw()
        key = msvcrt.getwch()
        if key in ("q", "Q", "\x1b"):
            break
        if key == " ":
            offset = min(max(0, len(lines) - height), offset + height)
        elif key in ("b", "B"):
            offset = max(0, offset - height)
        elif key in ("\r", "j"):
            offset = min(max(0, len(lines) - height), offset + 1)
        elif key == "k":
            offset = max(0, offset - 1)
        elif key in ("\x00", "\xe0"):
            arrow = msvcrt.getwch()
            if arrow == "H":
                offset = max(0, offset - 1)
            elif arrow == "P":
                offset = min(max(0, len(lines) - height), offset + 1)
            elif arrow == "I":
                offset = min(max(0, len(lines) - height), offset + height)
            elif arrow == "Q":
                offset = max(0, offset - height)

    sys.stdout.write("\x1b[0m\n")
    sys.stdout.flush()


def page_text(content: str) -> None:
    """Display content in an interactive less/bat-like pager.

    Direct output is used when stdout is redirected, which keeps piping and
    automated tests predictable. Interactive terminals prefer ``less`` and
    then ``bat``. Both receive Unicode text through a UTF-8 subprocess pipe,
    avoiding the Windows ``pydoc.pager`` conversion that produced literal
    ``\\uXXXX`` output.
    """
    if not content:
        return
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        sys.stdout.write(content)
        sys.stdout.flush()
        return

    less = shutil.which("less")
    if less and _run_external(less, ["-R"], content):
        return

    bat = shutil.which("bat")
    if bat and _run_external(
        bat,
        ["--paging=always", "--style=plain", "--language=txt", "--color=never", "-"],
        content,
    ):
        return

    _interactive_fallback(content)
