from .pserver import main as _pserver_main  # underscore suggests internal

def main():
    """Entry point for the client command-line interface."""
    _pserver_main()
