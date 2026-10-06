"""jev-pii: proof of concept measuring whether TypeSafe's Jev can detect PII in bulk data."""

__version__ = "0.1.0"


def main() -> None:
    from jev_pii.cli import main as _main

    _main()
