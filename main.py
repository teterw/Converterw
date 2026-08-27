import os
import sys

# Ensure the project root is always on sys.path, regardless of where Python is launched from
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from converterw.gui.app import run_app

if __name__ == "__main__":
    run_app()
