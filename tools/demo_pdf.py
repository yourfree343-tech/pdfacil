"""Crea un PDF de ejemplo (datos inventados) para las capturas del README.

Uso: python tools/demo_pdf.py salida.pdf
"""
import os
import sys

import pymupdf as fitz

FONTS = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
REG = dict(fontname="Esegoe", fontfile=os.path.join(FONTS, "segoeui.ttf"))
BOLD = dict(fontname="Esegoeb", fontfile=os.path.join(FONTS, "segoeuib.ttf"))
INK = (0.13, 0.15, 0.2)
MUTED = (0.42, 0.45, 0.5)
ACCENT = (0.91, 0.27, 0.23)

out = sys.argv[1] if len(sys.argv) > 1 else "demo.pdf"
d = fitz.open()

# ---- página 1: propuesta
p = d.new_page()
W = p.rect.width
p.draw_rect(fitz.Rect(0, 0, W, 8), color=None, fill=ACCENT)
p.insert_text((56, 70), "Estudio Nébula", fontsize=20, color=ACCENT, **BOLD)
p.insert_text((56, 88), "Diseño y comunicación · Calle Mayor 12, Valencia", fontsize=9, color=MUTED, **REG)
p.insert_text((56, 150), "Propuesta comercial", fontsize=26, color=INK, **BOLD)
p.insert_text((56, 172), "Rediseño de la identidad visual · Referencia P-2026-041", fontsize=11, color=MUTED, **REG)
body = ("Gracias por confiar en nosotros. En esta propuesta detallamos el alcance del proyecto, "
        "el calendario y el presupuesto para renovar la imagen de la marca y adaptarla a los "
        "canales digitales. El plazo de entrega estimado es de seis semanas desde la aceptación.")
p.insert_textbox(fitz.Rect(56, 196, W - 56, 270), body, fontsize=11, color=INK, lineheight=1.5, **REG)
p.insert_text((56, 300), "Alcance del proyecto", fontsize=14, color=INK, **BOLD)
items = ["Estudio de la marca y de la competencia", "Logotipo, paleta de colores y tipografías",
         "Manual de identidad visual (PDF)", "Plantillas para redes sociales y presentaciones"]
y = 326
for it in items:
    p.draw_circle(fitz.Point(62, y - 4), 2.4, color=None, fill=ACCENT)
    p.insert_text((72, y), it, fontsize=11, color=INK, **REG)
    y += 22
p.insert_text((56, y + 22), "Presupuesto", fontsize=14, color=INK, **BOLD)
y += 40
rows = [("Concepto", "Horas", "Importe"), ("Estudio de marca", "12", "960 €"), ("Identidad visual", "30", "2.400 €"),
        ("Manual y plantillas", "18", "1.440 €"), ("Total (IVA no incluido)", "60", "4.800 €")]
for k, (a, b, c) in enumerate(rows):
    r = fitz.Rect(56, y, W - 56, y + 26)
    if k == 0:
        p.draw_rect(r, color=None, fill=(0.96, 0.96, 0.97))
    elif k == len(rows) - 1:
        p.draw_line(fitz.Point(56, y), fitz.Point(W - 56, y), color=INK, width=0.8)
    f = BOLD if k in (0, len(rows) - 1) else REG
    p.insert_text((66, y + 17), a, fontsize=10.5, color=INK, **f)
    p.insert_text((W - 230, y + 17), b, fontsize=10.5, color=INK, **f)
    p.insert_text((W - 130, y + 17), c, fontsize=10.5, color=INK, **f)
    if 0 < k < len(rows) - 1:
        p.draw_line(fitz.Point(56, y + 26), fitz.Point(W - 56, y + 26), color=(0.88, 0.89, 0.9), width=0.5)
    y += 26
p.insert_textbox(fitz.Rect(56, y + 24, W - 56, y + 80),
                 "Forma de pago: 40 % a la aceptación y 60 % a la entrega. Validez de la propuesta: 30 días.",
                 fontsize=10, color=MUTED, **REG)
p.insert_text((56, 760), "Firma del cliente", fontsize=10, color=MUTED, **REG)
p.draw_line(fitz.Point(56, 745), fitz.Point(240, 745), color=MUTED, width=0.6)

# anotaciones de ejemplo
words = p.get_text("words")
hl = [fitz.Rect(w[:4]) for w in words if w[4] in ("seis", "semanas")]
if hl:
    a = p.add_highlight_annot(hl)
    a.update()
tot = [fitz.Rect(w[:4]) for w in words if w[4] == "4.800"]
if tot:
    r = tot[-1]
    a = p.add_circle_annot(fitz.Rect(r.x0 - 8, r.y0 - 5, r.x1 + 22, r.y1 + 5))
    a.set_colors(stroke=ACCENT)
    a.set_border(width=2)
    a.update()
a = p.add_text_annot((W - 80, 300), "Revisar el plazo con el cliente", icon="Note")
a.update()
a = p.add_freetext_annot(fitz.Rect(330, 690, 540, 712), "¡Aprobado por dirección!", fontsize=12, fontname="helv",
                         text_color=(0.1, 0.45, 0.25))
a.update()

# ---- página 2: calendario
p2 = d.new_page()
p2.draw_rect(fitz.Rect(0, 0, W, 8), color=None, fill=ACCENT)
p2.insert_text((56, 90), "Calendario", fontsize=22, color=INK, **BOLD)
for k, (wk, txt) in enumerate((("Semana 1", "Reunión inicial y estudio de la marca"),
                               ("Semanas 2-3", "Propuestas de logotipo y paleta"),
                               ("Semanas 4-5", "Desarrollo del manual y las plantillas"),
                               ("Semana 6", "Entrega final y formación"))):
    y = 140 + k * 60
    p2.draw_rect(fitz.Rect(56, y, 160, y + 36), color=None, fill=(1, 0.93, 0.91))
    p2.insert_text((66, y + 23), wk, fontsize=11, color=ACCENT, **BOLD)
    p2.insert_text((176, y + 23), txt, fontsize=11, color=INK, **REG)

# ---- página 3: condiciones
p3 = d.new_page()
p3.draw_rect(fitz.Rect(0, 0, W, 8), color=None, fill=ACCENT)
p3.insert_text((56, 90), "Condiciones", fontsize=22, color=INK, **BOLD)
p3.insert_textbox(fitz.Rect(56, 110, W - 56, 400),
                  "Los derechos de uso de los diseños se transfieren al cliente tras el pago completo. "
                  "Se incluyen dos rondas de cambios en cada fase.", fontsize=11, color=INK, lineheight=1.5, **REG)
d.subset_fonts()
d.save(out, garbage=3, deflate=True)
print("PDF de ejemplo:", out)
