"""Documento PDF en memoria con deshacer/rehacer y operaciones de páginas."""
import os
from contextlib import contextmanager

import pymupdf as fitz

OPEN_FILTER = (
    "Documentos (*.pdf *.png *.jpg *.jpeg *.bmp *.gif *.tif *.tiff *.webp *.xps *.epub *.svg);;"
    "PDF (*.pdf);;Todos los archivos (*.*)"
)
IMAGE_FILTER = "Imágenes (*.png *.jpg *.jpeg *.bmp *.gif *.tif *.tiff *.webp)"

WINFONTS = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
_TTF = {
    "sans": ("arial.ttf", "arialbd.ttf", "ariali.ttf", "arialbi.ttf"),
    "serif": ("times.ttf", "timesbd.ttf", "timesi.ttf", "timesbi.ttf"),
    "mono": ("cour.ttf", "courbd.ttf", "couri.ttf", "courbi.ttf"),
}
_BASE14 = {
    "sans": ("helv", "hebo", "heit", "hebi"),
    "serif": ("tiro", "tibo", "tiit", "tibi"),
    "mono": ("cour", "cobo", "coit", "cobi"),
}


def pick_font(family, bold, italic):
    """Devuelve (fontname, fontfile) usando las fuentes de Windows si existen."""
    k = (1 if bold else 0) + (2 if italic else 0)
    path = os.path.join(WINFONTS, _TTF[family][k])
    if os.path.exists(path):
        return "E" + os.path.splitext(_TTF[family][k])[0], path
    return _BASE14[family][k], None


class PasswordNeeded(Exception):
    pass


def load_any(path, password=None):
    """Abre PDF, imágenes, XPS, EPUB... y devuelve siempre un PDF en memoria (sin bloquear el archivo)."""
    with open(path, "rb") as f:
        data = f.read()
    ext = os.path.splitext(path)[1].lower().lstrip(".") or "pdf"
    doc = fitz.open(stream=data, filetype=ext)
    if doc.needs_pass:
        if not password or not doc.authenticate(password):
            doc.close()
            raise PasswordNeeded()
        clear = doc.tobytes(encryption=fitz.PDF_ENCRYPT_NONE)
        doc.close()
        doc = fitz.open("pdf", clear)
    if not doc.is_pdf:
        pdf = doc.convert_to_pdf()
        doc.close()
        doc = fitz.open("pdf", pdf)
    return doc


def parse_ranges(text, n):
    """'1-3, 5, 7-' -> [[0,1,2],[4],[6..n-1]]"""
    groups = []
    for part in text.replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            a = int(a) if a.strip() else 1
            b = int(b) if b.strip() else n
        else:
            a = b = int(part)
        if a < 1 or b > n or a > b:
            raise ValueError(f"Rango no válido: {part}")
        groups.append(list(range(a - 1, b)))
    if not groups:
        raise ValueError("No has indicado ningún rango")
    return groups


def images_to_pdf(paths):
    out = fitz.open()
    for p in paths:
        img = fitz.open(p)
        out.insert_pdf(fitz.open("pdf", img.convert_to_pdf()))
        img.close()
    return out


class PdfDoc:
    MAX_UNDO_BYTES = 400 * 1024 * 1024

    def __init__(self, doc, path=None, password=None):
        self.doc = doc
        self.path = path
        self.user_pw = password
        self.owner_pw = password
        self.undo_stack = []
        self.redo_stack = []
        self.dirty = False
        self.fonts_added = False

    # ---------- apertura ----------
    @classmethod
    def open(cls, path, password=None):
        doc = load_any(path, password)
        is_pdf = path.lower().endswith(".pdf")
        return cls(doc, path if is_pdf else None, password)

    @property
    def name(self):
        return os.path.basename(self.path) if self.path else "Sin título.pdf"

    # ---------- deshacer ----------
    def _bytes(self):
        return self.doc.tobytes(garbage=0)

    def _restore(self, data):
        self.doc.close()
        self.doc = fitz.open("pdf", data)

    @contextmanager
    def change(self):
        snap = self._bytes()
        try:
            yield
        except Exception:
            self._restore(snap)
            raise
        self.undo_stack.append(snap)
        self.redo_stack.clear()
        total = sum(len(s) for s in self.undo_stack)
        while total > self.MAX_UNDO_BYTES and len(self.undo_stack) > 1:
            total -= len(self.undo_stack.pop(0))
        self.dirty = True

    def undo(self):
        if not self.undo_stack:
            return False
        self.redo_stack.append(self._bytes())
        self._restore(self.undo_stack.pop())
        self.dirty = True
        return True

    def redo(self):
        if not self.redo_stack:
            return False
        self.undo_stack.append(self._bytes())
        self._restore(self.redo_stack.pop())
        self.dirty = True
        return True

    # ---------- guardar ----------
    def _save_kwargs(self):
        kw = dict(garbage=3, deflate=True)
        if self.user_pw or self.owner_pw:
            kw.update(
                encryption=fitz.PDF_ENCRYPT_AES_256,
                user_pw=self.user_pw or "",
                owner_pw=self.owner_pw or self.user_pw or "",
            )
        else:
            kw["encryption"] = fitz.PDF_ENCRYPT_NONE
        return kw

    def save(self, path=None):
        path = path or self.path
        if self.fonts_added:
            try:
                self.doc.subset_fonts()
            except Exception:
                pass
        tmp = path + ".tmp~"
        self.doc.save(tmp, **self._save_kwargs())
        os.replace(tmp, path)
        self.path = path
        self.dirty = False

    # ---------- páginas ----------
    def rotate(self, pages, delta):
        for i in pages:
            p = self.doc[i]
            p.set_rotation((p.rotation + delta) % 360)

    def delete(self, pages):
        for i in sorted(set(pages), reverse=True):
            self.doc.delete_page(i)

    def insert_blank(self, at, like=None):
        if like is not None and 0 <= like < self.doc.page_count:
            r = self.doc[like].rect
            w, h = r.width, r.height
        else:
            w, h = fitz.paper_size("a4")
        self.doc.new_page(at, width=w, height=h)

    def duplicate(self, pages):
        for i in sorted(set(pages), reverse=True):
            self.doc.fullcopy_page(i, i + 1 if i + 1 < self.doc.page_count else -1)

    def reorder(self, order):
        self.doc.select(order)

    def insert_doc(self, src, at=-1):
        self.doc.insert_pdf(src, start_at=at)

    def extract(self, pages):
        out = fitz.open()
        for i in pages:
            out.insert_pdf(self.doc, from_page=i, to_page=i)
        return out

    # ---------- conversión ----------
    def export_images(self, pages, folder, base, fmt="png", dpi=150):
        for i in pages:
            pix = self.doc[i].get_pixmap(dpi=dpi, alpha=False)
            out = os.path.join(folder, f"{base}_pag{i + 1:03d}.{fmt}")
            if fmt == "jpg":
                pix.save(out, jpg_quality=90)
            else:
                pix.save(out)
        return len(pages)

    def export_text(self, path):
        with open(path, "w", encoding="utf-8") as f:
            for page in self.doc:
                f.write(page.get_text())
                f.write("\n\f\n")

    def compress_to(self, path, dpi=120, quality=70):
        d = fitz.open("pdf", self._bytes())
        if hasattr(d, "rewrite_images"):
            try:
                d.rewrite_images(dpi_threshold=dpi + 20, dpi_target=dpi, quality=quality)
            except Exception:
                pass
        try:
            d.subset_fonts()
        except Exception:
            pass
        kw = self._save_kwargs()
        kw.update(garbage=4, deflate=True, deflate_images=True, deflate_fonts=True, clean=True)
        try:
            d.save(path, use_objstms=1, **kw)
        except TypeError:
            d.save(path, **kw)
        d.close()
