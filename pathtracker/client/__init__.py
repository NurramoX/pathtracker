from .pclient import main as _pclient_main  # underscore suggests internal

def main():
    """Entry point for the client command-line interface."""
    _pclient_main()