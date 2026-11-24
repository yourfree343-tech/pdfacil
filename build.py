"""Compila PDFácil: imágenes, ficha de versión, programa (dist/PDFacil/PDFacil.exe) e instalador."""
import os
import shutil
import subprocess
import sys

from editor_pdf import APP_NAME, EXE_NAME, __publisher__, __version__

# 1) icono e imágenes (con fuentes reales: en otro proceso sin el modo offscreen)
subprocess.check_call([sys.executable, os.path.join("tools", "generar_imagenes.py")])

# 2) ficha de versión del .exe
nums = tuple(int(x) for x in (__version__.split(".") + ["0", "0", "0"])[:4])
with open("version_info.txt", "w", encoding="utf-8") as f:
    f.write(f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={nums}, prodvers={nums}, mask=0x3f, flags=0x0, OS=0x40004,
                    fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('0C0A04B0', [
      StringStruct('CompanyName', '{__publisher__}'),
      StringStruct('FileDescription', '{APP_NAME}'),
      StringStruct('FileVersion', '{__version__}'),
      StringStruct('InternalName', '{EXE_NAME}'),
      StringStruct('LegalCopyright', '© 2026 {__publisher__}'),
      StringStruct('OriginalFilename', '{EXE_NAME}.exe'),
      StringStruct('ProductName', '{APP_NAME}'),
      StringStruct('ProductVersion', '{__version__}')])]),
    VarFileInfo([VarStruct('Translation', [0x0C0A, 1200])])
  ]
)
""")

# 3) programa
old = os.path.join("dist", "EditorPDF")  # carpeta del nombre anterior
if os.path.isdir(old):
    shutil.rmtree(old, ignore_errors=True)
subprocess.check_call([
    sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed",
    "--name", EXE_NAME, "--icon", "icono.ico", "--version-file", "version_info.txt",
    "--collect-submodules", "winrt",
    "--collect-submodules", "pyhanko", "--collect-data", "pyhanko",
    "--collect-submodules", "pyhanko_certvalidator", "--collect-data", "pyhanko_certvalidator",
    "--collect-submodules", "comtypes",
    "--hidden-import", "aiohttp", "--hidden-import", "truststore", "--collect-data", "certifi",
    "--exclude-module", "PySide6.QtWebEngineCore", "--exclude-module", "PySide6.QtPdf",
    "--exclude-module", "PySide6.Qt3DCore", "--exclude-module", "PySide6.QtQuick",
    "--exclude-module", "pymupdf4llm", "--exclude-module", "pymupdf_layout", "--exclude-module", "tkinter",
    "main.py",
])

# Qt no necesita el OpenGL por software (el visor pinta sin OpenGL): 20 MB menos
gl = os.path.join("dist", EXE_NAME, "_internal", "PySide6", "opengl32sw.dll")
if os.path.exists(gl):
    os.remove(gl)

# 4) instalador (Inno Setup). El .iss tiene que estar en UTF-8 con BOM para que salgan bien las tildes.
iss = os.path.join("installer", "PDFacil.iss")
raw = open(iss, "rb").read()
if not raw.startswith(b"\xef\xbb\xbf"):
    open(iss, "wb").write(b"\xef\xbb\xbf" + raw)
ISCC_CANDIDATES = [
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"),
    r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    r"C:\Program Files\Inno Setup 6\ISCC.exe",
]
iscc = next((p for p in ISCC_CANDIDATES if os.path.exists(p)), None)
if iscc:
    subprocess.check_call([iscc, "/Q", f"/DMyAppVersion={__version__}", iss])
    print(f"Instalador: dist/{EXE_NAME}-{__version__}-instalador.exe")
else:
    print("Inno Setup no está instalado: no se genera el instalador (winget install JRSoftware.InnoSetup).")
