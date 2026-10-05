$patterns = @("*pkcs11*.dll", "*p11*.dll", "eps2003*.dll", "wd*.dll", "WatchData*.dll")
$roots = @("C:\\Windows\\System32", "C:\\Windows\\SysWOW64", "C:\\Program Files", "C:\\Program Files (x86)")
Write-Host "Searching common PKCS#11 middleware DLL locations..." -ForegroundColor Cyan
foreach ($root in $roots) {
  if (Test-Path $root) {
    foreach ($pattern in $patterns) {
      Get-ChildItem -Path $root -Filter $pattern -File -Recurse -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty FullName
    }
  }
}
