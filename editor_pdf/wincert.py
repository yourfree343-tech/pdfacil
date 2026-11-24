"""Acceso a los certificados del almacén de Windows y firma con su clave privada (CNG).

La clave privada nunca sale de Windows: se le pide a Windows que firme un resumen (hash).
Funciona con certificados software (FNMT) y con tarjetas (DNIe) que tengan proveedor CNG.
"""
import ctypes
import datetime as dt
from ctypes import wintypes as W

from asn1crypto import x509

crypt32 = ctypes.WinDLL("crypt32")
ncrypt = ctypes.WinDLL("ncrypt")


class CERT_CONTEXT(ctypes.Structure):
    _fields_ = [("dwCertEncodingType", W.DWORD), ("pbCertEncoded", ctypes.POINTER(ctypes.c_ubyte)),
                ("cbCertEncoded", W.DWORD), ("pCertInfo", ctypes.c_void_p), ("hCertStore", ctypes.c_void_p)]


PCCERT_CONTEXT = ctypes.POINTER(CERT_CONTEXT)


class CERT_TRUST_STATUS(ctypes.Structure):
    _fields_ = [("dwErrorStatus", W.DWORD), ("dwInfoStatus", W.DWORD)]


class CERT_CHAIN_ELEMENT(ctypes.Structure):
    _fields_ = [("cbSize", W.DWORD), ("pCertContext", PCCERT_CONTEXT), ("TrustStatus", CERT_TRUST_STATUS)]


class CERT_SIMPLE_CHAIN(ctypes.Structure):
    _fields_ = [("cbSize", W.DWORD), ("TrustStatus", CERT_TRUST_STATUS), ("cElement", W.DWORD),
                ("rgpElement", ctypes.POINTER(ctypes.POINTER(CERT_CHAIN_ELEMENT)))]


class CERT_CHAIN_CONTEXT(ctypes.Structure):
    _fields_ = [("cbSize", W.DWORD), ("TrustStatus", CERT_TRUST_STATUS), ("cChain", W.DWORD),
                ("rgpChain", ctypes.POINTER(ctypes.POINTER(CERT_SIMPLE_CHAIN)))]


class CERT_ENHKEY_USAGE(ctypes.Structure):
    _fields_ = [("cUsageIdentifier", W.DWORD), ("rgpszUsageIdentifier", ctypes.c_void_p)]


class CERT_USAGE_MATCH(ctypes.Structure):
    _fields_ = [("dwType", W.DWORD), ("Usage", CERT_ENHKEY_USAGE)]


class CERT_CHAIN_PARA(ctypes.Structure):
    _fields_ = [("cbSize", W.DWORD), ("RequestedUsage", CERT_USAGE_MATCH)]


class BCRYPT_PKCS1_PADDING_INFO(ctypes.Structure):
    _fields_ = [("pszAlgId", W.LPCWSTR)]


crypt32.CertOpenSystemStoreW.argtypes = [ctypes.c_void_p, W.LPCWSTR]
crypt32.CertOpenSystemStoreW.restype = ctypes.c_void_p
crypt32.CertEnumCertificatesInStore.argtypes = [ctypes.c_void_p, PCCERT_CONTEXT]
crypt32.CertEnumCertificatesInStore.restype = PCCERT_CONTEXT
crypt32.CertDuplicateCertificateContext.argtypes = [PCCERT_CONTEXT]
crypt32.CertDuplicateCertificateContext.restype = PCCERT_CONTEXT
crypt32.CertFreeCertificateContext.argtypes = [PCCERT_CONTEXT]
crypt32.CertCloseStore.argtypes = [ctypes.c_void_p, W.DWORD]
crypt32.CertGetCertificateChain.argtypes = [ctypes.c_void_p, PCCERT_CONTEXT, ctypes.c_void_p, ctypes.c_void_p,
                                            ctypes.POINTER(CERT_CHAIN_PARA), W.DWORD, ctypes.c_void_p,
                                            ctypes.POINTER(ctypes.POINTER(CERT_CHAIN_CONTEXT))]
crypt32.CertFreeCertificateChain.argtypes = [ctypes.POINTER(CERT_CHAIN_CONTEXT)]
crypt32.CryptAcquireCertificatePrivateKey.argtypes = [PCCERT_CONTEXT, W.DWORD, ctypes.c_void_p,
                                                      ctypes.POINTER(ctypes.c_size_t), ctypes.POINTER(W.DWORD),
                                                      ctypes.POINTER(W.BOOL)]
ncrypt.NCryptSignHash.argtypes = [ctypes.c_size_t, ctypes.c_void_p, ctypes.c_char_p, W.DWORD, ctypes.c_char_p,
                                  W.DWORD, ctypes.POINTER(W.DWORD), W.DWORD]
ncrypt.NCryptSignHash.restype = ctypes.c_long
ncrypt.NCryptFreeObject.argtypes = [ctypes.c_size_t]

CRYPT_ACQUIRE_CACHE_FLAG = 0x1
CRYPT_ACQUIRE_COMPARE_KEY_FLAG = 0x4
CRYPT_ACQUIRE_ONLY_NCRYPT_KEY_FLAG = 0x40000
CERT_NCRYPT_KEY_SPEC = 0xFFFFFFFF
BCRYPT_PAD_PKCS1 = 0x2
HASH_NAMES = {"sha256": "SHA256", "sha384": "SHA384", "sha512": "SHA512", "sha1": "SHA1"}


def _der(ctx):
    return bytes(ctypes.string_at(ctx.contents.pbCertEncoded, ctx.contents.cbCertEncoded))


def _enum(store_name):
    h = crypt32.CertOpenSystemStoreW(None, store_name)
    if not h:
        return []
    out = []
    ctx = crypt32.CertEnumCertificatesInStore(h, None)
    while ctx:
        out.append(_der(ctx))
        ctx = crypt32.CertEnumCertificatesInStore(h, ctx)
    crypt32.CertCloseStore(h, 0)
    return out


def root_certificates():
    """Certificados raíz de confianza de Windows (para validar firmas)."""
    certs = []
    for der in _enum("ROOT"):
        try:
            certs.append(x509.Certificate.load(der))
        except Exception:
            pass
    return certs


def _name_parts(cert):
    s = cert.subject.native
    given, surname = s.get("given_name"), s.get("surname")
    cn = s.get("common_name", "")
    if given and surname:
        nice = f"{given} {surname}"
    else:
        nice = cn.split(" - ")[0]
    return cn, nice.title()


class WinCert:
    def __init__(self, der):
        self.der = der
        self.cert = x509.Certificate.load(der)
        self.cn, self.nice_name = _name_parts(self.cert)
        self.issuer = self.cert.issuer.native.get("common_name", "")
        self.not_after = self.cert["tbs_certificate"]["validity"]["not_after"].native
        self.not_before = self.cert["tbs_certificate"]["validity"]["not_before"].native
        self.thumb = self.cert.sha1.hex().upper()

    @property
    def valid_now(self):
        now = dt.datetime.now(dt.timezone.utc)
        return self.not_before <= now <= self.not_after

    @property
    def can_sign(self):
        ku = self.cert.key_usage_value
        if ku is None:
            return True
        return bool({"digital_signature", "non_repudiation"} & set(ku.native))

    @property
    def personal(self):
        """Descarta certificados internos de programas (autofirmados o con nombre tipo GUID)."""
        import re
        guid = r"^(trust_)?[0-9a-fA-F]{8}-[0-9a-fA-F-]{27}$"
        return (self.cert.self_signed == "no" and not re.match(guid, self.issuer or "")
                and not re.match(guid, self.cn or "") and self.cn.lower() != "localhost")

    @property
    def key_algo(self):
        return self.cert.public_key.algorithm  # 'rsa' o 'ec'

    @property
    def key_bits(self):
        return self.cert.public_key.bit_size

    def __str__(self):
        return f"{self.cn} — {self.issuer} (caduca {self.not_after:%d/%m/%Y})"

    # ---------- acceso al contexto de Windows
    def _find_ctx(self):
        h = crypt32.CertOpenSystemStoreW(None, "MY")
        ctx = crypt32.CertEnumCertificatesInStore(h, None)
        found = None
        while ctx:
            if _der(ctx) == self.der:
                found = crypt32.CertDuplicateCertificateContext(ctx)
                crypt32.CertFreeCertificateContext(ctx)
                break
            ctx = crypt32.CertEnumCertificatesInStore(h, ctx)
        return h, found

    def chain(self):
        """Certificados intermedios y raíz (sin el propio), según Windows."""
        h, ctx = self._find_ctx()
        out = []
        try:
            if not ctx:
                return out
            para = CERT_CHAIN_PARA()
            para.cbSize = ctypes.sizeof(CERT_CHAIN_PARA)
            pchain = ctypes.POINTER(CERT_CHAIN_CONTEXT)()
            if crypt32.CertGetCertificateChain(None, ctx, None, None, ctypes.byref(para), 0, None, ctypes.byref(pchain)):
                chain = pchain.contents
                if chain.cChain:
                    simple = chain.rgpChain[0].contents
                    for k in range(1, simple.cElement):
                        out.append(x509.Certificate.load(_der(simple.rgpElement[k].contents.pCertContext)))
                crypt32.CertFreeCertificateChain(pchain)
            crypt32.CertFreeCertificateContext(ctx)
        finally:
            crypt32.CertCloseStore(h, 0)
        return out

    def sign_hash(self, digest, hash_name="sha256"):
        """Firma un resumen ya calculado. Devuelve la firma (RSA PKCS#1 v1.5 o ECDSA en formato P1363)."""
        h, ctx = self._find_ctx()
        if not ctx:
            crypt32.CertCloseStore(h, 0)
            raise RuntimeError("No encuentro el certificado en el almacén de Windows.")
        key = ctypes.c_size_t()
        spec = W.DWORD()
        free = W.BOOL()
        try:
            ok = crypt32.CryptAcquireCertificatePrivateKey(
                ctx, CRYPT_ACQUIRE_ONLY_NCRYPT_KEY_FLAG | CRYPT_ACQUIRE_COMPARE_KEY_FLAG, None,
                ctypes.byref(key), ctypes.byref(spec), ctypes.byref(free))
            if not ok:
                raise RuntimeError(f"Windows no deja usar la clave privada (error {ctypes.GetLastError():#x}).")
            if self.key_algo == "rsa":
                pad = BCRYPT_PKCS1_PADDING_INFO(HASH_NAMES[hash_name])
                ppad, flags = ctypes.byref(pad), BCRYPT_PAD_PKCS1
            else:
                ppad, flags = None, 0
            size = W.DWORD()
            st = ncrypt.NCryptSignHash(key.value, ppad, digest, len(digest), None, 0, ctypes.byref(size), flags)
            if st != 0:
                raise RuntimeError(f"Error al preparar la firma ({st & 0xFFFFFFFF:#x}).")
            buf = ctypes.create_string_buffer(size.value)
            st = ncrypt.NCryptSignHash(key.value, ppad, digest, len(digest), buf, size, ctypes.byref(size), flags)
            if st != 0:
                if st & 0xFFFFFFFF == 0x800704C7:
                    raise RuntimeError("Firma cancelada.")
                raise RuntimeError(f"Windows no pudo firmar ({st & 0xFFFFFFFF:#x}).")
            return buf.raw[:size.value]
        finally:
            if free and key.value:
                ncrypt.NCryptFreeObject(key.value)
            crypt32.CertFreeCertificateContext(ctx)
            crypt32.CertCloseStore(h, 0)


def signing_certificates():
    """Certificados personales con clave privada que sirven para firmar."""
    out = []
    for der in _enum("MY"):
        try:
            c = WinCert(der)
        except Exception:
            continue
        if not c.can_sign:
            continue
        # solo los que tienen clave privada: lo comprobamos sin pedir nada al usuario
        h, ctx = c._find_ctx()
        try:
            key, spec, free = ctypes.c_size_t(), W.DWORD(), W.BOOL()
            ok = crypt32.CryptAcquireCertificatePrivateKey(
                ctx, CRYPT_ACQUIRE_ONLY_NCRYPT_KEY_FLAG | 0x40, None,  # 0x40 = SILENT
                ctypes.byref(key), ctypes.byref(spec), ctypes.byref(free)) if ctx else False
            if ok and free and key.value:
                ncrypt.NCryptFreeObject(key.value)
        finally:
            if ctx:
                crypt32.CertFreeCertificateContext(ctx)
            crypt32.CertCloseStore(h, 0)
        if ok or ctypes.GetLastError() == 0x80090022:  # NTE_SILENT_CONTEXT: hay clave pero pide PIN
            out.append(c)
    # primero los válidos y de entidades reales (los autofirmados con nombre GUID al final)
    out.sort(key=lambda c: (not c.valid_now, c.cn == c.issuer, c.cn))
    return out
