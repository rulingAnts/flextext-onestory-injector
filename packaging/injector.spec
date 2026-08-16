# -*- mode: python -*-
# PyInstaller onedir build. Run ON WINDOWS (the target platform):
#     pip install pyinstaller
#     pyinstaller packaging/injector.spec
# Output: dist/FlexTextOneStoryInjector/  (folder with the exe inside)
#
# onedir rather than onefile deliberately: no self-extraction step on
# village machines, faster start, and antivirus tools are far less
# suspicious of a plain folder than of a self-unpacking exe.

a = Analysis(
    ['../main.py'],
    pathex=['../src'],
    binaries=[],
    datas=[],
    hiddenimports=[],
    excludes=['numpy', 'PIL', 'matplotlib'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name='FlexTextOneStoryInjector',
    console=False,          # windowed app; tracebacks go to the messagebox
    icon=None,
)
coll = COLLECT(exe, a.binaries, a.datas, name='FlexTextOneStoryInjector')
