"""Errors that are the user's to fix, not bugs."""


class UserError(ValueError):
    """Bad input or a declined action. The CLI shows it as a warning and exits 1."""
