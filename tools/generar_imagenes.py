"""Genera las imágenes de PDFácil a partir del icono (editor_pdf/icon.py):

- icono.ico                      icono del .exe y del instalador (16-256 px, diseño simple en tamaños pequeños)
- installer/asistente*.bmp       panel lateral del instalador (100 % y 200 %)
- installer/asistente_peq*.bmp   logo pequeño de la cabecera del instalador
- docs/icono.png, docs/banner.png  imágenes para GitHub

Uso: python tools/generar_imagenes.py   (lo llama build.py)
"""
import io
import os
import sys

os.environ.pop("QT_QPA_PLATFORM", None)  # con fuentes reales (en modo offscreen no hay)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from PIL import Image  # noqa: E402
from PySide6.QtCore import QBuffer, QIODevice, QPointF, QRectF, Qt  # noqa: E402
from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QLinearGradient, QPainter  # noqa: E402

app = QGuiApplication.instance() or QGuiApplication([])
from editor_pdf import APP_NAME, __publisher__  # noqa: E402
from editor_pdf.icon import render  # noqa: E402

TAGLINE = "Edita, firma y organiza tus PDF"


def to_pil(qimg):
    buf = QBuffer()
    buf.open(QIODevice.WriteOnly)
    qimg.save(buf, "PNG")
    return Image.open(io.BytesIO(bytes(buf.data()))).convert("RGBA")


def gradient_bg(p, w, h):
    g = QLinearGradient(QPointF(0, 0), QPointF(w, h))
    g.setColorAt(0, QColor("#FF7A45"))
    g.setColorAt(0.55, QColor("#F0443A"))
    g.setColorAt(1, QColor("#C81E4B"))
    p.fillRect(QRectF(0, 0, w, h), g)


def font(px, bold=False):
    f = QFont("Segoe UI Variable Display")
    f.setFamilies(["Segoe UI Variable Display", "Segoe UI"])
    f.setPixelSize(int(px))
    f.setBold(bold)
    return f


def save_bmp(qimg, path):
    to_pil(qimg).convert("RGB").save(path, "BMP")


def make_ico(path):
    sizes = [16, 20, 24, 32, 40, 48, 64, 128, 256]
    frames = [to_pil(render(s)) for s in sizes]
    frames[-1].save(path, format="ICO", sizes=[(s, s) for s in sizes], append_images=frames[:-1])


def wizard_image(scale):
    w, h = 164 * scale, 314 * scale
    img = QImage(w, h, QImage.Format_ARGB32)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    gradient_bg(p, w, h)
    # círculos decorativos suaves
    p.setPen(Qt.NoPen)
    for cx, cy, r, a in ((0.9, 0.12, 0.55, 22), (0.05, 0.95, 0.6, 18), (0.6, 0.75, 0.25, 14)):
        p.setBrush(QColor(255, 255, 255, a))
        p.drawEllipse(QPointF(w * cx, h * cy), w * r, w * r)
    ic = render(int(96 * scale), small=False)
    p.drawImage(int((w - ic.width()) / 2), int(h * 0.2), ic)
    p.setPen(QColor("white"))
    p.setFont(font(26 * scale, True))
    p.drawText(QRectF(0, h * 0.2 + 108 * scale, w, 36 * scale), Qt.AlignCenter, APP_NAME)
    p.setFont(font(11.5 * scale))
    p.setPen(QColor(255, 255, 255, 230))
    p.drawText(QRectF(8 * scale, h * 0.2 + 146 * scale, w - 16 * scale, 44 * scale),
               Qt.AlignHCenter | Qt.AlignTop, "Edita, firma y organiza\ntus PDF")
    p.setFont(font(10 * scale))
    p.setPen(QColor(255, 255, 255, 190))
    p.drawText(QRectF(0, h - 30 * scale, w, 20 * scale), Qt.AlignCenter, __publisher__)
    p.end()
    return img


def wizard_small(scale):
    s = 55 * scale
    img = QImage(s, s, QImage.Format_ARGB32)
    img.fill(QColor("white"))
    p = QPainter(img)
    p.drawImage(0, 0, render(s))
    p.end()
    return img


def banner():
    w, h = 1280, 420
    img = QImage(w, h, QImage.Format_ARGB32)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    gradient_bg(p, w, h)
    p.setPen(Qt.NoPen)
    for cx, cy, r, a in ((1.0, 0.0, 380, 22), (0.0, 1.0, 300, 16), (0.78, 0.95, 160, 14)):
        p.setBrush(QColor(255, 255, 255, a))
        p.drawEllipse(QPointF(w * cx, h * cy), r, r)
    ic = render(230, small=False)
    p.drawImage(110, (h - 230) // 2, ic)
    p.setPen(QColor("white"))
    p.setFont(font(96, True))
    p.drawText(QRectF(390, 95, 860, 120), Qt.AlignLeft | Qt.AlignVCenter, APP_NAME)
    p.setFont(font(36))
    p.setPen(QColor(255, 255, 255, 235))
    p.drawText(QRectF(394, 215, 860, 56), Qt.AlignLeft | Qt.AlignVCenter, TAGLINE)
    p.setFont(font(24))
    p.setPen(QColor(255, 255, 255, 200))
    p.drawText(QRectF(396, 285, 860, 40), Qt.AlignLeft | Qt.AlignVCenter,
               "Para Windows · gratis · en español · " + __publisher__)
    p.end()
    return img


def main():
    os.makedirs(os.path.join(ROOT, "docs"), exist_ok=True)
    make_ico(os.path.join(ROOT, "icono.ico"))
    save_bmp(wizard_image(1), os.path.join(ROOT, "installer", "asistente.bmp"))
    save_bmp(wizard_image(2), os.path.join(ROOT, "installer", "asistente@2x.bmp"))
    save_bmp(wizard_small(1), os.path.join(ROOT, "installer", "asistente_peq.bmp"))
    save_bmp(wizard_small(2), os.path.join(ROOT, "installer", "asistente_peq@2x.bmp"))
    render(512, small=False).save(os.path.join(ROOT, "docs", "icono.png"))
    banner().save(os.path.join(ROOT, "docs", "banner.png"))
    print("Imágenes generadas.")


if __name__ == "__main__":
    main()
