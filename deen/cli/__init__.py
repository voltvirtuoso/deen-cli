"""Command-line interface: one module per command group.

    app.py       the Typer apps and the ``@command`` decorator
    _common.py   config access, init/error guard, shared option types
    setup.py     init
    quran.py, hadith.py, dua.py   list | read | random for each
    inspire.py   one random item of any type
    legacy.py    deprecated names (read-surah, categories, ...)
    habits.py    status, commit, log
    settings.py  config show/set/path
"""
