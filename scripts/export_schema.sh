#!/usr/bin/env bash
# export_schema.sh — Bootstrap local MySQL with the remote schema.
#
# Usage:
#   ./scripts/export_schema.sh              # dump schema + apply locally
#   ./scripts/export_schema.sh --dump-only  # just dump to /tmp, don't apply
#
# Prerequisites:
#   - Local MySQL running (sudo port load mysql8-server)
#   - Database + user already created:
#       CREATE DATABASE fairtlou_miolingo CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
#       CREATE USER 'miolingo_local'@'localhost' IDENTIFIED BY '...';
#       GRANT ALL ON fairtlou_miolingo.* TO 'miolingo_local'@'localhost';
#   - SSH key accepted by miolingo.io:722
set -euo pipefail

DUMP_FILE="/tmp/miolingo_schema.sql"
REMOTE_HOST="miolingo.io"
REMOTE_PORT=722
REMOTE_USER="fairtlou"
REMOTE_DB="fairtlou_miolingo"
REMOTE_DB_USER="fairtlou_miolingo_matthew"

LOCAL_DB="fairtlou_miolingo"
LOCAL_USER="miolingo_local"

echo "⏳ Dumping remote schema (no data) from ${REMOTE_HOST}..."
ssh -p "${REMOTE_PORT}" "${REMOTE_USER}@${REMOTE_HOST}" \
  "mysqldump -u ${REMOTE_DB_USER} -p --no-data ${REMOTE_DB}" \
  > "${DUMP_FILE}"

echo "✅ Schema saved to ${DUMP_FILE}"

if [[ "${1:-}" == "--dump-only" ]]; then
    echo "Done (--dump-only). Apply manually with:"
    echo "  mysql -u ${LOCAL_USER} -p ${LOCAL_DB} < ${DUMP_FILE}"
    exit 0
fi

echo "⏳ Applying schema to local MySQL (${LOCAL_DB})..."
mysql -u "${LOCAL_USER}" -p "${LOCAL_DB}" < "${DUMP_FILE}"

echo "✅ Local schema bootstrapped from remote."
