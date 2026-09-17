#!/usr/bin/env bash
# Re-deploy after the source tree at $SRC was updated (see infra/deploy.sh).
set -euo pipefail
SRC=${SRC:-/opt/nivesha/src}
APP_USER=nivesha
echo "▶ backend deps + migrations"
sudo -u $APP_USER bash -c "cd $SRC/backend && .venv/bin/pip install -q -r requirements.txt && .venv/bin/alembic upgrade head"
echo "▶ frontend build"
sudo -u $APP_USER bash -c "cd $SRC/arena-frontend && npm ci --no-audit --no-fund >/dev/null && npm run build >/dev/null"
echo "▶ restart"
systemctl restart nivesha-api nivesha-web
sleep 3 && curl -fsS http://127.0.0.1:8000/health && echo && echo "✓ updated"
