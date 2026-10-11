#!/usr/bin/env bash
set -eu
umask 077
# Run in a fresh directory. Refuse to overwrite an existing cert directory.
mkdir cert
openssl genpkey -algorithm ed25519 -out cert/ca.key.pem
openssl req -config /dev/null -new -x509 -key cert/ca.key.pem -out cert/ca.crt.pem \
  -days 30 -subj '/CN=Symbol P2P example CA' \
  -addext 'basicConstraints=critical,CA:TRUE,pathlen:0' \
  -addext 'keyUsage=critical,keyCertSign,cRLSign'
openssl genpkey -algorithm ed25519 -out cert/node.key.pem
openssl req -config /dev/null -new -key cert/node.key.pem -out cert/node.csr.pem \
  -subj '/CN=Symbol P2P example transport'
cat > cert/node.ext <<'EOF'
basicConstraints=critical,CA:FALSE
keyUsage=critical,digitalSignature
extendedKeyUsage=serverAuth,clientAuth
subjectKeyIdentifier=hash
authorityKeyIdentifier=keyid,issuer
EOF
openssl x509 -req -in cert/node.csr.pem -CA cert/ca.crt.pem \
  -CAkey cert/ca.key.pem -CAcreateserial -out cert/node.crt.pem \
  -days 7 -extfile cert/node.ext
cat cert/node.crt.pem cert/ca.crt.pem > cert/node.full.crt.pem
openssl verify -check_ss_sig -CAfile cert/ca.crt.pem cert/node.crt.pem
