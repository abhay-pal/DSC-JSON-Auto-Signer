"""Inspect an existing signed JSON and report the RSA PKCS#1 hash OID used.
Usage: python tools/inspect_signed_sample.py path\\to\\signed.json
"""
import base64, json, sys
from pathlib import Path
from cryptography import x509

path = Path(sys.argv[1])
obj = json.loads(path.read_text(encoding="utf-8-sig"))
sig = base64.b64decode(obj["digSign"]["startSignature"])
cert = x509.load_der_x509_certificate(base64.b64decode(obj["digSign"]["startCertificate"]))
pn = cert.public_key().public_numbers()
em = pow(int.from_bytes(sig, "big"), pn.e, pn.n).to_bytes((pn.n.bit_length()+7)//8, "big")
prefixes = {
    bytes.fromhex("3021300906052b0e03021a05000414"): "SHA1_RSA_PKCS",
    bytes.fromhex("3031300d060960864801650304020105000420"): "SHA256_RSA_PKCS",
    bytes.fromhex("3041300d060960864801650304020205000430"): "SHA384_RSA_PKCS",
    bytes.fromhex("3051300d060960864801650304020305000440"): "SHA512_RSA_PKCS",
}
print("Subject:", cert.subject.rfc4514_string())
print("Signature bytes:", len(sig))
for p, name in prefixes.items():
    idx = em.find(p)
    if idx >= 0:
        digest = em[idx+len(p):]
        print("Detected mechanism:", name)
        print("Embedded digest:", digest.hex())
        break
else:
    print("Could not recognize PKCS#1 v1.5 DigestInfo prefix.")
