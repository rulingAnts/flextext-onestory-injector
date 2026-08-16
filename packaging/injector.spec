# -*- mode: python -*-
# PyInstaller onedir build. Run ON WINDOWS from anywhere:
#     python -m PyInstaller packaging/injector.spec --noconfirm
#
# All paths are anchored to this spec file via SPECPATH -- pathex given as
# a cwd-relative string is what shipped a build missing the whole injector
# package (ModuleNotFoundError on a tester's machine).
#
# onedir rather than onefile deliberately: no self-extraction step on
# village machines, faster start, and antivirus tools are far less
# suspicious of a plain folder than of a self-unpacking exe.

import os

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
SRC = os.path.join(ROOT, "src")

a = Analysis(
    [os.path.join(ROOT, "main.py")],
    pathex=[SRC],
    binaries=[],
    datas=[],
    # Belt and braces: even if static analysis misses the package, name it.
    hiddenimports=[
        "injector",
        "injector.app",
        "injector.align",
        "injector.flextext_reader",
        "injector.ose_serializer",
        "injector.project",
        "injector.story_builder",
    ],
    excludes=["numpy", "PIL", "matplotlib"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="FlexTextOneStoryInjector",
    console=False,          # windowed app; tracebacks go to the messagebox
    icon=None,
)
coll = COLLECT(exe, a.binaries, a.datas, name="FlexTextOneStoryInjector")
