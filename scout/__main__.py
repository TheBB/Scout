import sys

from .gui.main import run
from .config import Persistent


def main():
    with Persistent() as persistent:
        sys.exit(run(persistent, sys.argv))
