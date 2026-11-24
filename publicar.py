"""Publica en GitHub la versión actual: crea la etiqueta vX.Y.Z y la «release» con el instalador.

Antes: subir __version__ en editor_pdf/__init__.py, añadir la sección en NOVEDADES.md,
ejecutar build.py y hacer commit + push. Los programas instalados la verán en su próxima comprobación.
"""
import os
import re
import subprocess
import sys
import tempfile

from editor_pdf import APP_NAME, EXE_NAME, GITHUB_REPO, __version__

inst = os.path.join("dist", f"{EXE_NAME}-{__version__}-instalador.exe")
if not os.path.exists(inst):
    sys.exit(f"No existe {inst}: ejecuta antes build.py")
text = open("NOVEDADES.md", encoding="utf-8").read()
m = re.search(rf"^## {re.escape(__version__)}\s*\n(.*?)(?=^## |\Z)", text, re.S | re.M)
if not m:
    sys.exit(f"Falta la sección «## {__version__}» en NOVEDADES.md")
notes = m.group(1).strip()
fd, notes_file = tempfile.mkstemp(suffix=".md")
with os.fdopen(fd, "w", encoding="utf-8") as f:
    f.write(notes)
subprocess.check_call(["gh", "release", "create", f"v{__version__}", inst, "--repo", GITHUB_REPO,
                       "--title", f"{APP_NAME} {__version__}", "--notes-file", notes_file])
os.remove(notes_file)
print(f"Publicada la versión {__version__} en https://github.com/{GITHUB_REPO}/releases")
