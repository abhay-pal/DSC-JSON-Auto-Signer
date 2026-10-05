from __future__ import annotations

import keyring

SERVICE_NAME = "DSC-JSON-Auto-Signer"
ACCOUNT_NAME = "token_pin"


def save_pin(pin: str) -> None:
    if not pin:
        raise ValueError("PIN cannot be empty.")
    keyring.set_password(SERVICE_NAME, ACCOUNT_NAME, pin)


def load_saved_pin() -> str | None:
    return keyring.get_password(SERVICE_NAME, ACCOUNT_NAME)


def delete_saved_pin() -> None:
    try:
        keyring.delete_password(SERVICE_NAME, ACCOUNT_NAME)
    except keyring.errors.PasswordDeleteError:
        pass
