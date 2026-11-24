"""Firma digital PAdES con certificados de Windows y verificación de firmas (pyHanko)."""
import datetime as dt
import hashlib
import io
import os

from asn1crypto import algos
from asn1crypto.algos import DSASignature
from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
from pyhanko.pdf_utils.reader import PdfFileReader
from pyhanko.sign import fields, signers, timestamps
from pyhanko.sign.validation import validate_pdf_signature
from pyhanko_certvalidator import ValidationContext
from pyhanko_certvalidator.registry import SimpleCertificateStore

from . import wincert

# pyHanko registra la extensión «qc_statements» (certificados cualificados como el de la FNMT) en asn1crypto.
# Si asn1crypto ya había construido su índice inverso antes, este no la incluye y falla al validar:
# se obliga a reconstruirlo.
from asn1crypto import x509 as _x509  # noqa: E402
from pyhanko.sign.ades import qualified_asn1  # noqa: E402,F401

_x509.ExtensionId._reverse_map = {v: k for k, v in _x509.ExtensionId._map.items()}

ARIAL = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "arial.ttf")
TSA_SERVERS = [
    ("DigiCert (gratuito)", "http://timestamp.digicert.com"),
    ("Sectigo (gratuito)", "http://timestamp.sectigo.com"),
    ("FreeTSA", "https://freetsa.org/tsr"),
]


class WindowsSigner(signers.Signer):
    """Firmante de pyHanko que delega la operación con la clave en Windows."""

    def __init__(self, wc: wincert.WinCert):
        from asn1crypto import x509
        self.wc = wc
        # copias recién leídas: los objetos de asn1crypto que ya se han inspeccionado pueden no volver a serializarse bien
        self.chain = [x509.Certificate.load(c.dump(force=True)) for c in wc.chain()]
        algo = "sha256_rsa" if wc.key_algo == "rsa" else "sha256_ecdsa"
        super().__init__(
            signing_cert=x509.Certificate.load(wc.der),
            cert_registry=SimpleCertificateStore.from_certs(self.chain),
            signature_mechanism=algos.SignedDigestAlgorithm({"algorithm": algo}),
            embed_roots=True,
        )

    async def async_sign_raw(self, data, digest_algorithm, dry_run=False):
        if dry_run:  # solo para calcular el tamaño
            n = (self.wc.key_bits + 7) // 8
            return bytes(n) if self.wc.key_algo == "rsa" else bytes(2 * n + 9)
        digest = hashlib.new(digest_algorithm, data).digest()
        sig = self.wc.sign_hash(digest, digest_algorithm)
        if self.wc.key_algo != "rsa":
            sig = DSASignature.from_p1363(sig).dump()
        return sig


def _stamp_style(lines, image_path, width, height):
    """Dibuja la apariencia de la firma con PyMuPDF (Arial, tildes) y la usa como sello fijo."""
    import tempfile

    import pymupdf as fitz
    from pyhanko.stamp import StaticStampStyle

    d = fitz.open()
    p = d.new_page(width=width, height=height)
    r = p.rect
    p.draw_rect(r + (0.5, 0.5, -0.5, -0.5), color=(0.25, 0.35, 0.6), width=1)
    text_rect = r + (5, 4, -4, -3)
    if image_path and os.path.exists(image_path):
        if width > height * 2.2:  # imagen a la izquierda, texto a la derecha
            img_rect = fitz.Rect(r.x0 + 4, r.y0 + 4, r.x0 + width * 0.38, r.y1 - 4)
            text_rect = fitz.Rect(img_rect.x1 + 4, r.y0 + 4, r.x1 - 4, r.y1 - 3)
        else:  # imagen arriba, texto abajo
            img_rect = fitz.Rect(r.x0 + 4, r.y0 + 3, r.x1 - 4, r.y0 + height * 0.45)
            text_rect = fitz.Rect(r.x0 + 5, img_rect.y1 + 2, r.x1 - 4, r.y1 - 3)
        p.insert_image(img_rect, filename=image_path, keep_proportion=True)
    font = dict(fontname="Earial", fontfile=ARIAL) if os.path.exists(ARIAL) else dict(fontname="helv")
    text = "\n".join(lines)
    size = 9.0
    while True:  # el tamaño de letra más grande que quepa (lo que no se confirma no se escribe)
        shape = p.new_shape()
        if shape.insert_textbox(text_rect, text, fontsize=size, color=(0.1, 0.15, 0.35), **font) >= 0 or size <= 4:
            shape.commit()
            break
        size -= 0.5
    d.subset_fonts()
    fd, path = tempfile.mkstemp(suffix=".pdf")
    os.close(fd)
    d.save(path)
    d.close()
    return StaticStampStyle.from_pdf_file(path, border_width=0), path


def sign_pdf(pdf_bytes, out_path, wc, *, page=0, box=None, reason="", location="", show_id=False,
             image_path=None, tsa_url=None, ltv=False, password=None):
    """Firma y guarda en out_path. box = (x1, y1, x2, y2) en coordenadas PDF (origen abajo) o None (invisible).

    Devuelve una lista de avisos (p. ej. si no se pudo añadir LTV)."""
    warnings = []
    name = wc.cn if show_id else wc.nice_name
    field_name = "Firma_" + dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    signer = WindowsSigner(wc)

    def attempt(with_ltv):
        w = IncrementalPdfFileWriter(io.BytesIO(pdf_bytes))
        if password and w.prev.encrypted:
            w.encrypt(password)
        vc = None
        if with_ltv:
            roots = wincert.root_certificates() + [c for c in signer.chain if c.self_signed != "no"]
            vc = ValidationContext(trust_roots=roots, other_certs=signer.chain, allow_fetching=True,
                                   revocation_mode="soft-fail")
        meta = signers.PdfSignatureMetadata(
            field_name=field_name, md_algorithm="sha256", subfilter=fields.SigSeedSubFilter.PADES,
            reason=reason or None, location=location or None, name=name,
            embed_validation_info=with_ltv, validation_context=vc,
        )
        style, spec, tmp_stamp = None, None, None
        if box:
            lines = ["Firmado digitalmente por:", name, "Fecha: " + dt.datetime.now().strftime("%d/%m/%Y %H:%M:%S")]
            if reason:
                lines.append("Motivo: " + reason)
            if location:
                lines.append("Lugar: " + location)
            ibox = tuple(int(round(v)) for v in box)
            style, tmp_stamp = _stamp_style(lines, image_path, ibox[2] - ibox[0], ibox[3] - ibox[1])
            spec = fields.SigFieldSpec(field_name, on_page=page, box=ibox)
        ts = timestamps.HTTPTimeStamper(tsa_url, timeout=15) if tsa_url else None
        pdf_signer = signers.PdfSigner(meta, signer=signer, timestamper=ts, stamp_style=style, new_field_spec=spec)
        buf = io.BytesIO()
        try:
            pdf_signer.sign_pdf(w, output=buf)
        finally:
            if tmp_stamp:
                try:
                    os.remove(tmp_stamp)
                except OSError:
                    pass
        return buf.getvalue()

    try:
        data = attempt(ltv)
    except Exception as e:
        if not ltv or "cancel" in str(e).lower():
            raise
        warnings.append(f"No se pudieron añadir los datos de validación a largo plazo ({e}). Se firmó sin ellos.")
        data = attempt(False)
    tmp = out_path + ".tmp~"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, out_path)
    return warnings


# ---------------------------------------------------------------- verificación
COVERAGE = {
    "ENTIRE_FILE": "Cubre todo el documento.",
    "ENTIRE_REVISION": "Hay cambios añadidos después de la firma.",
    "CONTIGUOUS_BLOCK_FROM_START": "Cubre solo parte del archivo.",
    "UNCLEAR": "No está claro qué parte cubre.",
}
MODIFICATION = {
    "NONE": "",
    "LTA_UPDATES": "Después solo se añadieron datos de validación.",
    "FORM_FILLING": "Después se rellenaron campos de formulario o se añadieron otras firmas.",
    "ANNOTATIONS": "Después se añadieron anotaciones o comentarios.",
    "OTHER": "¡Después se modificó el contenido!",
}


def verify(pdf_bytes, password=None):
    """Devuelve una lista de dicts, uno por firma."""
    r = PdfFileReader(io.BytesIO(pdf_bytes))
    if r.encrypted and password:
        r.decrypt(password)
    roots = wincert.root_certificates()
    out = []
    for sig in r.embedded_signatures:
        vc = ValidationContext(trust_roots=roots, allow_fetching=True, revocation_mode="soft-fail")
        info = {"field": sig.field_name}
        try:
            st = validate_pdf_signature(sig, vc, ts_validation_context=ValidationContext(
                trust_roots=roots, allow_fetching=True, revocation_mode="soft-fail"))
            cov = st.coverage.name if st.coverage else ""
            mod = st.modification_level.name if st.modification_level else ""
            if cov == "ENTIRE_REVISION" and mod in ("NONE", "LTA_UPDATES", ""):
                cov_text = "Cubre todo lo firmado; después solo se añadieron datos de validación."
            else:
                cov_text = COVERAGE.get(cov, cov)
            cert = st.signing_cert
            subj = cert.subject.native
            info.update(
                signer=subj.get("common_name") or cert.subject.human_friendly,
                issuer=cert.issuer.native.get("common_name", ""),
                intact=bool(st.intact), valid=bool(st.valid), trusted=bool(st.trusted),
                revoked=bool(getattr(st, "revoked", False)),
                time=st.signer_reported_dt,
                tsa_time=st.timestamp_validity.timestamp if st.timestamp_validity else None,
                coverage=cov_text,
                modification=MODIFICATION.get(mod, ""),
                ok=bool(st.bottom_line),
                details=st.pretty_print_details(),
            )
        except Exception as e:
            info.update(ok=False, error=str(e))
        out.append(info)
    return out
