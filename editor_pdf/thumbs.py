"""Panel de miniaturas: navegar, reordenar arrastrando y menú de página."""
import pymupdf as fitz
from PySide6.QtCore import QItemSelectionModel, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QAbstractItemView, QFrame, QListView, QListWidget, QListWidgetItem, QMenu

from .view import pixmap_to_qimage

TW, TH = 128, 166


def _icon(pm):
    """Mismo dibujo en estado normal y seleccionado (sin el tinte azul de Qt)."""
    ic = QIcon()
    ic.addPixmap(pm, QIcon.Normal)
    ic.addPixmap(pm, QIcon.Selected)
    return ic


class ThumbPanel(QListWidget):
    pageActivated = Signal(int)
    orderChanged = Signal(list)
    action = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setViewMode(QListView.ListMode)
        self.setIconSize(QSize(TW, TH + 18))
        self.setSpacing(4)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.setObjectName("thumbs")
        self.setFrameShape(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.text_color = "#4b5563"
        self.itemClicked.connect(lambda it: self.pageActivated.emit(self.row(it)))
        self.customContextMenuRequested.connect(self._menu)
        self.pdf = None
        self._queue = []
        self._timer = QTimer(self, interval=0)
        self._timer.timeout.connect(self._work)

    def set_document(self, pdf):
        self.pdf = pdf
        self.rebuild()

    def rebuild(self):
        self.clear()
        self._queue = []
        if not self.pdf:
            return
        for i in range(self.pdf.doc.page_count):
            it = QListWidgetItem()
            it.setData(Qt.UserRole, i)
            it.setSizeHint(QSize(TW + 12, TH + 26))
            it.setIcon(_icon(self._canvas(None, i)))
            self.addItem(it)
        self._queue = list(range(self.pdf.doc.page_count))
        self._timer.start()

    def refresh(self, pages=None):
        if not self.pdf or pages is None or self.count() != self.pdf.doc.page_count:
            self.rebuild()
            return
        for i in pages:
            if i not in self._queue:
                self._queue.append(i)
        self._timer.start()

    def resizeEvent(self, e):
        # centra la columna de miniaturas en el panel
        sb = self.verticalScrollBar().sizeHint().width() if self.verticalScrollBar().isVisible() else 0
        m = max(0, (self.width() - sb - (TW + 16)) // 2)
        self.setViewportMargins(m, 6, 0, 6)
        super().resizeEvent(e)

    def set_theme(self, pal):
        self.text_color = pal["thumb_text"]
        if self.pdf:
            self.rebuild()

    def _dpr(self):
        return self.devicePixelRatioF() or 1.0

    def _canvas(self, img, i):
        dpr = self._dpr()
        pm = QPixmap(int(TW * dpr), int((TH + 18) * dpr))
        pm.setDevicePixelRatio(dpr)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.setRenderHint(QPainter.Antialiasing)
        if img is not None:
            w, h = img.width() / dpr, img.height() / dpr
            x, y = (TW - w) / 2, (TH - h) / 2
            p.setPen(Qt.NoPen)
            for k, a in ((3, 10), (1.5, 22)):  # sombra
                p.setBrush(QColor(0, 0, 0, a))
                p.drawRoundedRect(QRectF(x - k, y - k * 0.5, w + 2 * k, h + k * 2), k + 1, k + 1)
            p.drawImage(QRectF(x, y, w, h), img)
        else:
            p.fillRect(QRectF(22, 12, TW - 44, TH - 24), QColor(128, 128, 128, 40))
        p.setPen(QColor(self.text_color))
        p.drawText(QRectF(0, TH + 1, TW, 17), Qt.AlignCenter, str(i + 1))
        p.end()
        return pm

    def _work(self):
        if not self.pdf:
            self._timer.stop()
            return
        for _ in range(3):
            if not self._queue:
                self._timer.stop()
                return
            i = self._queue.pop(0)
            if i >= self.count() or i >= self.pdf.doc.page_count:
                continue
            page = self.pdf.doc[i]
            r = page.rect
            z = min(TW / r.width, TH / r.height) * self._dpr()
            pix = page.get_pixmap(matrix=fitz.Matrix(z, z), alpha=False)
            self.item(i).setIcon(_icon(self._canvas(pixmap_to_qimage(pix), i)))

    def set_current(self, i):
        if 0 <= i < self.count():
            self.blockSignals(True)
            flag = QItemSelectionModel.ClearAndSelect if len(self.selectedItems()) <= 1 else QItemSelectionModel.NoUpdate
            self.setCurrentRow(i, flag)
            self.blockSignals(False)
            self.scrollToItem(self.item(i))

    def selected_pages(self):
        return sorted(self.row(it) for it in self.selectedItems())

    def dropEvent(self, e):
        super().dropEvent(e)
        order = [self.item(r).data(Qt.UserRole) for r in range(self.count())]
        if order != list(range(len(order))):
            self.orderChanged.emit(order)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Delete:
            self.action.emit("delete")
        else:
            super().keyPressEvent(e)

    def _menu(self, pos):
        if not self.itemAt(pos):
            return
        m = QMenu(self)
        for key, label in (("rot_left", "Girar a la izquierda"), ("rot_right", "Girar a la derecha"),
                           (None, None), ("duplicate", "Duplicar"), ("blank", "Insertar página en blanco detrás"),
                           ("extract", "Extraer a un PDF nuevo…"), (None, None), ("delete", "Eliminar")):
            if key is None:
                m.addSeparator()
            else:
                m.addAction(label).triggered.connect(lambda _=False, k=key: self.action.emit(k))
        m.exec(self.viewport().mapToGlobal(pos))
