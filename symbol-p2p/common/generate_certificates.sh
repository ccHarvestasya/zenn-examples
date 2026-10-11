#!/usr/bin/env bash
set -eu
umask 077
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cert_dir="${1:-$script_dir/cert}"
# Generate once for the series. Never overwrite an existing identity.
if [[ -e "$cert_dir" || -L "$cert_dir" ]]; then
  echo "既存の証明書ディレクトリを上書きしません: $cert_dir" >&2
  echo "各回で同じ証明書を使ってください。" >&2
  exit 1
fi
mkdir -- "$cert_dir"
cd -- "$cert_dir"
openssl genpkey -algorithm ed25519 -out ca.key.pem
openssl req -config /dev/null -new -x509 -key ca.key.pem -out ca.crt.pem \
  -days 3650 -subj '/CN=Symbol P2P example CA' \
  -addext 'basicConstraints=critical,CA:TRUE,pathlen:0' \
  -addext 'keyUsage=critical,keyCertSign,cRLSign'
openssl genpkey -algorithm ed25519 -out node.key.pem
openssl req -config /dev/null -new -key node.key.pem -out node.csr.pem \
  -subj '/CN=Symbol P2P example transport'
cat > node.ext <<'EOF'
basicConstraints=critical,CA:FALSE
keyUsage=critical,digitalSignature
extendedKeyUsage=serverAuth,clientAuth
subjectKeyIdentifier=hash
authorityKeyIdentifier=keyid,issuer
EOF
openssl x509 -req -in node.csr.pem -CA ca.crt.pem \
  -CAkey ca.key.pem -CAcreateserial -out node.crt.pem \
  -days 365 -extfile node.ext
cat node.crt.pem ca.crt.pem > node.full.crt.pem
openssl verify -check_ss_sig -CAfile ca.crt.pem node.crt.pem
