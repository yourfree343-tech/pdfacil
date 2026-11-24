"""Registro de PDFácil para los archivos .pdf (solo en el usuario actual, sin permisos de administrador).

Windows 10/11 no deja que un programa se ponga como predeterminado él solo: se registra para que
aparezca en «Abrir con» y en Configuración > Aplicaciones predeterminadas, y el usuario lo elige allí.
"""
import ctypes
import os
import sys
import winreg

PROGID = "EditorPDF.Document"
APP_REG_NAME = "PDFácil"
OLD_REG_NAMES = ("Editor PDF",)  # nombres anteriores del programa
CAPS = r"Software\EditorPDF\Capabilities"


def open_command():
    if getattr(sys, "frozen", False):
        exe = sys.executable
        return exe, f'"{exe}" "%1"'
    pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    main = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "main.py")
    return pyw, f'"{pyw}" "{main}" "%1"'


def _set(path, name, value):
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_WRITE) as k:
        winreg.SetValueEx(k, name, 0, winreg.REG_SZ, value)


def _notify():
    try:
        ctypes.windll.shell32.SHChangeNotify(0x08000000, 0, None, None)  # SHCNE_ASSOCCHANGED
    except Exception:
        pass


def register():
    exe, cmd = open_command()
    base = rf"Software\Classes\{PROGID}"
    _set(base, "", "Documento PDF")
    _set(base, "FriendlyTypeName", "Documento PDF")
    _set(base + r"\DefaultIcon", "", f'"{exe}",0')
    _set(base + r"\shell\open", "FriendlyAppName", APP_REG_NAME)
    _set(base + r"\shell\open\command", "", cmd)
    _set(r"Software\Classes\.pdf\OpenWithProgids", PROGID, "")
    _set(CAPS, "ApplicationName", APP_REG_NAME)
    _set(CAPS, "ApplicationDescription", "Ver, editar, firmar y organizar documentos PDF")
    _set(CAPS + r"\FileAssociations", ".pdf", PROGID)
    _set(r"Software\RegisteredApplications", APP_REG_NAME, CAPS)
    _remove_old_names()
    _notify()


def _remove_old_names():
    for name in OLD_REG_NAMES:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\RegisteredApplications", 0,
                                winreg.KEY_SET_VALUE) as k:
                winreg.DeleteValue(k, name)
        except OSError:
            pass


def _delete_tree(root, path):
    try:
        with winreg.OpenKey(root, path, 0, winreg.KEY_ALL_ACCESS) as k:
            while True:
                try:
                    sub = winreg.EnumKey(k, 0)
                except OSError:
                    break
                _delete_tree(root, path + "\\" + sub)
        winreg.DeleteKey(root, path)
    except FileNotFoundError:
        pass


def unregister():
    hk = winreg.HKEY_CURRENT_USER
    _delete_tree(hk, rf"Software\Classes\{PROGID}")
    _delete_tree(hk, CAPS)  # solo esta subclave: en Software\EditorPDF\EditorPDF están los ajustes del programa
    for path, name in ((r"Software\Classes\.pdf\OpenWithProgids", PROGID),
                       (r"Software\RegisteredApplications", APP_REG_NAME)):
        try:
            with winreg.OpenKey(hk, path, 0, winreg.KEY_SET_VALUE) as k:
                winreg.DeleteValue(k, name)
        except FileNotFoundError:
            pass
    _notify()


def status():
    """'none' (no registrado), 'ok' (registrado con este programa) u 'old' (registrado con otra ruta)."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{PROGID}\shell\open\command") as k:
            cmd = winreg.QueryValueEx(k, "")[0]
    except FileNotFoundError:
        return "none"
    return "ok" if cmd == open_command()[1] else "old"


def is_default():
    """True si Windows tiene PDFácil como predeterminado para .pdf."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\.pdf\UserChoice") as k:
            return winreg.QueryValueEx(k, "ProgId")[0] == PROGID
    except FileNotFoundError:
        return False


def open_default_apps_settings():
    from urllib.parse import quote
    os.startfile("ms-settings:defaultapps?registeredAppUser=" + quote(APP_REG_NAME))
