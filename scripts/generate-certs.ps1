# Self-signed cert generation for Windows hosts (also covered by generate-certs.sh).
# Run:  powershell -ExecutionPolicy Bypass -File scripts\generate-certs.ps1
$CertsDir = Join-Path $PSScriptRoot "..\nginx\certs"
New-Item -ItemType Directory -Force -Path $CertsDir | Out-Null

& openssl req -x509 -nodes -days 365 `
  -newkey rsa:3072 `
  -keyout (Join-Path $CertsDir "versa-cpe.key") `
  -out (Join-Path $CertsDir "versa-cpe.crt") `
  -subj "/C=US/ST=Telecom/L=Network/O=Versa Telecom/OU=Security/CN=localhost" `
  -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"

Write-Host "Self-signed certificate written to $CertsDir"
Write-Host "Replace with the Corporate PKI certificate using the same filenames when available."