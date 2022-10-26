import sys

from .config import Persistent
from .gui.main import run


def main():
    with Persistent() as persistent:
        run(persistent, sys.argv)


if __name__ == '__main__':
    main()
