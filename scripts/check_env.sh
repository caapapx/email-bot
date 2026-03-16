#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT_DIR}/.env"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "未找到 .env 文件：${ENV_FILE}"
  exit 1
fi

set -a
source "${ENV_FILE}"
set +a

imap_auth_mode="${IMAP_AUTH_MODE:-password}"
smtp_auth_mode="${SMTP_AUTH_MODE:-password}"

required=(
  MAIL_ACCOUNT_NAME
  MAIL_DISPLAY_NAME
  MAIL_ADDRESS
  IMAP_HOST
  IMAP_PORT
  IMAP_ENCRYPTION
  IMAP_LOGIN
  SMTP_HOST
  SMTP_PORT
  SMTP_ENCRYPTION
  SMTP_LOGIN
)

missing=0
for key in "${required[@]}"; do
  if [[ -z "${!key:-}" ]]; then
    echo "缺少必填键：${key}"
    missing=1
  fi
done

case "${imap_auth_mode}" in
  password)
    if [[ -z "${IMAP_PASS:-}" ]]; then
      echo "缺少必填键：IMAP_PASS（当前 IMAP_AUTH_MODE=password）"
      missing=1
    fi
    ;;
  keyring)
    if [[ -z "${IMAP_KEYRING:-}" ]]; then
      echo "缺少必填键：IMAP_KEYRING（当前 IMAP_AUTH_MODE=keyring）"
      missing=1
    fi
    ;;
  *)
    echo "不支持的 IMAP_AUTH_MODE：${imap_auth_mode}"
    missing=1
    ;;
esac

case "${smtp_auth_mode}" in
  password)
    if [[ -z "${SMTP_PASS:-}" ]]; then
      echo "缺少必填键：SMTP_PASS（当前 SMTP_AUTH_MODE=password）"
      missing=1
    fi
    ;;
  keyring)
    if [[ -z "${SMTP_KEYRING:-}" ]]; then
      echo "缺少必填键：SMTP_KEYRING（当前 SMTP_AUTH_MODE=keyring）"
      missing=1
    fi
    ;;
  *)
    echo "不支持的 SMTP_AUTH_MODE：${smtp_auth_mode}"
    missing=1
    ;;
esac

if [[ "${missing}" -ne 0 ]]; then
  exit 1
fi

echo "所有必填 .env 键均已存在。"
