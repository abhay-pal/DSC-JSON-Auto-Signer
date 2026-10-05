# DSC JSON Auto Signer

Windows folder-watcher that signs JSON files with an RSA private key held inside a DSC/USB token via PKCS#11.

## What it does

1. Watches `input/` for `.json` files.
2. Validates the JSON and refuses already-signed files.
3. Signs the configured byte representation using the private key inside the USB token.
4. Reads the X.509 certificate from the token and embeds it as Base64.
5. Adds:

```json
"digSign": {
  "startSignature": "...",
  "startCertificate": "...",
  "signerVersion": "1.0"
}
```

6. Saves the result to `output/` as `*_Signed.json`.
7. Moves successful inputs to `archive/`; failures go to `error/` with a reason file.
8. Writes logs under `logs/`.

## Important compatibility note

The provided signed sample was inspected cryptographically. Its RSA PKCS#1 v1.5 `DigestInfo` identifies SHA-1, so the supplied default is `SHA1_RSA_PKCS`.

However, a signed output file alone does **not** reveal with certainty which exact byte representation the original vendor utility hashed before signing. JSON signatures are byte-sensitive. This project therefore supports several `payload_mode` values in `config.json`:

- `raw` (default): signs the exact input file bytes.
- `raw_trimmed`: exact input bytes with trailing whitespace removed.
- `compact_json`: parses and serializes compact UTF-8 JSON.
- `sorted_compact_json`: compact JSON with sorted keys.

Start with `raw`. If ICEGATE/vendor validation says the signature is invalid, compare against a matched pair where the **same unsigned file** was signed by the existing official/vendor signer, then select/implement its exact byte canonicalization.

## Setup

### 1. Install token middleware
Install the official driver/middleware for your DSC token (ePass, ProxKey, WatchData, etc.). Keep the token connected.

### 2. Find PKCS#11 DLL
Run PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File tools\find_pkcs11_dll.ps1
```

Typical names vary by token. Do not blindly use the sample path; use the DLL installed by your token vendor.

### 3. Configure
Edit `config.json`:

```json
"pkcs11": {
  "library_path": "C:\\path\\to\\your\\pkcs11.dll",
  "slot_index": 0,
  "token_label_contains": "",
  "certificate_label_contains": "",
  "private_key_label_contains": "",
  "pin_env_var": "DSC_TOKEN_PIN"
}
```

Leaving label filters empty selects the first matching RSA signing identity, preferring a cert/key pair with the same `CKA_ID`.

### 4. Install Python dependencies
Double-click `install.bat`.

Recommended: Python 3.11 or 3.12 (64-bit if your token middleware is 64-bit). Python and the PKCS#11 DLL must have compatible architecture.

### 5. Verify token
Double-click `token_info.bat` and enter the token PIN. The PIN is not stored by the program.

### 6. Run
Double-click `run_signer.bat`.

Drop unsigned `.json` files into `input/`. Signed files appear in `output/`.

For a one-time batch, use `sign_once.bat`.

## PIN handling
By default the app asks for the PIN interactively on startup. It can also read an environment variable named `DSC_TOKEN_PIN`, but storing a token PIN in a persistent environment variable is less secure and is not recommended for shared PCs.

## Defaults matching the supplied signed sample

```json
"signature": {
  "algorithm": "SHA1_RSA_PKCS",
  "payload_mode": "raw",
  "output_style": "preserve",
  "signer_version": "1.0",
  "signed_suffix": "_Signed"
}
```

`output_style=preserve` keeps the original top-level JSON text and inserts `digSign` before the final closing brace, minimizing unintended data changes.

## Troubleshooting

- **Could not load PKCS#11 library**: wrong DLL path or 32/64-bit mismatch.
- **No token detected**: middleware missing, token unplugged, or wrong DLL.
- **Token login failed**: incorrect PIN; repeated wrong attempts can lock many DSC tokens.
- **No RSA private key/certificate**: label filters are too strict or wrong token slot selected.
- **Signed file rejected by ICEGATE/vendor**: most likely exact payload canonicalization differs. Obtain a matched same-file before/after example from the existing signer and adjust `payload_mode`.

## Security

The private key is never exported from the DSC token. The application asks the token middleware to perform the signature operation. Do not copy private-key material into this project.
