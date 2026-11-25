"""OCR con el motor que trae Windows 10/11 (Windows.Media.Ocr). Añade una capa de texto invisible."""
import asyncio
import os

import pymupdf as fitz

from .document import free_fontname

try:
    from winrt.windows.globalization import Language
    from winrt.windows.graphics.imaging import BitmapPixelFormat, SoftwareBitmap
    from winrt.windows.media.ocr import OcrEngine
    from winrt.windows.storage.streams import DataWriter

    AVAILABLE = True
    ERROR = ""
except Exception as e:  # pragma: no cover
    AVAILABLE = False
    ERROR = str(e)

ARIAL = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "arial.ttf")


def languages():
    if not AVAILABLE:
        return []
    return [(l.language_tag, l.display_name) for l in OcrEngine.available_recognizer_languages]


def create_engine(tag=None):
    """Devuelve (motor, nombre del idioma) o (None, motivo)."""
    if not AVAILABLE:
        return None, "No se pudo cargar el OCR de Windows: " + ERROR
    tags = [tag] if tag else ["es-ES", "es", "en-US", "en"]
    for t in tags:
        try:
            lang = Language(t)
            if OcrEngine.is_language_supported(lang):
                return OcrEngine.try_create_from_language(lang), lang.display_name
        except Exception:
            pass
    eng = OcrEngine.try_create_from_user_profile_languages()
    if eng is None:
        return None, ("Windows no tiene ningún idioma de OCR instalado. Instálalo en "
                      "Configuración > Hora e idioma > Idioma > Español > Opciones > Reconocimiento óptico de caracteres.")
    return eng, eng.recognizer_language.display_name


async def _recognize(engine, pix):
    w = DataWriter()
    w.write_bytes(pix.samples)
    bmp = SoftwareBitmap.create_copy_from_buffer(w.detach_buffer(), BitmapPixelFormat.GRAY8, pix.width, pix.height)
    res = await engine.recognize_async(bmp)
    out = []
    for line in res.lines:
        for word in line.words:
            r = word.bounding_rect
            out.append((word.text, r.x, r.y, r.width, r.height))
    return out


def ocr_page(page, engine):
    """Reconoce la página y añade el texto invisible. Devuelve el número de palabras."""
    r = page.rect
    dpi = min(300.0, OcrEngine.max_image_dimension * 72.0 / max(r.width, r.height) * 0.98)
    z = dpi / 72.0
    pix = page.get_pixmap(matrix=fitz.Matrix(z, z), colorspace=fitz.csGRAY, alpha=False, annots=False)
    words = asyncio.run(_recognize(engine, pix))
    if not words:
        return 0
    der = page.derotation_matrix
    lin = fitz.Matrix(der.a, der.b, der.c, der.d, 0, 0)
    use_arial = os.path.exists(ARIAL)
    fkw = dict(fontname=free_fontname(page, "Earial"), fontfile=ARIAL) if use_arial else dict(fontname="helv")
    shape = page.new_shape()
    for text, x, y, w, h in words:
        rr = fitz.Rect(x / z, y / z, (x + w) / z, (y + h) / z)
        fs = max(rr.height, 4)
        tl = fitz.get_text_length(text, "helv", fs)
        sx = rr.width / tl if tl > 0 else 1
        o = fitz.Point(rr.x0, rr.y1 - rr.height * 0.2) * der
        shape.insert_text(o, text, fontsize=fs, render_mode=3,
                          morph=(o, fitz.Matrix(sx, 0, 0, 1, 0, 0) * lin), **fkw)
    shape.commit()
    return len(words)
