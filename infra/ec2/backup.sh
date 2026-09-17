#!/usr/bin/env bash
# Nightly Postgres dump. Keeps 14 locally; copies to S3 if BACKUP_S3_BUCKET is set in backend/.env.
set -euo pipefail
SRC=${SRC:-/opt/nivesha/src}
OUT=/opt/nivesha/backups
URL=$(grep '^DATABASE_URL=' $SRC/backend/.env | cut -d= -f2- | sed 's#postgresql+psycopg://#postgresql://#')
BUCKET=$(grep '^BACKUP_S3_BUCKET=' $SRC/backend/.env | cut -d= -f2- || true)
F=$OUT/arena-$(date +%F).dump
pg_dump --format=custom --compress=6 "$URL" -f "$F"
ls -1t $OUT/arena-*.dump | tail -n +15 | xargs -r rm -f
if [[ -n "$BUCKET" ]] && command -v aws >/dev/null; then
  aws s3 cp "$F" "s3://$BUCKET/nivesha/$(basename $F)" --only-show-errors
fi
echo "backup ok: $F ($(du -h "$F" | cut -f1))"
