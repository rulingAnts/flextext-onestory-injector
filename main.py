#!/usr/bin/env python3
"""Entry point: python3 main.py  (or the PyInstaller build of it).

--selftest imports the whole app (including tkinter) and exits 0 without
opening a window. The Windows build script runs the FROZEN exe with this
flag, which is what catches packaging mistakes -- a missing module dies
here instead of on a field worker's machine.
"""
import os
import sys

if not getattr(sys, "frozen", False):
    # Source checkout: the package lives under src/. In the frozen app
    # PyInstaller bundles it, and this path does not exist.
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

if "--selftest" in sys.argv:
    import tkinter                          # noqa: F401
    from injector import app, align, flextext_reader, ose_serializer  # noqa: F401
    from injector import project, story_builder                       # noqa: F401
    print("selftest OK")
    sys.exit(0)

from injector.app import main
main()
