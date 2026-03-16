#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT_DIR}/.env"
RUNTIME_DIR="${ROOT_DIR}/runtime/himalaya"
CONFIG_FILE="${RUNTIME_DIR}/config.toml"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "未找到 .env 文件：${ENV_FILE}"
  exit 1
fi

set -a
source "${ENV_FILE}"
set +a

mkdir -p "${RUNTIME_DIR}"
mkdir -p "${ROOT_DIR}/runtime/drafts"

imap_auth_mode="${IMAP_AUTH_MODE:-password}"
smtp_auth_mode="${SMTP_AUTH_MODE:-password}"

imap_auth_block='backend.auth.raw = "'"${IMAP_PASS:-}"'"'
case "${imap_auth_mode}" in
  password)
    imap_auth_block='backend.auth.raw = "'"${IMAP_PASS:-}"'"'
    ;;
  keyring)
    imap_auth_block='backend.auth.keyring = "'"${IMAP_KEYRING:-}"'"'
    ;;
  *)
    echo "不支持的 IMAP_AUTH_MODE：${imap_auth_mode}"
    exit 1
    ;;
esac

smtp_auth_block='message.send.backend.auth.raw = "'"${SMTP_PASS:-}"'"'
case "${smtp_auth_mode}" in
  password)
    smtp_auth_block='message.send.backend.auth.raw = "'"${SMTP_PASS:-}"'"'
    ;;
  keyring)
    smtp_auth_block='message.send.backend.auth.keyring = "'"${SMTP_KEYRING:-}"'"'
    ;;
  *)
    echo "不支持的 SMTP_AUTH_MODE：${smtp_auth_mode}"
    exit 1
    ;;
esac

cat > "${CONFIG_FILE}" <<EOF
display-name = "${MAIL_DISPLAY_NAME}"
downloads-dir = "${RUNTIME_DIR}/downloads"

[accounts.${MAIL_ACCOUNT_NAME}]
email = "${MAIL_ADDRESS}"
default = true
display-name = "${MAIL_DISPLAY_NAME}"
folder.aliases.inbox = "${MAIL_FOLDER_INBOX:-INBOX}"
folder.aliases.sent = "${MAIL_FOLDER_SENT:-Sent}"
folder.aliases.drafts = "${MAIL_FOLDER_DRAFTS:-Drafts}"
folder.aliases.trash = "${MAIL_FOLDER_TRASH:-Trash}"

backend.type = "imap"
backend.host = "${IMAP_HOST}"
backend.port = ${IMAP_PORT}
backend.encryption.type = "${IMAP_ENCRYPTION}"
backend.login = "${IMAP_LOGIN}"
backend.auth.type = "password"
${imap_auth_block}

message.send.backend.type = "smtp"
message.send.backend.host = "${SMTP_HOST}"
message.send.backend.port = ${SMTP_PORT}
message.send.backend.encryption.type = "${SMTP_ENCRYPTION}"
message.send.backend.login = "${SMTP_LOGIN}"
message.send.backend.auth.type = "password"
${smtp_auth_block}
EOF

echo "已生成配置：${CONFIG_FILE}"
