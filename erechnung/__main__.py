import sys
from . import __version__
if __name__ == "__main__":
    if sys.argv[1:] == ["--version"]:
        print(__version__)
        sys.exit(0)
    sys.exit("Aufruf: python -m erechnung --version")
