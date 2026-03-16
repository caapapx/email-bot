#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT_DIR}/.env"
RUNTIME_DIR="${ROOT_DIR}/runtime/himalaya"
CONFIG_FILE="${RUNTIME_DIR}/config.toml"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Missing .env at ${ENV_FILE}"
  exit 1
fi

set -a
source "${ENV_FILE}"
set +a

mkdir -p "${RUNTIME_DIR}"

cat > "${CONFIG_FILE}" <<EOF
display-name = "${MAIL_DISPLAY_NAME}"
downloads-dir = "${RUNTIME_DIR}/downloads"

[${MAIL_ACCOUNT_NAME}]
email = "${MAIL_ADDRESS}"
default = true
display-name = "${MAIL_DISPLAY_NAME}"

[${MAIL_ACCOUNT_NAME}.imap]
host = "${IMAP_HOST}"
port = ${IMAP_PORT}
encryption = "${IMAP_ENCRYPTION}"
login = "${IMAP_LOGIN}"
auth = { type = "passwd", passwd = "${IMAP_PASS}" }

[${MAIL_ACCOUNT_NAME}.smtp]
host = "${SMTP_HOST}"
port = ${SMTP_PORT}
encryption = "${SMTP_ENCRYPTION}"
login = "${SMTP_LOGIN}"
auth = { type = "passwd", passwd = "${SMTP_PASS}" }
EOF

echo "Rendered ${CONFIG_FILE}"
