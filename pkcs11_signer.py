from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Optional

import PyKCS11
from cryptography import x509
from cryptography.hazmat.primitives.asymmetric import rsa


class TokenError(RuntimeError):
    pass


@dataclass
class TokenIdentity:
    slot: int
    token_label: str
    certificate_label: str
    certificate_der: bytes
    certificate_base64: str
    private_key: object
    certificate: object


MECHANISMS = {
    "SHA1_RSA_PKCS": PyKCS11.Mechanism(PyKCS11.CKM_SHA1_RSA_PKCS, None),
    "SHA256_RSA_PKCS": PyKCS11.Mechanism(PyKCS11.CKM_SHA256_RSA_PKCS, None),
    "SHA384_RSA_PKCS": PyKCS11.Mechanism(PyKCS11.CKM_SHA384_RSA_PKCS, None),
    "SHA512_RSA_PKCS": PyKCS11.Mechanism(PyKCS11.CKM_SHA512_RSA_PKCS, None),
}


class PKCS11Signer:
    def __init__(self, library_path: str, slot_index: int = 0,
                 token_label_contains: str = "",
                 certificate_label_contains: str = "",
                 private_key_label_contains: str = "") -> None:
        self.library_path = library_path
        self.slot_index = slot_index
        self.token_label_contains = token_label_contains.lower().strip()
        self.certificate_label_contains = certificate_label_contains.lower().strip()
        self.private_key_label_contains = private_key_label_contains.lower().strip()
        self.lib = PyKCS11.PyKCS11Lib()
        self.session: Optional[PyKCS11.Session] = None
        self.identity: Optional[TokenIdentity] = None

    @staticmethod
    def _attr(obj, attr, default=None):
        try:
            return obj.to_dict().get(attr, default)
        except Exception:
            return default

    def open(self, pin: str) -> TokenIdentity:
        try:
            self.lib.load(self.library_path)
        except Exception as exc:
            raise TokenError(f"Could not load PKCS#11 library: {self.library_path}. {exc}") from exc

        slots = self.lib.getSlotList(tokenPresent=True)
        if not slots:
            raise TokenError("No DSC/USB token detected by the PKCS#11 library.")

        eligible = []
        for slot in slots:
            try:
                info = self.lib.getTokenInfo(slot)
                label = str(info.label).strip()
            except Exception:
                continue
            if not self.token_label_contains or self.token_label_contains in label.lower():
                eligible.append((slot, label))

        if not eligible:
            raise TokenError(f"No token matched token_label_contains={self.token_label_contains!r}.")
        if self.slot_index >= len(eligible):
            raise TokenError(f"slot_index={self.slot_index} is out of range; matching tokens={len(eligible)}.")

        slot, token_label = eligible[self.slot_index]
        session = self.lib.openSession(slot)
        try:
            session.login(pin)
        except PyKCS11.PyKCS11Error as exc:
            session.closeSession()
            raise TokenError(f"Token login failed. Check PIN. {exc}") from exc

        certs = session.findObjects([
            (PyKCS11.CKA_CLASS, PyKCS11.CKO_CERTIFICATE),
            (PyKCS11.CKA_CERTIFICATE_TYPE, PyKCS11.CKC_X_509),
        ])
        keys = session.findObjects([
            (PyKCS11.CKA_CLASS, PyKCS11.CKO_PRIVATE_KEY),
            (PyKCS11.CKA_KEY_TYPE, PyKCS11.CKK_RSA),
        ])
        if not certs:
            session.logout(); session.closeSession()
            raise TokenError("No X.509 certificate found on the token.")
        if not keys:
            session.logout(); session.closeSession()
            raise TokenError("No RSA private key found on the token.")

        def attrs(obj, names):
            try:
                vals = session.getAttributeValue(obj, names)
                return dict(zip(names, vals))
            except Exception:
                return {}

        cert_meta = []
        for c in certs:
            a = attrs(c, [PyKCS11.CKA_LABEL, PyKCS11.CKA_ID, PyKCS11.CKA_VALUE])
            label = str(a.get(PyKCS11.CKA_LABEL) or "").strip()
            if self.certificate_label_contains and self.certificate_label_contains not in label.lower():
                continue
            cert_meta.append((c, label, bytes(a.get(PyKCS11.CKA_ID) or []), bytes(a.get(PyKCS11.CKA_VALUE) or [])))

        key_meta = []
        for k in keys:
            a = attrs(k, [PyKCS11.CKA_LABEL, PyKCS11.CKA_ID])
            label = str(a.get(PyKCS11.CKA_LABEL) or "").strip()
            if self.private_key_label_contains and self.private_key_label_contains not in label.lower():
                continue
            key_meta.append((k, label, bytes(a.get(PyKCS11.CKA_ID) or [])))

        if not cert_meta:
            session.logout(); session.closeSession()
            raise TokenError("No certificate matched certificate_label_contains.")
        if not key_meta:
            session.logout(); session.closeSession()
            raise TokenError("No private key matched private_key_label_contains.")

        selected = None
        for c, clabel, cid, cder in cert_meta:
            for k, klabel, kid in key_meta:
                if cid and kid and cid == kid:
                    selected = (c, clabel, cder, k)
                    break
            if selected:
                break
        if selected is None:
            selected = (cert_meta[0][0], cert_meta[0][1], cert_meta[0][3], key_meta[0][0])

        cert_obj, cert_label, cert_der, private_key = selected
        if not cert_der:
            session.logout(); session.closeSession()
            raise TokenError("Selected token certificate has no DER value.")

        try:
            parsed = x509.load_der_x509_certificate(cert_der)
            if not isinstance(parsed.public_key(), rsa.RSAPublicKey):
                raise TokenError("Selected certificate is not an RSA certificate.")
        except Exception as exc:
            session.logout(); session.closeSession()
            raise TokenError(f"Unable to parse selected certificate: {exc}") from exc

        self.session = session
        self.identity = TokenIdentity(
            slot=slot,
            token_label=token_label,
            certificate_label=cert_label,
            certificate_der=cert_der,
            certificate_base64=base64.b64encode(cert_der).decode("ascii"),
            private_key=private_key,
            certificate=parsed,
        )
        return self.identity

    def sign(self, payload: bytes, algorithm: str) -> str:
        if not self.session or not self.identity:
            raise TokenError("Token session is not open.")
        mechanism = MECHANISMS.get(algorithm.upper())
        if mechanism is None:
            raise TokenError(f"Unsupported signature algorithm: {algorithm}")
        try:
            signature = bytes(self.session.sign(self.identity.private_key, payload, mechanism))
        except Exception as exc:
            raise TokenError(f"Token signing failed: {exc}") from exc
        return base64.b64encode(signature).decode("ascii")

    def close(self) -> None:
        if self.session:
            try:
                self.session.logout()
            except Exception:
                pass
            try:
                self.session.closeSession()
            except Exception:
                pass
            self.session = None
            self.identity = None
