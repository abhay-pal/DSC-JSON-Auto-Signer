from __future__ import annotations

import argparse
import getpass
import json
import logging
import os
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

from credential_store import load_saved_pin
from json_signing import build_payload, load_and_validate, make_signed_json
from pkcs11_signer import PKCS11Signer, TokenError


ROOT = Path(__file__).resolve().parent


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def resolve_folder(value: str) -> Path:
    p = Path(value)
    return p if p.is_absolute() else ROOT / p


def setup_logging(log_dir: Path) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"signer_{datetime.now():%Y%m%d}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[logging.FileHandler(log_file, encoding="utf-8"), logging.StreamHandler(sys.stdout)],
    )


def get_pin(cfg: dict) -> str:
    saved = load_saved_pin()
    if saved:
        logging.info("Using saved DSC PIN from Windows Credential Manager.")
        return saved

    env_name = cfg["pkcs11"].get("pin_env_var", "DSC_TOKEN_PIN")
    pin = os.environ.get(env_name, "")
    if pin:
        logging.info("Using DSC PIN from environment variable %s.", env_name)
        return pin

    return getpass.getpass(
        "Enter DSC token PIN (not saved automatically). "
        "Run setup_once.bat to save it securely for future runs: "
    )


def unique_target(folder: Path, name: str) -> Path:
    target = folder / name
    if not target.exists():
        return target
    stem, suffix = target.stem, target.suffix
    i = 2
    while True:
        candidate = folder / f"{stem}_{i}{suffix}"
        if not candidate.exists():
            return candidate
        i += 1


def wait_until_stable(path: Path, checks: int, sleep_seconds: float = 0.5) -> bool:
    last = None
    stable = 0
    for _ in range(max(4, checks * 3)):
        try:
            stat = path.stat()
            current = (stat.st_size, stat.st_mtime_ns)
        except FileNotFoundError:
            return False
        if current == last:
            stable += 1
            if stable >= checks:
                return True
        else:
            stable = 0
        last = current
        time.sleep(sleep_seconds)
    return False


def process_file(path: Path, signer: PKCS11Signer, cfg: dict, folders: dict) -> None:
    sig_cfg = cfg["signature"]
    try:
        raw, text, obj, _ = load_and_validate(path)
        payload = build_payload(raw, text, obj, sig_cfg.get("payload_mode", "raw"))
        signature = signer.sign(payload, sig_cfg.get("algorithm", "SHA1_RSA_PKCS"))
        cert_b64 = signer.identity.certificate_base64
        out_bytes = make_signed_json(
            text=text,
            obj=obj,
            signature_b64=signature,
            certificate_b64=cert_b64,
            signer_version=sig_cfg.get("signer_version", "1.0"),
            output_style=sig_cfg.get("output_style", "preserve"),
        )
        suffix = sig_cfg.get("signed_suffix", "_Signed")
        out_name = f"{path.stem}{suffix}{path.suffix}"
        target = unique_target(folders["output"], out_name)
        target.write_bytes(out_bytes)
        archived = unique_target(folders["archive"], path.name)
        shutil.move(str(path), str(archived))
        logging.info("SIGNED | %s -> %s", path.name, target.name)
    except Exception as exc:
        logging.exception("FAILED | %s | %s", path.name, exc)
        try:
            failed = unique_target(folders["error"], path.name)
            shutil.move(str(path), str(failed))
            (failed.with_suffix(failed.suffix + ".error.txt")).write_text(str(exc), encoding="utf-8")
        except Exception:
            logging.exception("Could not move failed file %s", path)


def build_signer(cfg: dict, pin: str) -> PKCS11Signer:
    c = cfg["pkcs11"]
    signer = PKCS11Signer(
        library_path=c["library_path"],
        slot_index=int(c.get("slot_index", 0)),
        token_label_contains=c.get("token_label_contains", ""),
        certificate_label_contains=c.get("certificate_label_contains", ""),
        private_key_label_contains=c.get("private_key_label_contains", ""),
    )
    identity = signer.open(pin)
    parsed = identity.certificate
    subject = parsed.subject.rfc4514_string()
    logging.info(
        "TOKEN CONNECTED | %s | Certificate: %s | Subject: %s",
        identity.token_label,
        identity.certificate_label,
        subject,
    )
    return signer


def main() -> int:
    parser = argparse.ArgumentParser(description="DSC JSON Auto Signer")
    parser.add_argument("--config", default=str(ROOT / "config.json"))
    parser.add_argument("--once", action="store_true", help="Process current JSON files once and exit")
    parser.add_argument("--token-info", action="store_true", help="Connect to token and print selected certificate info")
    args = parser.parse_args()

    cfg = load_config(Path(args.config))
    folders = {k: resolve_folder(v) for k, v in cfg["folders"].items()}
    for p in folders.values():
        p.mkdir(parents=True, exist_ok=True)
    setup_logging(folders["logs"])

    pin = get_pin(cfg)
    signer = None
    try:
        signer = build_signer(cfg, pin)
        if args.token_info:
            ident = signer.identity
            cert = ident.certificate
            print("Token label :", ident.token_label)
            print("Cert label  :", ident.certificate_label)
            print("Subject     :", cert.subject.rfc4514_string())
            print("Valid until :", cert.not_valid_after_utc)
            return 0

        poll = float(cfg.get("watcher", {}).get("poll_seconds", 2))
        stable_checks = int(cfg.get("watcher", {}).get("stable_checks", 2))
        logging.info("Watching input folder: %s", folders["input"])
        logging.info(
            "Algorithm=%s | payload_mode=%s | output_style=%s",
            cfg["signature"].get("algorithm"),
            cfg["signature"].get("payload_mode"),
            cfg["signature"].get("output_style"),
        )

        while True:
            files = sorted(p for p in folders["input"].glob("*.json") if p.is_file())
            for path in files:
                if wait_until_stable(path, stable_checks):
                    process_file(path, signer, cfg, folders)
            if args.once:
                break
            time.sleep(poll)
        return 0
    except KeyboardInterrupt:
        logging.info("Stopped by user.")
        return 0
    except TokenError as exc:
        logging.error("TOKEN ERROR: %s", exc)
        return 2
    except Exception:
        logging.exception("Fatal error")
        return 1
    finally:
        if signer:
            signer.close()


if __name__ == "__main__":
    raise SystemExit(main())
