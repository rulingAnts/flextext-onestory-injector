#!/usr/bin/env python3
"""Entry point: python3 main.py  (or the PyInstaller build of it)."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
from injector.app import main
main()
