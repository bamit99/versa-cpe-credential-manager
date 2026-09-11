#!/usr/bin/env bash
# Regenerate the self-signed certificate used by nginx.
# Replace with Corporate PKI cert/key later WITHOUT changing code (same filenames).
set -euo pipefail

CERT_DIR="$(dirname "$0")/../nginx/certs"
mkdir -p "$CERT_DIR"

openssl req -x509 -nodes -days 365 \
  -newkey rsa:3072 \
  -keyout "$CERT_DIR/versa-cpe.key" \
  -out "$CERT_DIR/versa-cpe.crt" \
  -subj "/C=US/ST=Telecom/L=Network/O=Versa Telecom/OU=Security/CN=localhost" \
  -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"

echo "Self-signed certificate written to $CERT_DIR (versa-cpe.crt / versa-cpe.key)"
echo "Replace with the Corporate PKI certificate using the same filenames when available."