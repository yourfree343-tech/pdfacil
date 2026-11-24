"""Genera el icono y la ficha de versión, y empaqueta el programa en dist/EditorPDF/EditorPDF.exe"""
import os
import subprocess
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication([])
from editor_pdf import APP_NAME, __publisher__, __version__  # noqa: E402
from editor_pdf.icon import make_pixmap  # noqa: E402

make_pixmap(256).save("icono.ico", "ICO")

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
      StringStruct('InternalName', 'EditorPDF'),
      StringStruct('LegalCopyright', '© 2026 {__publisher__}'),
      StringStruct('OriginalFilename', 'EditorPDF.exe'),
      StringStruct('ProductName', '{APP_NAME}'),
      StringStruct('ProductVersion', '{__version__}')])]),
    VarFileInfo([VarStruct('Translation', [0x0C0A, 1200])])
  ]
)
""")

subprocess.check_call([
    sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed",
    "--name", "EditorPDF", "--icon", "icono.ico", "--version-file", "version_info.txt",
    "--collect-submodules", "winrt",
    "--collect-submodules", "pyhanko", "--collect-data", "pyhanko",
    "--collect-submodules", "pyhanko_certvalidator", "--collect-data", "pyhanko_certvalidator",
    "--collect-submodules", "comtypes",
    "--hidden-import", "aiohttp",
    "--exclude-module", "PySide6.QtWebEngineCore", "--exclude-module", "PySide6.QtPdf",
    "--exclude-module", "PySide6.Qt3DCore", "--exclude-module", "PySide6.QtQuick",
    "--exclude-module", "pymupdf4llm", "--exclude-module", "pymupdf_layout", "--exclude-module", "tkinter",
    "main.py",
])

# Qt no necesita el OpenGL por software (el visor pinta sin OpenGL): 20 MB menos
gl = os.path.join("dist", "EditorPDF", "_internal", "PySide6", "opengl32sw.dll")
if os.path.exists(gl):
    os.remove(gl)

# ---- instalador (Inno Setup)
ISCC_CANDIDATES = [
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"),
    r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    r"C:\Program Files\Inno Setup 6\ISCC.exe",
]
iscc = next((p for p in ISCC_CANDIDATES if os.path.exists(p)), None)
if iscc:
    subprocess.check_call([iscc, "/Q", f"/DMyAppVersion={__version__}", r"installer\EditorPDF.iss"])
    print(f"Instalador: dist\EditorPDF-{__version__}-instalador.exe")
else:
    print("Inno Setup no está instalado: no se genera el instalador (winget install JRSoftware.InnoSetup).")
