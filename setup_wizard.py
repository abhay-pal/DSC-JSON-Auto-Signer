from __future__ import annotations

import getpass
import json
import os
from pathlib import Path

from credential_store import save_pin

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.json"

SEARCH_ROOTS = [
    Path(r"C:\Windows\System32"),
    Path(r"C:\Windows\SysWOW64"),
    Path(r"C:\Program Files"),
    Path(r"C:\Program Files (x86)"),
]

LIKELY_NAMES = {
    "eps2003csp11.dll",
    "eps2003csp11v2.dll",
    "eps2003csp11v2_64.dll",
    "wdpkcs.dll",
    "wdpkcs64.dll",
    "pkcs11.dll",
    "hyp2003pkcs11.dll",
    "hyperpki.dll",
}

KEYWORDS = ("pkcs11", "pkcs", "eps2003", "hyp2003", "hyperpki", "watchdata", "wdpkcs")


def find_candidates() -> list[Path]:
    found: list[Path] = []
    seen = set()
    for root in SEARCH_ROOTS:
        if not root.exists():
            continue
        try:
            iterator = root.rglob("*.dll")
            for path in iterator:
                name = path.name.lower()
                full = str(path).lower()
                if name in LIKELY_NAMES or any(k in name or k in full for k in KEYWORDS):
                    key = str(path).lower()
                    if key not in seen:
                        seen.add(key)
                        found.append(path)
        except (PermissionError, OSError):
            continue
    return sorted(found, key=lambda p: (0 if "system32" in str(p).lower() else 1, len(str(p))))


def choose_library(config: dict) -> str:
    print("\nSearching installed token middleware DLLs. This can take a minute...")
    candidates = find_candidates()

    current = config.get("pkcs11", {}).get("library_path", "")
    existing = Path(current)
    if current and existing.exists():
        print(f"\nCurrent configured DLL exists:\n  {current}")
        use = input("Use this DLL? [Y/n]: ").strip().lower()
        if use in ("", "y", "yes"):
            return current

    if candidates:
        print("\nPossible PKCS#11 DLLs found:")
        for i, p in enumerate(candidates[:30], 1):
            print(f"  {i}. {p}")
        print("  0. Enter DLL path manually")

        while True:
            choice = input("\nChoose DLL number: ").strip()
            if choice == "0":
                break
            try:
                idx = int(choice)
                if 1 <= idx <= min(30, len(candidates)):
                    return str(candidates[idx - 1])
            except ValueError:
                pass
            print("Invalid selection.")

    manual = input("\nPaste full PKCS#11 DLL path: ").strip().strip('"')
    if not manual:
        raise SystemExit("No DLL selected. Install HyperPKI/token middleware first and run setup_once.bat again.")
    if not Path(manual).exists():
        raise SystemExit(f"DLL not found: {manual}")
    return manual


def main() -> None:
    print("=" * 62)
    print(" DSC JSON Auto Signer - One-Time Setup")
    print("=" * 62)
    print("\n1) Keep your HyperPKI / DSC USB token connected.")
    print("2) Token middleware/driver must already be installed.")
    print("3) This wizard will save your PIN in Windows Credential Manager.")
    print("   PIN is NOT written to config.json or GitHub.\n")

    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

    dll = choose_library(config)
    config["pkcs11"]["library_path"] = dll
    config["pkcs11"]["pin_env_var"] = "DSC_TOKEN_PIN"
    CONFIG_PATH.write_text(json.dumps(config, indent=2), encoding="utf-8")
    print(f"\nSaved DLL path to config.json:\n  {dll}")

    pin1 = getpass.getpass("\nEnter DSC token PIN (hidden): ")
    pin2 = getpass.getpass("Enter PIN again to confirm: ")
    if not pin1:
        raise SystemExit("PIN cannot be empty.")
    if pin1 != pin2:
        raise SystemExit("PINs did not match. Nothing saved.")

    save_pin(pin1)
    print("\nPIN saved securely in Windows Credential Manager.")
    print("It will be reused automatically by run_signer.bat/token_info.bat.")
    print("\nNext step: run token_info.bat to verify the token, then run_signer.bat.")


if __name__ == "__main__":
    main()
