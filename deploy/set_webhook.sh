#!/usr/bin/env sh
set -eu

if [ -z "${TELEGRAM_BOT_TOKEN:-}" ]; then
  echo "TELEGRAM_BOT_TOKEN is required"
  exit 1
fi

if [ -z "${PUBLIC_BASE_URL:-}" ]; then
  echo "PUBLIC_BASE_URL is required, for example https://conductor-luba.onrender.com"
  exit 1
fi

SECRET_ARG=""
if [ -n "${TELEGRAM_WEBHOOK_SECRET:-}" ]; then
  SECRET_ARG="&secret_token=${TELEGRAM_WEBHOOK_SECRET}"
fi

curl "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook?url=${PUBLIC_BASE_URL}/telegram/webhook${SECRET_ARG}"
