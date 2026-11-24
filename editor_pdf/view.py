"""Visor de páginas continuo con herramientas de anotación y edición."""
import math

import pymupdf as fitz
from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QImage, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QFrame, QGraphicsItem, QGraphicsPixmapItem, QGraphicsRectItem, QGraphicsScene,
    QGraphicsView, QInputDialog, QMessageBox,
)

from .dialogs import TextDialog
from .document import IMAGE_FILTER, pick_font

GAP = 26


class T:
    HAND = "hand"
    SELECT = "select"
    TEXTSEL = "textsel"
    EDIT = "edit"
    TEXT = "text"
    NOTE = "note"
    HIGHLIGHT = "highlight"
    UNDERLINE = "underline"
    STRIKE = "strike"
    INK = "ink"
    RECT = "rect"
    ELLIPSE = "ellipse"
    ARROW = "arrow"
    LINE = "line"
    IMAGE = "image"
    SIGN = "sign"
    WHITEOUT = "whiteout"
    DIGSIGN = "digsign"


RECT_TOOLS = {T.TEXTSEL, T.HIGHLIGHT, T.UNDERLINE, T.STRIKE, T.RECT, T.ELLIPSE, T.IMAGE, T.SIGN, T.WHITEOUT, T.DIGSIGN}
LINE_TOOLS = {T.ARROW, T.LINE}
HIGHLIGHT_COLOR = (1.0, 0.9, 0.2)
TEXT_MARKUP = {fitz.PDF_ANNOT_HIGHLIGHT, fitz.PDF_ANNOT_UNDERLINE, fitz.PDF_ANNOT_STRIKE_OUT, fitz.PDF_ANNOT_SQUIGGLY}


def span_style(s):
    """Color, tamaño y tipo de letra aproximado de un span de get_text('dict')."""
    c = s["color"]
    font = s["font"].lower()
    flags = s["flags"]
    bold = bool(flags & 16) or any(k in font for k in ("bold", "black", "heavy", "semibold"))
    italic = bool(flags & 2) or "italic" in font or "oblique" in font
    if flags & 8 or "courier" in font or "mono" in font:
        family = "mono"
    elif (flags & 4 or any(k in font for k in ("times", "serif", "garamond", "georgia"))) and "sans" not in font:
        family = "serif"
    else:
        family = "sans"
    return dict(color=(((c >> 16) & 255) / 255, ((c >> 8) & 255) / 255, (c & 255) / 255), size=s["size"],
                family=family, bold=bold, italic=italic)


def pixmap_to_qimage(pix):
    fmt = QImage.Format_RGB888 if pix.n == 3 else QImage.Format_RGBA8888
    return QImage(pix.samples, pix.width, pix.height, pix.stride, fmt).copy()


class ShadowItem(QGraphicsItem):
    """Sombra suave detrás de una página (capas translúcidas, barato de pintar)."""

    def __init__(self, w, h, strength=1.0):
        super().__init__()
        self.w, self.h, self.strength = w, h, strength
        self.setZValue(-1)

    def boundingRect(self):
        return QRectF(-14, -10, self.w + 28, self.h + 26)

    def paint(self, p, opt, widget=None):
        p.setPen(Qt.NoPen)
        for k, a in ((12, 5), (8, 8), (5, 12), (2.5, 18), (1, 26)):
            p.setBrush(QColor(0, 0, 0, int(a * self.strength)))
            p.drawRoundedRect(QRectF(-k, -k * 0.6, self.w + 2 * k, self.h + k * 1.8), k + 2, k + 2)


class PageItem(QGraphicsRectItem):
    def __init__(self, index, w, h):
        super().__init__(0, 0, w, h)
        self.index = index
        self.setBrush(Qt.white)
        self.setPen(Qt.NoPen)
        self.pix = QGraphicsPixmapItem(self)
        self.pix.setTransformationMode(Qt.SmoothTransformation)
        self.rendered = False


class PageView(QGraphicsView):
    currentPageChanged = Signal(int)
    zoomChanged = Signal(float)
    modified = Signal(object)        # lista de páginas cambiadas o None (todas)
    message = Signal(str)
    widgetClicked = Signal(int, int)  # página, xref
    selectionChanged = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scn = QGraphicsScene(self)
        self.setScene(self.scn)
        self.setBackgroundBrush(QColor("#e7e9ec"))
        self.setFrameShape(QFrame.NoFrame)
        self.shadow_strength = 1.0
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        self.setFocusPolicy(Qt.StrongFocus)
        self.pdf = None
        self.zoom = 1.0
        self.items = []
        self.tool = T.HAND
        self.color = (0.85, 0.1, 0.1)
        self.width = 2.0
        self.fontsize = 12.0
        self.get_signature = None     # callback -> ruta PNG o None
        self.on_digital_sign = None   # callback(página, rect) para la firma con certificado
        self.drag = None
        self.preview = None
        self.temp_items = []
        self.results = []
        self.cur_result = -1
        self.result_items = []
        self.sel = None
        self.sel_item = None
        self._last_page = -1
        self._whiteout_warned = False
        self._timer = QTimer(self, singleShot=True, interval=40)
        self._timer.timeout.connect(self.render_visible)
        self.verticalScrollBar().valueChanged.connect(self._scrolled)
        self.horizontalScrollBar().valueChanged.connect(lambda _: self._timer.start())
        self.set_tool(T.HAND)

    # ------------------------------------------------------------ documento y dibujo
    def set_theme(self, pal):
        self.setBackgroundBrush(QColor(pal["canvas"]))
        self.shadow_strength = 1.8 if pal["dark"] else 1.0
        if self.pdf:
            self.rebuild()

    def set_document(self, pdf):
        self.pdf = pdf
        self.sel = None
        self.results = []
        self.cur_result = -1
        self.rebuild(keep=False)

    def _anchor(self):
        if not self.items:
            return (0, 0.0)
        top = self.mapToScene(0, 0).y()
        for it in self.items:
            r = it.sceneBoundingRect()
            if r.bottom() + GAP > top:
                return (it.index, (top - r.top()) / max(r.height(), 1))
        return (len(self.items) - 1, 0.0)

    def _scroll_to_y(self, y):
        sb = self.verticalScrollBar()
        sb.setValue(int(sb.value() + self.mapFromScene(QPointF(0, y)).y()))

    def rebuild(self, keep=True):
        anchor = self._anchor() if keep else (0, -GAP / 1000)
        self.preview = None
        self.sel_item = None
        self.temp_items = []
        self.result_items = []
        self.scn.clear()
        self.items = []
        if not self.pdf:
            self.scn.setSceneRect(0, 0, 1, 1)
            return
        y = GAP
        maxw = 100
        for i, page in enumerate(self.pdf.doc):
            r = page.rect
            w, h = r.width * self.zoom, r.height * self.zoom
            sh = ShadowItem(w, h, self.shadow_strength)
            sh.setPos(-w / 2, y)
            self.scn.addItem(sh)
            it = PageItem(i, w, h)
            it.setPos(-w / 2, y)
            self.scn.addItem(it)
            self.items.append(it)
            y += h + GAP
            maxw = max(maxw, w)
        self.scn.setSceneRect(-maxw / 2 - GAP, 0, maxw + 2 * GAP, y)
        i, f = anchor
        i = min(i, len(self.items) - 1)
        if i >= 0:
            r = self.items[i].sceneBoundingRect()
            self._scroll_to_y(r.top() + f * r.height())
        self._draw_results()
        self._draw_selection()
        self.render_visible()

    def refresh(self, pages=None):
        if not self.pdf:
            self.rebuild()
            return
        n = self.pdf.doc.page_count
        if pages is None or n != len(self.items):
            self.rebuild()
            return
        for i in pages:
            if not 0 <= i < n:
                continue
            r = self.pdf.doc[i].rect
            br = self.items[i].rect()
            if abs(r.width * self.zoom - br.width()) > 0.5 or abs(r.height * self.zoom - br.height()) > 0.5:
                self.rebuild()
                return
        for i in pages:
            if 0 <= i < n:
                self.items[i].rendered = False
        self._draw_selection()
        self.render_visible()

    def render_visible(self):
        if not self.pdf or not self.items:
            return
        vis = self.mapToScene(self.viewport().rect()).boundingRect()
        h = vis.height()
        near = vis.adjusted(0, -h * 0.6, 0, h * 0.6)
        far = vis.adjusted(0, -4 * h, 0, 4 * h)
        dpr = self.devicePixelRatioF()
        for it in self.items:
            r = it.sceneBoundingRect()
            if r.intersects(near):
                if not it.rendered:
                    self._render(it, dpr)
            elif not r.intersects(far) and not it.pix.pixmap().isNull():
                it.pix.setPixmap(QPixmap())
                it.rendered = False
        self._emit_page()

    def _render(self, it, dpr):
        page = self.pdf.doc[it.index]
        z = self.zoom * dpr
        pix = page.get_pixmap(matrix=fitz.Matrix(z, z), alpha=False, annots=True)
        qp = QPixmap.fromImage(pixmap_to_qimage(pix))
        qp.setDevicePixelRatio(dpr)
        it.pix.setPixmap(qp)
        it.rendered = True

    def _scrolled(self, _=None):
        self._timer.start()
        self._emit_page()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._timer.start()

    # ------------------------------------------------------------ navegación y zoom
    def current_page(self):
        if not self.items:
            return 0
        c = self.mapToScene(self.viewport().rect().center()).y()
        for it in self.items:
            if it.sceneBoundingRect().bottom() + GAP / 2 >= c:
                return it.index
        return len(self.items) - 1

    def _emit_page(self):
        p = self.current_page()
        if p != self._last_page:
            self._last_page = p
            self.currentPageChanged.emit(p)

    def goto_page(self, i):
        if 0 <= i < len(self.items):
            self._scroll_to_y(self.items[i].sceneBoundingRect().top() - GAP / 2)

    def set_zoom(self, z):
        z = max(0.1, min(8.0, z))
        if abs(z - self.zoom) < 1e-4:
            return
        self.zoom = z
        self.rebuild()
        self.zoomChanged.emit(z)

    def fit_width(self):
        if self.pdf and self.pdf.doc.page_count:
            w = self.pdf.doc[self.current_page()].rect.width
            self.set_zoom((self.viewport().width() - 2 * GAP - 4) / w)

    def fit_page(self):
        if self.pdf and self.pdf.doc.page_count:
            r = self.pdf.doc[self.current_page()].rect
            z = min((self.viewport().width() - 2 * GAP) / r.width, (self.viewport().height() - 2 * GAP) / r.height)
            page = self.current_page()
            self.set_zoom(z)
            self.goto_page(page)

    def wheelEvent(self, e):
        if e.modifiers() & Qt.ControlModifier:
            f = 1.15 if e.angleDelta().y() > 0 else 1 / 1.15
            self.set_zoom(self.zoom * f)
            e.accept()
        else:
            super().wheelEvent(e)

    # ------------------------------------------------------------ coordenadas
    def page_at(self, sp):
        for it in self.items:
            if it.sceneBoundingRect().contains(sp):
                return it.index
        return None

    def to_page(self, i, sp):
        it = self.items[i]
        page = self.pdf.doc[i]
        return fitz.Point((sp.x() - it.x()) / self.zoom, (sp.y() - it.y()) / self.zoom) * page.derotation_matrix

    def to_scene_rect(self, i, rect):
        page = self.pdf.doc[i]
        it = self.items[i]
        r = fitz.Rect(rect) * page.rotation_matrix
        r.normalize()
        z = self.zoom
        return QRectF(it.x() + r.x0 * z, it.y() + r.y0 * z, r.width * z, r.height * z)

    def _unrotated_rect(self, page):
        r = page.rect * page.derotation_matrix
        r.normalize()
        return r

    # ------------------------------------------------------------ herramientas
    def set_tool(self, t):
        self.tool = t
        self.setDragMode(QGraphicsView.ScrollHandDrag if t == T.HAND else QGraphicsView.NoDrag)
        if t in (T.TEXTSEL, T.EDIT, T.TEXT):
            self.viewport().setCursor(Qt.IBeamCursor)
        elif t == T.SELECT:
            self.viewport().setCursor(Qt.ArrowCursor)
        elif t == T.HAND:
            self.viewport().unsetCursor()
        else:
            self.viewport().setCursor(Qt.CrossCursor)
        if t != T.SELECT:
            self.select_annot(None)

    def _pen(self, dashed=False, color=None, width=None):
        c = QColor.fromRgbF(*(color or self.color))
        pen = QPen(c, width if width is not None else max(1.0, self.width * self.zoom),
                   Qt.DashLine if dashed else Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        pen.setCosmetic(width is not None)
        return pen

    def _clear_temp(self):
        for it in self.temp_items:
            if it.scene():
                self.scn.removeItem(it)
        self.temp_items = []

    def mousePressEvent(self, e):
        if self.pdf is None or e.button() != Qt.LeftButton or self.tool == T.HAND:
            return super().mousePressEvent(e)
        self.setFocus()
        self._clear_temp()
        sp = self.mapToScene(e.position().toPoint())
        i = self.page_at(sp)
        if i is None:
            self.select_annot(None)
            return
        p = self.to_page(i, sp)
        self.drag = {"i": i, "sp": sp, "p": p, "moved": False}
        t = self.tool
        if t == T.SELECT:
            page = self.pdf.doc[i]
            xref = self._annot_at(page, p)
            if xref:
                self.select_annot((i, xref))
                self.drag["move"] = xref
                self.preview = self.scn.addRect(self.sel_item.rect(), self._pen(True, (0.1, 0.4, 0.9), 1.5))
                self.preview.setZValue(20)
            else:
                self.select_annot(None)
                w = self._widget_at(page, p)
                if w:
                    self.widgetClicked.emit(i, w)
                self.drag = None
        elif t == T.INK:
            path = QPainterPath(sp)
            self.drag["path"] = path
            self.drag["pts"] = [p]
            self.preview = self.scn.addPath(path, self._pen())
        elif t in RECT_TOOLS:
            if t in (T.HIGHLIGHT, T.TEXTSEL):
                pen, brush = QPen(Qt.NoPen), QBrush(QColor(255, 220, 0, 70) if t == T.HIGHLIGHT else QColor(0, 120, 215, 50))
            elif t == T.WHITEOUT:
                pen, brush = QPen(QColor("#c00"), 1, Qt.DashLine), QBrush(QColor(255, 255, 255, 200))
            else:
                pen, brush = self._pen(t not in (T.RECT, T.ELLIPSE)), QBrush(Qt.NoBrush)
            self.preview = self.scn.addRect(QRectF(sp, sp), pen, brush)
        elif t in LINE_TOOLS:
            self.preview = self.scn.addLine(sp.x(), sp.y(), sp.x(), sp.y(), self._pen())
        if self.preview is not None:
            self.preview.setZValue(20)
        e.accept()

    def mouseMoveEvent(self, e):
        d = self.drag
        if not d:
            return super().mouseMoveEvent(e)
        sp = self.mapToScene(e.position().toPoint())
        if (sp - d["sp"]).manhattanLength() > 3:
            d["moved"] = True
        t = self.tool
        if t == T.SELECT and "move" in d:
            self.preview.setPos(sp - d["sp"])
        elif t == T.INK:
            d["path"].lineTo(sp)
            self.preview.setPath(d["path"])
            d["pts"].append(self.to_page(d["i"], sp))
        elif t in RECT_TOOLS and self.preview is not None:
            self.preview.setRect(QRectF(d["sp"], sp).normalized())
        elif t in LINE_TOOLS and self.preview is not None:
            self.preview.setLine(d["sp"].x(), d["sp"].y(), sp.x(), sp.y())

    def mouseReleaseEvent(self, e):
        d = self.drag
        if not d or e.button() != Qt.LeftButton:
            return super().mouseReleaseEvent(e)
        self.drag = None
        sp = self.mapToScene(e.position().toPoint())
        if self.preview is not None and self.preview.scene():
            self.scn.removeItem(self.preview)
        self.preview = None
        i, t = d["i"], self.tool
        p2 = self.to_page(i, sp)
        try:
            if t == T.SELECT:
                if d["moved"]:
                    self._move_annot(i, d["move"], p2.x - d["p"].x, p2.y - d["p"].y)
            elif t == T.INK:
                if len(d["pts"]) > 1:
                    self._add_ink(i, d["pts"])
            elif t in RECT_TOOLS:
                rect = fitz.Rect(d["p"], p2)
                rect.normalize()
                rect &= self._unrotated_rect(self.pdf.doc[i])
                self._rect_tool(t, i, rect, d["moved"], d["p"])
            elif t in LINE_TOOLS:
                if d["moved"]:
                    self._add_line(i, d["p"], p2, t == T.ARROW)
            elif t == T.TEXT:
                self._add_text(i, d["p"])
            elif t == T.NOTE:
                self._add_note(i, d["p"])
            elif t == T.EDIT:
                self._edit_text(i, d["p"])
        except Exception as ex:
            QMessageBox.warning(self, "Error", f"No se pudo completar la acción:\n{ex}")

    def mouseDoubleClickEvent(self, e):
        if self.tool == T.SELECT and self.sel:
            self.edit_selected()
            return
        super().mouseDoubleClickEvent(e)

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Delete, Qt.Key_Backspace) and self.sel:
            self.delete_selected()
        elif e.key() == Qt.Key_Escape:
            self.select_annot(None)
            self._clear_temp()
        else:
            super().keyPressEvent(e)

    # ------------------------------------------------------------ cambios en el PDF
    def _commit(self, pages, fn):
        with self.pdf.change():
            fn()
        self.modified.emit(pages)

    def _words_in(self, page, rect):
        return [w for w in page.get_text("words") if fitz.Rect(w[:4]).intersects(rect)]

    @staticmethod
    def _line_rects(words):
        groups = {}
        for w in words:
            key = (w[5], w[6])
            r = fitz.Rect(w[:4])
            groups[key] = groups[key] | r if key in groups else r
        return [groups[k] for k in sorted(groups)]

    @staticmethod
    def _words_text(words):
        out, last = [], None
        for w in sorted(words, key=lambda w: (w[5], w[6], w[7])):
            key = (w[5], w[6])
            if last is not None:
                out.append("\n" if key != last else " ")
            out.append(w[4])
            last = key
        return "".join(out)

    def _rect_tool(self, t, i, rect, moved, click):
        page = self.pdf.doc[i]
        if t in (T.TEXTSEL, T.HIGHLIGHT, T.UNDERLINE, T.STRIKE):
            if not moved:
                return
            words = self._words_in(page, rect)
            if not words:
                self.message.emit("Aquí no hay texto seleccionable. Si es un escaneo, usa Convertir > OCR.")
                return
            if t == T.TEXTSEL:
                QApplication.clipboard().setText(self._words_text(words))
                for r in self._line_rects(words):
                    it = self.scn.addRect(self.to_scene_rect(i, r), QPen(Qt.NoPen), QBrush(QColor(0, 120, 215, 70)))
                    it.setZValue(15)
                    self.temp_items.append(it)
                self.message.emit(f"Copiado al portapapeles ({len(words)} palabras).")
                return
            rects = self._line_rects(words)

            def fn():
                pg = self.pdf.doc[i]
                if t == T.HIGHLIGHT:
                    a = pg.add_highlight_annot(rects)
                    a.set_colors(stroke=HIGHLIGHT_COLOR)
                elif t == T.UNDERLINE:
                    a = pg.add_underline_annot(rects)
                    a.set_colors(stroke=self.color)
                else:
                    a = pg.add_strikeout_annot(rects)
                    a.set_colors(stroke=self.color)
                a.update()
            self._commit([i], fn)
        elif t in (T.RECT, T.ELLIPSE):
            if not moved or rect.width < 2 or rect.height < 2:
                return

            def fn():
                pg = self.pdf.doc[i]
                a = pg.add_rect_annot(rect) if t == T.RECT else pg.add_circle_annot(rect)
                a.set_colors(stroke=self.color)
                a.set_border(width=self.width)
                a.update()
            self._commit([i], fn)
        elif t == T.WHITEOUT:
            if not moved or rect.width < 2 or rect.height < 2:
                return
            if not self._whiteout_warned:
                r = QMessageBox.question(
                    self, "Borrar zona",
                    "Esto borra para siempre todo lo que hay en la zona (texto, imágenes y dibujos) "
                    "y la deja en blanco.\n\nSe puede deshacer con Ctrl+Z mientras no cierres el archivo. ¿Seguir?")
                if r != QMessageBox.Yes:
                    return
                self._whiteout_warned = True

            def fn():
                pg = self.pdf.doc[i]
                pg.add_redact_annot(rect, fill=(1, 1, 1))
                pg.apply_redactions()
            self._commit([i], fn)
        elif t == T.DIGSIGN:
            if not moved or rect.width < 30 or rect.height < 15:
                rect = fitz.Rect(click.x - 100, click.y - 32, click.x + 100, click.y + 32)
            if self.on_digital_sign:
                self.on_digital_sign(i, rect)
        elif t in (T.IMAGE, T.SIGN):
            if t == T.IMAGE:
                path, _ = QFileDialog.getOpenFileName(self, "Insertar imagen", "", IMAGE_FILTER)
            else:
                path = self.get_signature() if self.get_signature else None
            if not path:
                return
            img = QImage(path)
            if img.isNull():
                self.message.emit("No se pudo leer la imagen.")
                return
            if not moved or rect.width < 8 or rect.height < 8:
                w = 160.0 if t == T.SIGN else 200.0
                h = w * img.height() / max(img.width(), 1)
                rect = fitz.Rect(click.x - w / 2, click.y - h / 2, click.x + w / 2, click.y + h / 2)

            def fn():
                pg = self.pdf.doc[i]
                pg.insert_image(rect, filename=path, keep_proportion=True, rotate=(-pg.rotation) % 360)
            self._commit([i], fn)

    def _add_ink(self, i, pts):
        stroke = [(p.x, p.y) for p in pts]

        def fn():
            pg_ = self.pdf.doc[i]
            a = pg_.add_ink_annot([stroke])
            a.set_colors(stroke=self.color)
            a.set_border(width=self.width)
            a.update()
        self._commit([i], fn)

    def _add_line(self, i, p1, p2, arrow):
        def fn():
            pg_ = self.pdf.doc[i]
            a = pg_.add_line_annot(p1, p2)
            a.set_colors(stroke=self.color, fill=self.color)
            a.set_border(width=self.width)
            if arrow:
                a.set_line_ends(fitz.PDF_ANNOT_LE_NONE, fitz.PDF_ANNOT_LE_CLOSED_ARROW)
            a.update()
        self._commit([i], fn)

    @staticmethod
    def _freetext_rect(p, text, size):
        lines = text.split("\n")
        w = max(fitz.get_text_length(l, "helv", size) for l in lines) + size * 0.9
        h = len(lines) * size * 1.25 + size * 0.6
        return fitz.Rect(p.x, p.y, p.x + w, p.y + h)

    def _add_text(self, i, p):
        res = TextDialog.ask(self, "Añadir texto", size=self.fontsize, color=self.color)
        if not res:
            return
        self.fontsize = res["size"]
        page = self.pdf.doc[i]
        rot = page.rotation
        box = self._freetext_rect(fitz.Point(0, 0), res["text"], res["size"])
        # el clic es la esquina superior izquierda tal como se ve en pantalla
        vis = fitz.Point(p) * page.rotation_matrix
        corner = fitz.Rect(vis.x, vis.y, vis.x + box.width, vis.y + box.height) * page.derotation_matrix
        corner.normalize()

        def fn():
            pg_ = self.pdf.doc[i]
            a = pg_.add_freetext_annot(corner, res["text"], fontsize=res["size"], fontname="helv",
                                                   text_color=res["color"], rotate=rot)
            a.update()
        self._commit([i], fn)

    def _add_note(self, i, p):
        text, ok = QInputDialog.getMultiLineText(self, "Nota", "Texto de la nota:")
        if not ok or not text.strip():
            return

        def fn():
            pg_ = self.pdf.doc[i]
            a = pg_.add_text_annot(p, text, icon="Note")
            a.set_colors(stroke=(1, 0.8, 0.1))
            a.update()
        self._commit([i], fn)

    def _edit_text(self, i, p):
        page = self.pdf.doc[i]
        target = None
        for b in page.get_text("dict")["blocks"]:
            if b.get("type") != 0:
                continue
            for line in b["lines"]:
                if fitz.Rect(line["bbox"]).contains(p) and "".join(s["text"] for s in line["spans"]).strip():
                    target = line
        if not target:
            self.message.emit("Haz clic encima de una línea de texto. Si es un escaneo, pasa antes el OCR.")
            return
        spans = target["spans"]
        text = "".join(s["text"] for s in spans).replace("\xa0", " ")
        s0 = max(spans, key=lambda s: len(s["text"].strip()))
        st = span_style(s0)
        color, family, bold, italic = st["color"], st["family"], st["bold"], st["italic"]
        bbox = fitz.Rect(target["bbox"])
        it = self.scn.addRect(self.to_scene_rect(i, bbox), QPen(QColor(0, 120, 215), 1.5, Qt.DashLine))
        it.setZValue(15)
        self.temp_items.append(it)
        res = TextDialog.ask(self, "Editar texto", text=text, size=round(s0["size"], 1), color=color,
                             font_opts=True, family=family, bold=bold, italic=italic)
        self._clear_temp()
        if not res:
            return
        hh = bbox.height
        red = fitz.Rect(bbox.x0, bbox.y0 + hh * 0.15, bbox.x1, bbox.y1 - hh * 0.15)
        origin = fitz.Point(spans[0]["origin"])
        dx, dy = target["dir"]
        angle = math.degrees(math.atan2(-dy, dx))

        def fn():
            pg = self.pdf.doc[i]
            pg.add_redact_annot(red)
            pg.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE, graphics=fitz.PDF_REDACT_LINE_ART_NONE)
            fname, ffile = pick_font(res["family"], res["bold"], res["italic"])
            kw = dict(fontsize=res["size"], fontname=fname, color=res["color"])
            if ffile:
                kw["fontfile"] = ffile
                self.pdf.fonts_added = True
            if abs(angle) > 0.5:
                kw["morph"] = (origin, fitz.Matrix(-angle))
            pg.insert_text(origin, res["text"], **kw)
        self._commit([i], fn)
        self.message.emit("Texto modificado.")

    def replace_word(self, i, rect, new_text):
        """Sustituye la palabra que ocupa rect por new_text (vacío = borrarla), imitando su fuente."""
        page = self.pdf.doc[i]
        c = fitz.Point((rect.x0 + rect.x1) / 2, (rect.y0 + rect.y1) / 2)
        span, line = None, None
        for b in page.get_text("dict")["blocks"]:
            for ln in b.get("lines", []):
                for s in ln["spans"]:
                    if fitz.Rect(s["bbox"]).contains(c) and s["text"].strip():
                        span, line = s, ln
        if span is None:
            self.message.emit("No encuentro esa palabra en el PDF (puede que ya se haya cambiado).")
            return False
        dx, dy = line["dir"]
        if abs(dy) > 0.01:
            self.message.emit("Ese texto está girado: corrígelo con la herramienta «Editar texto».")
            return False
        st = span_style(span)
        baseline = span["origin"][1]
        # espacio disponible hasta la palabra siguiente de la misma línea
        words = page.get_text("words")
        here = [w for w in words if fitz.Rect(w[:4]).contains(c)]
        avail = None
        if here:
            b0, l0 = here[0][5], here[0][6]
            nxt = [w[0] for w in words if w[5] == b0 and w[6] == l0 and w[0] > rect.x1 - 0.5]
            if nxt:
                avail = min(nxt) - rect.x0 - st["size"] * 0.25
        h = rect.height
        red = fitz.Rect(rect.x0, rect.y0 + h * 0.15, rect.x1, rect.y1 - h * 0.15)
        # palabras de la misma línea a la derecha, con su posición y estilo (por si MuPDF las desplaza)
        spans = [s for b in page.get_text("dict")["blocks"] for ln in b.get("lines", []) for s in ln["spans"]]
        right = []
        for w in words:
            wr = fitz.Rect(w[:4])
            if wr.x0 >= rect.x1 - 0.5 and abs((wr.y0 + wr.y1) / 2 - c.y) < h * 0.4:
                wc = fitz.Point((wr.x0 + wr.x1) / 2, (wr.y0 + wr.y1) / 2)
                sp = next((s for s in spans if fitz.Rect(s["bbox"]).contains(wc)), span)
                right.append(dict(text=w[4], x0=wr.x0, y=wc.y, base=sp["origin"][1], st=span_style(sp)))

        def write(pg, x, base, text, style, max_w=None):
            fn_, ff_ = pick_font(style["family"], style["bold"], style["italic"])
            kw = dict(fontsize=style["size"], fontname=fn_, color=style["color"])
            if ff_:
                kw["fontfile"] = ff_
                self.pdf.fonts_added = True
                width = fitz.Font(fontfile=ff_).text_length(text, fontsize=style["size"])
            else:
                width = fitz.get_text_length(text, fontname=fn_, fontsize=style["size"])
            origin = fitz.Point(x, base)
            if max_w and width > max_w:  # si no cabe, se estrecha un poco (como mucho un 25 %)
                kw["morph"] = (origin, fitz.Matrix(max(max_w / width, 0.75), 1))
            pg.insert_text(origin, text, **kw)

        def fn():
            pg = self.pdf.doc[i]
            pg.add_redact_annot(red)
            pg.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE, graphics=fitz.PDF_REDACT_LINE_ART_NONE)
            # MuPDF a veces calcula mal el hueco y corre el resto de la línea: se detecta y se recoloca
            if right:
                now = pg.get_text("words")
                first = right[0]
                cand = [w for w in now if w[4] == first["text"] and abs((w[1] + w[3]) / 2 - first["y"]) < h * 0.4]
                moved = bool(cand) and min(abs(w[0] - first["x0"]) for w in cand) > 0.3
                # al borrar una palabra (p. ej. repetida) se cierra el hueco corriendo el resto de la línea
                shift = (first["x0"] - rect.x0) if not new_text else 0.0
                if moved or shift:
                    line_end = max(r["x0"] for r in right) + 500
                    pg.add_redact_annot(fitz.Rect(rect.x0, red.y0, line_end, red.y1))
                    pg.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE, graphics=fitz.PDF_REDACT_LINE_ART_NONE)
                    for r in right:
                        write(pg, r["x0"] - shift, r["base"], r["text"], r["st"])
            if new_text:
                write(pg, rect.x0, baseline, new_text, st, avail)
        self._commit([i], fn)
        return True

    # ------------------------------------------------------------ selección de anotaciones
    def _annot_at(self, page, p):
        found = None
        for a in page.annots():
            r = a.rect
            if fitz.Rect(r.x0 - 3, r.y0 - 3, r.x1 + 3, r.y1 + 3).contains(p):
                found = a.xref
        return found

    def _widget_at(self, page, p):
        for w in page.widgets():
            if w.rect.contains(p):
                return w.xref
        return None

    def select_annot(self, sel):
        self.sel = sel
        self._draw_selection()
        self.selectionChanged.emit(sel is not None)

    def _draw_selection(self):
        if self.sel_item is not None and self.sel_item.scene():
            self.scn.removeItem(self.sel_item)
        self.sel_item = None
        if not self.sel or not self.pdf:
            return
        i, xref = self.sel
        pg_ = self.pdf.doc[i] if i < self.pdf.doc.page_count else None
        try:
            a = pg_.load_annot(xref) if pg_ is not None else None
        except Exception:
            a = None
        if a is None:
            self.sel = None
            return
        r = self.to_scene_rect(i, a.rect).adjusted(-3, -3, 3, 3)
        self.sel_item = self.scn.addRect(r, self._pen(True, (0.1, 0.4, 0.9), 1.5))
        self.sel_item.setZValue(18)

    def delete_selected(self):
        if not self.sel:
            return
        i, xref = self.sel
        self.sel = None

        def fn():
            pg = self.pdf.doc[i]
            pg.delete_annot(pg.load_annot(xref))
        self._commit([i], fn)
        self.selectionChanged.emit(False)

    def _move_annot(self, i, xref, dx, dy):
        page = self.pdf.doc[i]
        a = page.load_annot(xref)
        typ = a.type[0]
        if typ in TEXT_MARKUP:
            self.message.emit("Los resaltados van pegados al texto: bórralos y vuelve a crearlos.")
            return
        result = {}
        self.sel = None

        def fn():
            pg = self.pdf.doc[i]
            an = pg.load_annot(xref)
            if typ in (fitz.PDF_ANNOT_INK, fitz.PDF_ANNOT_LINE):
                colors, width = an.colors, an.border.get("width", 1) or 1
                verts, ends, opacity = an.vertices, an.line_ends, an.opacity
                pg.delete_annot(an)
                if typ == fitz.PDF_ANNOT_INK:
                    new = pg.add_ink_annot([[(x + dx, y + dy) for x, y in s] for s in verts])
                else:
                    (x1, y1), (x2, y2) = verts[0], verts[1]
                    new = pg.add_line_annot((x1 + dx, y1 + dy), (x2 + dx, y2 + dy))
                    if ends:
                        new.set_line_ends(*ends)
                new.set_colors(stroke=colors.get("stroke"), fill=colors.get("fill"))
                new.set_border(width=width)
                if opacity is not None and 0 <= opacity < 1:
                    new.set_opacity(opacity)
                new.update()
                result["xref"] = new.xref
            else:
                r = an.rect
                an.set_rect(fitz.Rect(r.x0 + dx, r.y0 + dy, r.x1 + dx, r.y1 + dy))
                an.update()
                result["xref"] = xref
        self._commit([i], fn)
        self.sel = (i, result.get("xref", xref))
        self._draw_selection()

    def edit_selected(self):
        if not self.sel:
            return
        i, xref = self.sel
        pg_ = self.pdf.doc[i]
        a = pg_.load_annot(xref)
        typ = a.type[0]
        content = a.info.get("content", "")
        if typ == fitz.PDF_ANNOT_FREE_TEXT:
            res = TextDialog.ask(self, "Editar texto", text=content, size=self.fontsize, color=self.color)
            if not res:
                return

            def fn():
                pg_ = self.pdf.doc[i]
                an = pg_.load_annot(xref)
                r = an.rect
                nr = self._freetext_rect(fitz.Point(r.x0, r.y0), res["text"], res["size"])
                if self.pdf.doc[i].rotation in (90, 270):
                    nr = fitz.Rect(r.x0, r.y0, r.x0 + nr.height, r.y0 + nr.width)
                an.set_info(content=res["text"])
                an.set_rect(nr)
                an.update(fontsize=res["size"], text_color=res["color"])
            self._commit([i], fn)
        elif typ == fitz.PDF_ANNOT_TEXT:
            text, ok = QInputDialog.getMultiLineText(self, "Nota", "Texto de la nota:", content)
            if not ok:
                return

            def fn():
                pg_ = self.pdf.doc[i]
                an = pg_.load_annot(xref)
                an.set_info(content=text)
                an.update()
            self._commit([i], fn)
        elif typ not in TEXT_MARKUP and typ != fitz.PDF_ANNOT_WIDGET:
            def fn():
                pg_ = self.pdf.doc[i]
                an = pg_.load_annot(xref)
                an.set_colors(stroke=self.color)
                an.set_border(width=self.width)
                an.update()
            self._commit([i], fn)
            self.message.emit("Aplicados el color y el grosor actuales.")
        self._draw_selection()

    # ------------------------------------------------------------ búsqueda
    def search(self, text):
        self.results = []
        self.cur_result = -1
        if self.pdf and text:
            for page in self.pdf.doc:
                for r in page.search_for(text):
                    self.results.append((page.number, r))
        self._draw_results()
        return len(self.results)

    def _draw_results(self):
        for it in self.result_items:
            if it.scene():
                self.scn.removeItem(it)
        self.result_items = []
        for k, (i, r) in enumerate(self.results):
            if i >= len(self.items):
                continue
            col = QColor(255, 120, 0, 120) if k == self.cur_result else QColor(255, 230, 0, 100)
            it = self.scn.addRect(self.to_scene_rect(i, r), QPen(Qt.NoPen), QBrush(col))
            it.setZValue(10)
            self.result_items.append(it)

    def show_result(self, k):
        if not self.results:
            return
        self.cur_result = k % len(self.results)
        self._draw_results()
        i, r = self.results[self.cur_result]
        self.ensureVisible(self.to_scene_rect(i, r), 80, 120)

    def flash(self, i, rect):
        self._clear_temp()
        sr = self.to_scene_rect(i, rect)
        self.ensureVisible(sr, 80, 120)
        it = self.scn.addRect(sr.adjusted(-2, -2, 2, 2), QPen(QColor(0, 120, 215), 2), QBrush(QColor(0, 120, 215, 40)))
        it.setZValue(15)
        self.temp_items.append(it)
