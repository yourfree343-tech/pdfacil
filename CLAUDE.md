# Editor PDF

Programa de escritorio para Windows para ver y editar PDF, al estilo de Acrobat. Editor: Agencia Daga (no poner nombres de personas en la app).
Python 3.11 + PySide6 (Qt) + PyMuPDF; firma digital con pyHanko; OCR y corrector con los motores de Windows.
Toda la interfaz y los mensajes van en español.

## Comandos
- Ejecutar: `.venv\Scripts\python main.py [archivo.pdf]`
- Compilar el .exe: `.venv\Scripts\python build.py`. Genera `dist\EditorPDF\EditorPDF.exe`, al que apunta
  el acceso directo «Editor PDF» del escritorio. Antes de compilar, cierra el programa si está abierto.
- Diagnóstico del .exe (OCR, firma con el certificado real, ortografía):
  `dist\EditorPDF\EditorPDF.exe --diagnostico salida.txt`. Es una app sin consola: escribe en el archivo.
- Pruebas (sin pantalla, `QT_QPA_PLATFORM=offscreen`; usa `PYTHONIOENCODING=utf-8` para ver la salida):
  - `tests\prueba_auto.py <carpeta>`: anotaciones, editar texto, formularios, páginas, deshacer, OCR,
    guardar, comprimir y contraseña. Debe terminar con `TODO OK`.
  - `tests\prueba_ortografia.py <carpeta>`: revisión y corrección ortográfica.
  - `tests\prueba_actualizacion.py`: botón «Buscar actualizaciones» contra GitHub; los avisos deben salir en el hilo principal.
  - `tests\prueba_firma.py <muestra.pdf> <carpeta>`: firma desde la interfaz con el certificado real de
    la FNMT; necesita internet. Los PDF firmados llevan el nombre y el DNI del usuario: escríbelos en el
    scratchpad, bórralos después y no muestres el DNI en la salida.
  - Las capturas en modo offscreen salen sin letras (cuadraditos): es normal. Para ver la interfaz real,
    abre la ventana y usa `grab()`.

## Versión
`editor_pdf/__init__.py` (`__version__`, `__publisher__`, `GITHUB_REPO`). Sube la versión con cada cambio que se
entregue: se muestra en Ayuda > Acerca de y `build.py` la copia a las propiedades del .exe.
Historial en `NOVEDADES.md`.

## Estructura (`editor_pdf/`)
- `document.py`: `PdfDoc`, el PDF en memoria (se abre desde bytes para no bloquear el archivo).
  Deshacer y rehacer por instantáneas (`with pdf.change(): ...`), guardado y operaciones con páginas.
- `view.py`: `PageView`, el visor continuo, con todas las herramientas (`T.*`) y `replace_word`.
- `main_window.py`: menús, barras, abrir y guardar, páginas, OCR, conversión, firma digital y verificación.
- `thumbs.py` (miniaturas), `forms.py` (formularios), `dialogs.py`, `icon.py`.
- `ocr.py`: OCR de Windows (winrt) que añade una capa de texto invisible.
- `wincert.py`: certificados del almacén de Windows y firma con CNG (ctypes). La clave no sale de Windows.
- `signing.py`: firma PAdES (pyHanko) y verificación.
- `spell.py` (COM ISpellChecker, con comtypes) y `spell_ui.py` (subrayado al escribir y revisión del documento).
- `theme.py` (paletas claro/oscuro, QSS, barra de título y traducción de Qt al español) e `icons.py` (iconos SVG).
- `settings_dialog.py` (Ajustes y valores por defecto), `fileassoc.py` (registro .pdf en HKCU) y `updater.py`.

## Trampas conocidas (no las repitas)
- **PyMuPDF se cuelga** si usas una anotación cuya página ya se ha liberado:
  `doc[i].load_annot(x).rect` en una sola expresión rompe. Guarda antes la página: `pg = doc[i]; a = pg.load_annot(x)`.
- **Coordenadas:** las anotaciones, `get_text` y `search_for` usan coordenadas de la página *sin girar*.
  Visor → página: `÷ zoom × page.derotation_matrix`. Página → visor: `× page.rotation_matrix`.
  pyHanko usa coordenadas PDF con el origen abajo: `rect × page.transformation_matrix`.
- Las anotaciones de tinta y de línea no se mueven con `set_rect`: se recrean desplazadas (`_move_annot`).
- **Redacción parcial de una línea:** con fuentes que incrusta PyMuPDF (texto de «Editar texto», del OCR o de
  PDF creados con PyMuPDF), MuPDF calcula mal el hueco y corre el resto de la línea. Con PDF normales
  (Word, Qt) no pasa. `replace_word` lo detecta y vuelve a escribir esas palabras en su posición original.
- **asn1crypto + pyHanko:** pyHanko registra `qc_statements` en `ExtensionId._map`, pero no en el índice
  inverso. Si antes se han leído certificados, la validación de certificados cualificados (FNMT) falla.
  `signing.py` reconstruye `_reverse_map` al importarse: no lo quites.
- Un PDF firmado no se puede reescribir con PyMuPDF sin romper la firma. Si se guarda sin cambios se copia
  `pdf.source_bytes`, y con cambios se avisa antes. La firma se hace siempre sobre un archivo nuevo.
- La fuente Helvetica básica pierde el «€»: para texto nuevo usa Arial (`pick_font`); `subset_fonts()` al guardar.
- `fullcopy_page(i, i+1)` falla en la última página: usa `-1`.
- **Hilos de Qt:** nunca crees ventanas o avisos fuera del hilo principal. Una señal de un QThread conectada a una
  función suelta se ejecuta en ese hilo (así se colgaba la 1.3.1): recibe el resultado en un QObject del hilo principal.
- Las conexiones HTTPS van con `truststore` (certificados de Windows); con el `ssl` de Python fallaba la cadena de GitHub.
- En Git Bash, los heredocs largos con comillas fallan a veces («unexpected EOF»): escribe el script en un
  archivo y ejecútalo.

## Publicación y actualizaciones
- Repositorio público: https://github.com/yourfree343-tech/editor-pdf (cuenta de GitHub `yourfree343-tech`).
- Instalador: Inno Setup (`installer/EditorPDF.iss`), por usuario y sin administrador; lo genera `build.py`.
  En modo silencioso vuelve a abrir el programa (lo usan las actualizaciones).
- Actualización automática (`updater.py`): consulta `releases/latest` de GitHub, descarga el adjunto
  `*instalador.exe` y lo ejecuta con `/SILENT`. Solo funciona en el .exe instalado; desde el código abre la página.
- Para publicar: subir la versión, añadir la sección en `NOVEDADES.md` (su texto sale como «Novedades»),
  ejecutar `build.py`, hacer commit y push, y después `publicar.py`.
- Los commits se firman como «Agencia Daga» con el correo noreply de GitHub (configuración local del repo).
  No publiques datos personales del usuario (nombre, DNI, correo).

## Entorno
- Venv con Python 3.11 (`py -3.11`); el Python del sistema es el 3.14.
- El OCR y el corrector usan el idioma es-ES instalado en Windows.
- Sello de tiempo por defecto: `http://timestamp.digicert.com`. Para la LTV se consulta el OCSP de la FNMT.
