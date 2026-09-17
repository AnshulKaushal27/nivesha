#!/usr/bin/env bash
# Deploy from this laptop to the EC2 instance.
#
#   infra/deploy.sh ubuntu@1.2.3.4                   # sync source + rebuild + restart
#   infra/deploy.sh ubuntu@1.2.3.4 --with-data       # also copy the local Postgres data (first deploy)
#   FIRST=1 DOMAIN=... AUTH_USER=... AUTH_PASS=... DUCKDNS_TOKEN=... infra/deploy.sh ubuntu@1.2.3.4 --with-data
#
# Requires: ssh access with your key pair; local `pg_dump` (brew install libpq) for --with-data.
set -euo pipefail
HOST=${1:?usage: infra/deploy.sh user@host [--with-data]}
WITH_DATA=${2:-}
HERE=$(cd "$(dirname "$0")/.." && pwd)
REMOTE=/opt/nivesha/src

echo "▶ syncing source to $HOST:$REMOTE"
ssh "$HOST" 'sudo mkdir -p /opt/nivesha/src && sudo chown -R $USER /opt/nivesha'
rsync -az --delete \
  --exclude .git --exclude node_modules --exclude .next --exclude .venv --exclude __pycache__ \
  --exclude '*.db' --exclude research/reports --exclude 'backend/models/' \
  "$HERE"/ "$HOST:$REMOTE/"

if [[ "$WITH_DATA" == "--with-data" ]]; then
  echo "▶ dumping local Postgres"
  if command -v pg_dump >/dev/null; then
    LOCAL_URL=$(grep '^DATABASE_URL=' "$HERE/backend/.env" | cut -d= -f2- | sed 's#postgresql+psycopg://#postgresql://#')
    pg_dump --format=custom --compress=6 "$LOCAL_URL" -f /tmp/nivesha-local.dump
  else
    # no libpq on the laptop: dump from inside the docker-compose Postgres container
    docker exec ai-arena-postgres pg_dump -U arena --format=custom --compress=6 arena > /tmp/nivesha-local.dump
  fi
  ls -lh /tmp/nivesha-local.dump
  scp /tmp/nivesha-local.dump "$HOST:/tmp/nivesha-local.dump"
fi

if [[ "${FIRST:-}" == "1" ]]; then
  echo "▶ first-time bootstrap"
  ssh "$HOST" "sudo DOMAIN='$DOMAIN' AUTH_USER='$AUTH_USER' AUTH_PASS='$AUTH_PASS' DUCKDNS_TOKEN='${DUCKDNS_TOKEN:-}' bash $REMOTE/infra/ec2/bootstrap.sh"
else
  ssh "$HOST" "sudo bash $REMOTE/infra/ec2/update.sh"
fi

if [[ "$WITH_DATA" == "--with-data" ]]; then
  echo "▶ restoring data on the server"
  ssh "$HOST" "sudo -u postgres pg_restore --clean --if-exists --no-owner --role=arena -d arena /tmp/nivesha-local.dump 2>&1 | grep -v 'already exists' || true; \
               sudo -u nivesha bash -c 'cd $REMOTE/backend && .venv/bin/alembic upgrade head'; sudo systemctl restart nivesha-api; rm -f /tmp/nivesha-local.dump"
fi
echo "✓ deployed"
