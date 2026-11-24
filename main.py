import os
import sys

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from editor_pdf.main_window import MainWindow


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--diagnostico":  # escribe el resultado en un archivo
        lines = []
        try:
            from editor_pdf import ocr
            eng, info = ocr.create_engine()
            lines.append(f"OCR: disponible={ocr.AVAILABLE} motor={eng is not None} idioma={info} {ocr.ERROR}")
        except Exception as e:
            lines.append(f"OCR: ERROR {e}")
        try:
            import tempfile

            import pymupdf
            from editor_pdf import signing, wincert
            certs = [c for c in wincert.signing_certificates() if c.personal and c.valid_now]
            lines.append(f"Certificados personales válidos: {len(certs)}")
            if certs:
                d = pymupdf.open()
                d.new_page().insert_text((72, 72), "Prueba de firma")
                out = os.path.join(tempfile.gettempdir(), "editorpdf_diagnostico.pdf")
                signing.sign_pdf(d.tobytes(), out, certs[0], box=(300, 700, 500, 770))
                r = signing.verify(open(out, "rb").read())[0]
                lines.append(f"Firma: correcta={r.get('ok')} íntegra={r.get('intact')} {r.get('error', '')}")
                os.remove(out)
        except Exception as e:
            lines.append(f"Firma: ERROR {e!r}")
        try:
            from editor_pdf import spell
            sp = spell.get()
            lines.append(f"Ortografía: {'idioma ' + sp.tag if sp else 'ERROR ' + str(spell.error())}"
                         + (f", sugerencia para 'prueva': {sp.suggest('prueva', 1)}" if sp else ""))
        except Exception as e:
            lines.append(f"Ortografía: ERROR {e!r}")
        try:
            from editor_pdf import updater
            info = updater.latest_release()
            lines.append(f"Actualizaciones: última publicada {info['version'] if info else 'ninguna'}")
        except Exception as e:
            lines.append(f"Actualizaciones: ERROR {e!r}")
        from editor_pdf import __version__
        lines.insert(0, f"Versión {__version__}")
        with open(sys.argv[2], "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return
    try:  # icono propio en la barra de tareas
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("EditorPDF.App")
    except Exception:
        pass
    app = QApplication(sys.argv)
    from editor_pdf import __publisher__, __version__
    app.setApplicationName("Editor PDF")
    app.setApplicationVersion(__version__)
    app.setOrganizationName(__publisher__)
    from editor_pdf import theme
    theme.install_spanish(app)
    theme.apply(app, QSettings("EditorPDF", "EditorPDF").value("theme", "system"))
    w = MainWindow()
    w.show()
    args = [a for a in sys.argv[1:] if os.path.exists(a)]
    if args:
        w.open_path(args[0])
    elif str(w.settings.value("startup", "welcome")) == "last" and w.recent_files():
        w.open_path(w.recent_files()[0])
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
