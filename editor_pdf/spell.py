"""Corrector ortográfico de Windows (ISpellChecker, Windows 8 o posterior) mediante COM.

Usa los diccionarios del sistema y el diccionario personal de Windows: las palabras añadidas
aquí también sirven en otros programas que usen el corrector de Windows.
"""
import ctypes
from ctypes import HRESULT, POINTER, byref, c_ulong, c_void_p, c_wchar_p
from ctypes.wintypes import BOOL, DWORD

import comtypes
import comtypes.client
from comtypes import COMMETHOD, GUID, IUnknown

ole32 = ctypes.windll.ole32
ole32.CoTaskMemFree.argtypes = [c_void_p]


def _take_string(p):
    if not p:
        return ""
    s = ctypes.wstring_at(p)
    ole32.CoTaskMemFree(p)
    return s


class IEnumString(IUnknown):
    _iid_ = GUID("{00000101-0000-0000-C000-000000000046}")
    _methods_ = [
        COMMETHOD([], HRESULT, "Next", (["in"], c_ulong, "celt"), (["in"], POINTER(c_void_p), "rgelt"),
                  (["in"], POINTER(c_ulong), "pceltFetched")),
        COMMETHOD([], HRESULT, "Skip", (["in"], c_ulong, "celt")),
        COMMETHOD([], HRESULT, "Reset"),
        COMMETHOD([], HRESULT, "Clone", (["out"], POINTER(c_void_p), "ppenum")),
    ]


def _read_enum(enum, limit=50):
    out = []
    while len(out) < limit:
        p = c_void_p()
        n = c_ulong()
        hr = enum.Next(1, byref(p), byref(n))
        if hr != 0 or n.value == 0:
            break
        out.append(_take_string(p.value))
    return out


class ISpellingError(IUnknown):
    _iid_ = GUID("{B7C82D61-FBE8-4B47-9B27-6C0D2E0DE0A3}")
    _methods_ = [
        COMMETHOD([], HRESULT, "get_StartIndex", (["out"], POINTER(c_ulong), "value")),
        COMMETHOD([], HRESULT, "get_Length", (["out"], POINTER(c_ulong), "value")),
        COMMETHOD([], HRESULT, "get_CorrectiveAction", (["out"], POINTER(DWORD), "value")),
        COMMETHOD([], HRESULT, "get_Replacement", (["out"], POINTER(c_void_p), "value")),
    ]


class IEnumSpellingError(IUnknown):
    _iid_ = GUID("{803E3BD4-2828-4410-8290-418D1D73C762}")
    _methods_ = [
        COMMETHOD([], HRESULT, "Next", (["out"], POINTER(POINTER(ISpellingError)), "value")),
    ]


class ISpellChecker(IUnknown):
    _iid_ = GUID("{B6FD0B71-E2BC-4653-8D05-F197E412770B}")
    _methods_ = [
        COMMETHOD([], HRESULT, "get_LanguageTag", (["out"], POINTER(c_void_p), "value")),
        COMMETHOD([], HRESULT, "Check", (["in"], c_wchar_p, "text"), (["out"], POINTER(POINTER(IEnumSpellingError)), "value")),
        COMMETHOD([], HRESULT, "Suggest", (["in"], c_wchar_p, "word"), (["out"], POINTER(POINTER(IEnumString)), "value")),
        COMMETHOD([], HRESULT, "Add", (["in"], c_wchar_p, "word")),
        COMMETHOD([], HRESULT, "Ignore", (["in"], c_wchar_p, "word")),
        COMMETHOD([], HRESULT, "AutoCorrect", (["in"], c_wchar_p, "frm"), (["in"], c_wchar_p, "to")),
        COMMETHOD([], HRESULT, "GetOptionValue", (["in"], c_wchar_p, "optionId"), (["out"], POINTER(ctypes.c_byte), "value")),
        COMMETHOD([], HRESULT, "get_OptionIds", (["out"], POINTER(POINTER(IEnumString)), "value")),
        COMMETHOD([], HRESULT, "get_Id", (["out"], POINTER(c_void_p), "value")),
        COMMETHOD([], HRESULT, "get_LocalizedName", (["out"], POINTER(c_void_p), "value")),
        COMMETHOD([], HRESULT, "add_SpellCheckerChanged", (["in"], c_void_p, "handler"), (["out"], POINTER(DWORD), "cookie")),
        COMMETHOD([], HRESULT, "remove_SpellCheckerChanged", (["in"], DWORD, "cookie")),
        COMMETHOD([], HRESULT, "GetOptionDescription", (["in"], c_wchar_p, "optionId"), (["out"], POINTER(c_void_p), "value")),
        COMMETHOD([], HRESULT, "ComprehensiveCheck", (["in"], c_wchar_p, "text"), (["out"], POINTER(POINTER(IEnumSpellingError)), "value")),
    ]


class ISpellCheckerFactory(IUnknown):
    _iid_ = GUID("{8E018A9D-2415-4677-BF08-794EA61F94BB}")
    _methods_ = [
        COMMETHOD([], HRESULT, "get_SupportedLanguages", (["out"], POINTER(POINTER(IEnumString)), "value")),
        COMMETHOD([], HRESULT, "IsSupported", (["in"], c_wchar_p, "languageTag"), (["out"], POINTER(BOOL), "value")),
        COMMETHOD([], HRESULT, "CreateSpellChecker", (["in"], c_wchar_p, "languageTag"), (["out"], POINTER(POINTER(ISpellChecker)), "value")),
    ]


CLSID_SpellCheckerFactory = GUID("{7AB36653-1796-484B-BDFA-E74F1DB7C1DC}")

# acciones que propone Windows para cada error
ACTION_SUGGEST, ACTION_REPLACE, ACTION_DELETE = 1, 2, 3


class SpellError:
    __slots__ = ("start", "length", "action", "replacement")

    def __init__(self, start, length, action, replacement):
        self.start, self.length, self.action, self.replacement = start, length, action, replacement

    def __repr__(self):
        return f"SpellError({self.start}, {self.length}, {self.action}, {self.replacement!r})"


class Speller:
    def __init__(self, preferred=("es-ES", "es-MX", "es")):
        comtypes.CoInitialize()
        self.factory = comtypes.client.CreateObject(CLSID_SpellCheckerFactory, interface=ISpellCheckerFactory)
        self.languages = _read_enum(self.factory.get_SupportedLanguages(), 200)
        tag = next((t for t in preferred if t in self.languages), None)
        if tag is None:
            tag = next((t for t in self.languages if t.lower().startswith("es")), None)
        if tag is None and self.languages:
            tag = self.languages[0]
        if tag is None:
            raise RuntimeError("Windows no tiene ningún diccionario instalado.")
        self.tag = tag
        self.checker = self.factory.CreateSpellChecker(tag)
        self.session_ignored = set()

    def check(self, text):
        """Lista de SpellError en el texto (posiciones en caracteres de Python)."""
        if not text.strip():
            return []
        out = []
        enum = self.checker.Check(text)
        while True:
            try:
                err = enum.Next()
            except comtypes.COMError:
                break
            if not err:
                break
            start, length = err.get_StartIndex(), err.get_Length()
            word = text[start:start + length]
            if word in self.session_ignored or any(ch.isdigit() for ch in word):
                continue
            out.append(SpellError(start, length, err.get_CorrectiveAction(), _take_string(err.get_Replacement())))
        return out

    def suggest(self, word, limit=8):
        try:
            return _read_enum(self.checker.Suggest(word), limit)
        except comtypes.COMError:
            return []

    def add(self, word):
        """Añade la palabra al diccionario personal de Windows."""
        self.checker.Add(word)

    def ignore(self, word):
        """Ignora la palabra mientras el programa esté abierto."""
        self.session_ignored.add(word)
        try:
            self.checker.Ignore(word)
        except comtypes.COMError:
            pass


_instance = None
_error = None


def get():
    """Corrector compartido, o None si no está disponible (ver error())."""
    global _instance, _error
    if _instance is None and _error is None:
        try:
            _instance = Speller()
        except Exception as e:
            _error = str(e)
    return _instance


def error():
    return _error
