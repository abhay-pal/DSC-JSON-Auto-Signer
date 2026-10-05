from __future__ import annotations

import json
from pathlib import Path
from typing import Tuple


class JSONSigningError(RuntimeError):
    pass


def _decode_json_bytes(raw: bytes) -> Tuple[str, str]:
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw[3:].decode("utf-8"), "utf-8-sig"
    try:
        return raw.decode("utf-8"), "utf-8"
    except UnicodeDecodeError as exc:
        raise JSONSigningError("Input JSON must be UTF-8 encoded.") from exc


def load_and_validate(path: Path):
    raw = path.read_bytes()
    text, encoding = _decode_json_bytes(raw)
    try:
        obj = json.loads(text)
    except json.JSONDecodeError as exc:
        raise JSONSigningError(f"Invalid JSON: {exc}") from exc
    if not isinstance(obj, dict):
        raise JSONSigningError("Top-level JSON must be an object.")
    if "digSign" in obj:
        raise JSONSigningError("Input already contains digSign; refusing to sign twice.")
    return raw, text, obj, encoding


def build_payload(raw: bytes, text: str, obj: dict, payload_mode: str) -> bytes:
    mode = payload_mode.lower()
    if mode == "raw":
        return raw
    if mode == "raw_trimmed":
        return raw.rstrip(b"\r\n\t ")
    if mode == "compact_json":
        return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if mode == "sorted_compact_json":
        return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    raise JSONSigningError(f"Unknown payload_mode: {payload_mode}")


def _digsign_text(signature_b64: str, certificate_b64: str, signer_version: str, pretty: bool = False) -> str:
    block = {
        "startSignature": signature_b64,
        "startCertificate": certificate_b64,
        "signerVersion": signer_version,
    }
    if pretty:
        return json.dumps(block, ensure_ascii=False, indent=2)
    return json.dumps(block, ensure_ascii=False, separators=(",", ":"))


def make_signed_json(text: str, obj: dict, signature_b64: str, certificate_b64: str,
                     signer_version: str, output_style: str) -> bytes:
    style = output_style.lower()
    if style == "preserve":
        stripped = text.rstrip()
        if not stripped.endswith("}"):
            raise JSONSigningError("Input JSON has no final top-level closing brace.")
        body = stripped[:-1].rstrip()
        sep = "" if body.endswith("{") else ","
        signed = body + sep + '\n"digSign":\n' + _digsign_text(signature_b64, certificate_b64, signer_version, pretty=True) + "\n}"
        return signed.encode("utf-8")

    result = dict(obj)
    result["digSign"] = {
        "startSignature": signature_b64,
        "startCertificate": certificate_b64,
        "signerVersion": signer_version,
    }
    if style == "compact":
        return json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if style == "pretty":
        return json.dumps(result, ensure_ascii=False, indent=2).encode("utf-8")
    raise JSONSigningError(f"Unknown output_style: {output_style}")
