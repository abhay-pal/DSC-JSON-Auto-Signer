# DSC JSON Auto Signer

Windows tool jo unsigned JSON files ko DSC / HyperPKI USB token se automatically sign karta hai.

## Simple flow

```text
input\
  unsigned.json
      ↓
run_signer.bat
      ↓
DSC token private key se digital signature
      ↓
output\
  unsigned_Signed.json
```

Successful original file `archive\` me move hoti hai. Failure hua to file `error\` me chali jaati hai aur reason log me milta hai.

---

# First-time setup — step by step

## Step 1 — HyperPKI driver install karo

DSC token PC me lagao.

Token ke virtual CD drive me agar `HyperPKI_HYP2003_Setup` dikhe to:

1. Setup file par **Right Click**
2. **Run as administrator**
3. Driver/middleware install complete karo
4. Token connected rehne do

Agar Windows bole *Administrator account required*, normal double-click se install mat karo. Administrator rights required hain.

---

## Step 2 — Python install karo

Windows me **Python 3.11 ya Python 3.12** install hona chahiye.

Install karte waqt:

```text
Add Python to PATH
```

tick kar dena.

Check karne ke liye CMD me:

```bat
py --version
```

---

## Step 3 — GitHub se project clone karo

```bat
git clone https://github.com/abhay-pal/DSC-JSON-Auto-Signer.git
cd DSC-JSON-Auto-Signer
```

Git use nahi karna ho to GitHub se **Code → Download ZIP** karke extract bhi kar sakte ho.

---

## Step 4 — Bas `setup_once.bat` run karo

Project folder me:

```text
setup_once.bat
```

double-click karo.

Ye automatically:

- Python virtual environment banayega
- required packages install karega
- HyperPKI / PKCS#11 DLL search karega
- correct DLL choose karne dega
- `config.json` update karega
- DSC PIN **ek baar** maangega
- PIN ko **Windows Credential Manager** me securely save karega

### Important

PIN **config.json me mat likhna**.

Ye line:

```json
"pin_env_var": "DSC_TOKEN_PIN"
```

PIN nahi hai. Ye sirf environment-variable ka naam hai.

Actual PIN first setup me hidden input ke through enter karna hai.

---

# PIN baar-baar enter nahi karna padega

`setup_once.bat` ke time PIN ek baar enter karne ke baad app usko Windows Credential Manager me store karta hai.

Uske baad:

```text
token_info.bat
run_signer.bat
sign_once.bat
```

automatically saved PIN use karenge.

### Security

PIN:

- GitHub par upload nahi hota
- `config.json` me save nahi hota
- plain-text file me save nahi hota
- Windows Credential Manager me local Windows user ke under store hota hai

Agar PIN remove/change karna ho:

```text
clear_saved_pin.bat
```

run karo, then `setup_once.bat` dobara run karo.

---

# Step 5 — Token test karo

First setup complete hone ke baad:

```text
token_info.bat
```

run karo.

Successful result approximately:

```text
Token label : ...
Cert label  : ...
Subject     : CN=...
Valid until : ...
```

Agar ye aa gaya to token successfully connect ho gaya.

---

# Step 6 — Auto signer start karo

```text
run_signer.bat
```

double-click karo.

Program `input\` folder ko continuously watch karega.

Unsigned JSON:

```text
input\F_CUCHE01_....json
```

me paste karo.

Signed file automatically:

```text
output\F_CUCHE01_...._Signed.json
```

me aayegi.

Original successfully processed JSON:

```text
archive\
```

me move ho jayegi.

Signing failure:

```text
error\
```

me jayegi.

Logs:

```text
logs\
```

me milenge.

---

# Ek baar ka batch sign

Continuous watcher nahi chahiye aur sirf currently available files sign karni hain to:

```text
sign_once.bat
```

run karo.

---

# config.json

Normally first setup ke baad manually edit karne ki zarurat nahi hai.

Main section:

```json
"pkcs11": {
  "library_path": "C:\\...\\your-token-pkcs11.dll",
  "slot_index": 0,
  "token_label_contains": "",
  "certificate_label_contains": "",
  "private_key_label_contains": "",
  "pin_env_var": "DSC_TOKEN_PIN"
}
```

## library_path

HyperPKI/token middleware ka PKCS#11 DLL path.

`setup_once.bat` isko automatically search/select karne me help karta hai.

## slot_index

Ek hi DSC token connected hai to:

```json
"slot_index": 0
```

rehne do.

## token/certificate/private-key labels

Normally blank rehne do:

```json
"token_label_contains": "",
"certificate_label_contains": "",
"private_key_label_contains": ""
```

Program certificate aur RSA private key select karega, preferably matching PKCS#11 `CKA_ID` pair se.

---

# Signature settings

Provided signed sample ko inspect karne par RSA PKCS#1 v1.5 signature me SHA-1 DigestInfo identify hua, therefore current default:

```json
"signature": {
  "algorithm": "SHA1_RSA_PKCS",
  "payload_mode": "raw",
  "output_style": "preserve",
  "signer_version": "1.0",
  "signed_suffix": "_Signed"
}
```

Available signing algorithms:

```text
SHA1_RSA_PKCS
SHA256_RSA_PKCS
SHA384_RSA_PKCS
SHA512_RSA_PKCS
```

Current sample matching default:

```text
SHA1_RSA_PKCS
```

---

# Important — exact ICEGATE/vendor compatibility

Signed sample se ye identify kiya ja sakta hai ki signature RSA PKCS#1 v1.5 + SHA-1 use kar raha hai.

Lekin signed JSON alone se 100% prove nahi hota ki original vendor software JSON ke **exact kaunse bytes** sign karta hai.

JSON signature byte-sensitive hoti hai.

Supported `payload_mode`:

```text
raw
raw_trimmed
compact_json
sorted_compact_json
```

Default:

```json
"payload_mode": "raw"
```

Final production validation ke liye best test hai:

1. Ek exact unsigned JSON lo
2. Usko existing official/vendor signer se sign karo
3. Same exact unsigned JSON ko is bot se sign karo
4. Receiving system/ICEGATE validation compare karo

Agar signature rejection aaye, payload canonicalization ko vendor format ke according adjust karna hoga.

---

# Folder structure

```text
DSC-JSON-Auto-Signer\
│
├── input\
├── output\
├── archive\
├── error\
├── logs\
├── tools\
│
├── config.json
├── main.py
├── json_signing.py
├── pkcs11_signer.py
├── credential_store.py
├── setup_wizard.py
│
├── setup_once.bat
├── install.bat
├── token_info.bat
├── run_signer.bat
├── sign_once.bat
├── clear_saved_pin.bat
└── requirements.txt
```

---

# Common errors

## Administrator account required

HyperPKI setup ko **Right Click → Run as administrator** se install karo.

## Could not load PKCS#11 library

Wrong DLL selected hai ya DLL/driver architecture mismatch hai.

`setup_once.bat` dobara run karke correct DLL choose karo.

## No DSC/USB token detected

Check:

- token connected hai
- HyperPKI middleware installed hai
- correct PKCS#11 DLL configured hai

## Token login failed

Saved PIN wrong ho sakta hai.

Run:

```text
clear_saved_pin.bat
```

then:

```text
setup_once.bat
```

and correct PIN save karo.

**Repeated wrong PIN attempts mat karo — token lock ho sakta hai.**

## Signed JSON receiving system reject kar raha hai

Most likely payload byte/canonicalization mismatch hai. Existing signer ka matched same-file before/after sample required hoga.

---

# Daily use

First-time setup ke baad daily process sirf:

```text
1. DSC token plug in karo
2. run_signer.bat start karo
3. JSON files input folder me paste karo
4. Signed JSON output folder se le lo
```

PIN dobara enter karne ki zarurat nahi hogi jab tak saved credential remove/change nahi hota.
