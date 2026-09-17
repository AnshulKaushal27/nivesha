#!/usr/bin/env bash
# Nivesha — one-shot setup for a fresh Ubuntu 24.04 EC2 instance (t3.micro / t4g.micro).
# Idempotent: safe to re-run. Run as root (sudo) from the copied source tree:
#
#   sudo DOMAIN=nivesha.duckdns.org DUCKDNS_TOKEN=xxxx AUTH_USER=anshul AUTH_PASS='a strong password' \
#        bash /opt/nivesha/src/infra/ec2/bootstrap.sh
#
# What it does: 4 GB swap · apt packages · Postgres 16 (local only) · Python venv ·
# Node 20 + frontend build · systemd units · Caddy with automatic HTTPS + basic auth ·
# DuckDNS updater · nightly backups · alembic migrations · calendar seed.
set -euo pipefail

SRC=${SRC:-/opt/nivesha/src}
APP_USER=nivesha
DOMAIN=${DOMAIN:?set DOMAIN, e.g. nivesha.duckdns.org}
AUTH_USER=${AUTH_USER:?set AUTH_USER}
AUTH_PASS=${AUTH_PASS:?set AUTH_PASS}
DUCKDNS_TOKEN=${DUCKDNS_TOKEN:-}
PG_PASS=${PG_PASS:-$(openssl rand -hex 16)}

log() { printf '\n\033[1;36m▶ %s\033[0m\n' "$*"; }

# ── 0. swap (the predictor and pandas need headroom on 1 GB) ─────────────────
if ! swapon --show | grep -q /swapfile; then
  log "Creating 4 GB swap"
  fallocate -l 4G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
  sysctl -w vm.swappiness=20 && echo 'vm.swappiness=20' > /etc/sysctl.d/90-nivesha.conf
fi

# ── 1. packages ──────────────────────────────────────────────────────────────
log "Installing packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3.12 python3.12-venv python3-pip postgresql postgresql-contrib \
  git curl rsync debian-keyring debian-archive-keyring apt-transport-https ca-certificates gnupg libgl1 >/dev/null
if ! command -v node >/dev/null || [[ "$(node -v)" != v20* ]]; then
  curl -fsSL https://deb.nodesource.com/setup_20.x | bash - >/dev/null
  apt-get install -y -qq nodejs >/dev/null
fi
if ! command -v caddy >/dev/null; then
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' > /etc/apt/sources.list.d/caddy-stable.list
  apt-get update -qq && apt-get install -y -qq caddy >/dev/null
fi

# ── 2. app user + tree ───────────────────────────────────────────────────────
id -u $APP_USER >/dev/null 2>&1 || useradd --system --create-home --shell /bin/bash $APP_USER
mkdir -p /opt/nivesha/backups && chown -R $APP_USER:$APP_USER /opt/nivesha

# ── 3. Postgres (localhost only) ─────────────────────────────────────────────
log "Configuring Postgres"
systemctl enable --now postgresql
sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='arena'" | grep -q 1 || \
  sudo -u postgres psql -c "CREATE ROLE arena LOGIN PASSWORD '${PG_PASS}';"
sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='arena'" | grep -q 1 || \
  sudo -u postgres psql -c "CREATE DATABASE arena OWNER arena;"
PGCONF=$(sudo -u postgres psql -tAc "SHOW config_file")
sed -i "s/^#\?shared_buffers.*/shared_buffers = 128MB/; s/^#\?work_mem.*/work_mem = 16MB/; s/^#\?maintenance_work_mem.*/maintenance_work_mem = 64MB/" "$PGCONF"
systemctl restart postgresql

# ── 4. backend .env (merge the copied one with production values) ────────────
log "Writing backend/.env"
ENV=$SRC/backend/.env
[[ -f $ENV ]] || cp $SRC/backend/.env.example $ENV
setkv() { grep -q "^$1=" "$ENV" && sed -i "s#^$1=.*#$1=$2#" "$ENV" || echo "$1=$2" >> "$ENV"; }
if ! grep -q "^DATABASE_URL=postgresql+psycopg://arena:" "$ENV" || grep -q "localhost:5432/arena$" "$ENV"; then
  setkv DATABASE_URL "postgresql+psycopg://arena:${PG_PASS}@127.0.0.1:5432/arena"
fi
setkv CORS_ORIGINS "https://${DOMAIN}"
grep -q "^PREDICTOR_MAX_YEARS=" "$ENV" || setkv PREDICTOR_MAX_YEARS 8
chown $APP_USER:$APP_USER "$ENV" && chmod 600 "$ENV"

# ── 5. python venv + migrations ──────────────────────────────────────────────
log "Python environment"
sudo -u $APP_USER bash -c "cd $SRC/backend && python3.12 -m venv .venv && .venv/bin/pip install -q --upgrade pip && .venv/bin/pip install -q -r requirements.txt"
sudo -u $APP_USER bash -c "cd $SRC/backend && .venv/bin/alembic upgrade head"

# ── 6. frontend build ────────────────────────────────────────────────────────
log "Frontend build"
echo "NEXT_PUBLIC_API_URL=https://${DOMAIN}/api" > $SRC/arena-frontend/.env.production
chown $APP_USER:$APP_USER $SRC/arena-frontend/.env.production
sudo -u $APP_USER bash -c "cd $SRC/arena-frontend && npm ci --no-audit --no-fund >/dev/null && npm run build >/dev/null"

# ── 7. systemd units ─────────────────────────────────────────────────────────
log "systemd services"
sed "s#__SRC__#$SRC#g" $SRC/infra/systemd/nivesha-api.service > /etc/systemd/system/nivesha-api.service
sed "s#__SRC__#$SRC#g" $SRC/infra/systemd/nivesha-web.service > /etc/systemd/system/nivesha-web.service
systemctl daemon-reload
systemctl enable --now nivesha-api nivesha-web

# ── 8. Caddy: HTTPS + basic auth ─────────────────────────────────────────────
log "Caddy"
HASH=$(caddy hash-password --plaintext "$AUTH_PASS")
sed "s#__DOMAIN__#$DOMAIN#g; s#__USER__#$AUTH_USER#g; s#__HASH__#$HASH#g" $SRC/infra/caddy/Caddyfile.tmpl > /etc/caddy/Caddyfile
systemctl enable --now caddy && systemctl reload caddy

# ── 9. DuckDNS updater (public IP changes on stop/start without an Elastic IP) ─
if [[ -n "$DUCKDNS_TOKEN" && "$DOMAIN" == *.duckdns.org ]]; then
  SUB=${DOMAIN%%.duckdns.org}
  cat > /etc/cron.d/duckdns <<EOF
*/5 * * * * root curl -fsS "https://www.duckdns.org/update?domains=${SUB}&token=${DUCKDNS_TOKEN}&ip=" >/dev/null 2>&1
EOF
  curl -fsS "https://www.duckdns.org/update?domains=${SUB}&token=${DUCKDNS_TOKEN}&ip=" >/dev/null || true
fi

# ── 10. backups: nightly pg_dump, 14 kept locally, optional S3 copy ──────────
install -m 755 $SRC/infra/ec2/backup.sh /usr/local/bin/nivesha-backup
echo "15 2 * * * $APP_USER /usr/local/bin/nivesha-backup >/dev/null 2>&1" > /etc/cron.d/nivesha-backup

# ── 11. journald size cap (no CloudWatch bills) ──────────────────────────────
mkdir -p /etc/systemd/journald.conf.d
printf '[Journal]\nSystemMaxUse=200M\n' > /etc/systemd/journald.conf.d/nivesha.conf
systemctl restart systemd-journald

log "Done. Checks:"
sleep 3
curl -fsS http://127.0.0.1:8000/health && echo
systemctl --no-pager --lines=0 status nivesha-api nivesha-web caddy | grep -E 'nivesha|caddy|Active'
echo
echo "Open https://${DOMAIN}  (user: ${AUTH_USER}).  Postgres password saved in ${ENV}."
echo "First data load:  sudo -u ${APP_USER} bash -c 'cd ${SRC}/backend && .venv/bin/python -m jobs.nightly --source upstox --backfill 250'"
